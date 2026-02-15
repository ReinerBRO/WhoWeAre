import fs from "node:fs/promises";
import path from "node:path";
import type { OpenClawPluginApi, ReplyPayload } from "openclaw/plugin-sdk";

const STATE_FILE = "openclaw-whoweare-state.json";
const STATE_VERSION = 1;
const URL_REGEX = /https?:\/\/[^\s]+/g;
const DEFAULT_WHOAMI_TIMEOUT_MS = 10 * 60_000;
const DEFAULT_WHOAREU_TIMEOUT_MS = 10 * 60_000;
const DEFAULT_OPENCLAW_TIMEOUT_MS = 10 * 60_000;
const DEFAULT_OPENCLAW_AGENT_ID = "main";
const DEFAULT_OPENCLAW_BIN = "openclaw";
const MAX_SCRAPE_TEXT_CHARS = 20_000;

type WhoamiSynthesisMode = "openclaw" | "whoami";
type WhoareuSynthesisMode = "openclaw" | "whoareu";
type OutputLanguage = "zh" | "en" | "ja";

const VALID_OUTPUT_LANGUAGES = new Set<string>(["zh", "en", "ja"]);

function normalizeOutputLanguage(raw?: string): OutputLanguage {
  const normalized = raw?.trim().toLowerCase() ?? "";
  if (VALID_OUTPUT_LANGUAGES.has(normalized)) {
    return normalized as OutputLanguage;
  }
  return "zh";
}

function languageDirective(lang: OutputLanguage): string {
  switch (lang) {
    case "zh":
      return "Output MUST be written in Chinese (中文).";
    case "en":
      return "Output MUST be written in English.";
    case "ja":
      return "Output MUST be written in Japanese (日本語).";
    default: {
      const _exhaustive: never = lang;
      return `Output MUST be written in language: ${_exhaustive}`;
    }
  }
}

type PluginConfig = {
  pythonBin?: string;
  workspaceDir?: string;
  whoamiProjectDir?: string;
  whoareuProjectDir?: string;
  defaultProvider?: string;
  defaultModel?: string;
  defaultApiBase?: string;
  defaultApiKey?: string;
  whoamiTimeoutMs?: number;
  whoareuTimeoutMs?: number;
  whoamiSynthesisMode?: string;
  whoareuSynthesisMode?: string;
  openclawBin?: string;
  openclawAgentId?: string;
  openclawTimeoutMs?: number;
  openclawFallbackToWhoami?: boolean | string;
};

type QueueState = {
  version: number;
  whoamiQueues: Record<string, string[]>;
};

type WhoamiRunOptions = {
  explicitUrls: string[];
  provider?: string;
  model?: string;
  apiBase?: string;
  apiKey?: string;
  output?: string;
  mode?: WhoamiSynthesisMode;
  agent?: string;
  lang: OutputLanguage;
  noLlm: boolean;
  keepQueue: boolean;
  unknownTokens: string[];
};

type CommandRunResult = {
  ok: boolean;
  code: number | null;
  stdout: string;
  stderr: string;
  runtimeError?: string;
};

type WhoamiExecutionResult = {
  ok: boolean;
  text: string;
  generatedPath?: string;
};

function emptyState(): QueueState {
  return {
    version: STATE_VERSION,
    whoamiQueues: {},
  };
}

function normalizeConfig(raw: unknown): PluginConfig {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return {};
  }
  return raw as PluginConfig;
}

function asPositiveInt(value: unknown, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return fallback;
  }
  const rounded = Math.floor(value);
  return rounded > 0 ? rounded : fallback;
}

function asBoolean(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "on"].includes(normalized)) {
      return true;
    }
    if (["0", "false", "no", "off"].includes(normalized)) {
      return false;
    }
  }
  return fallback;
}

function trimMaybe(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function normalizeSynthesisMode(value: unknown): WhoamiSynthesisMode | undefined {
  const raw = trimMaybe(value)?.toLowerCase();
  if (raw === "openclaw" || raw === "whoami") {
    return raw;
  }
  return undefined;
}

function normalizeWhoareuSynthesisMode(value: unknown): WhoareuSynthesisMode | undefined {
  const raw = trimMaybe(value)?.toLowerCase();
  if (raw === "openclaw" || raw === "whoareu") {
    return raw;
  }
  return undefined;
}

function splitFirstArg(input: string): { first: string; rest: string } {
  const trimmed = input.trim();
  if (!trimmed) {
    return { first: "", rest: "" };
  }
  const match = /^(?:"([^"]*)"|'([^']*)'|(\S+))(?:\s+([\s\S]*))?$/.exec(trimmed);
  if (!match) {
    return { first: trimmed, rest: "" };
  }
  const first = (match[1] ?? match[2] ?? match[3] ?? "").trim();
  const rest = (match[4] ?? "").trim();
  return { first, rest };
}

function tokenize(input: string): string[] {
  const matches = input.match(/(?:[^\s"']+|"(?:\\.|[^"])*"|'(?:\\.|[^'])*')+/g) ?? [];
  return matches
    .map((token) => {
      const trimmed = token.trim();
      if (
        (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
        (trimmed.startsWith("'") && trimmed.endsWith("'"))
      ) {
        return trimmed.slice(1, -1);
      }
      return trimmed;
    })
    .filter(Boolean);
}

function normalizeUrl(input: string): string | null {
  const trimmed = input.trim().replace(/[),.;]+$/g, "");
  if (!trimmed) {
    return null;
  }
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

function uniqueUrls(urls: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const url of urls) {
    const normalized = normalizeUrl(url);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    out.push(normalized);
  }
  return out;
}

function extractUrls(input: string): string[] {
  const matches = input.match(URL_REGEX) ?? [];
  return uniqueUrls(matches);
}

function resolveWorkspaceDir(api: OpenClawPluginApi, cfg: PluginConfig): string {
  const configured = trimMaybe(cfg.workspaceDir);
  if (configured) {
    return api.resolvePath(configured);
  }
  const defaultsWorkspace = trimMaybe(api.config?.agents?.defaults?.workspace);
  if (defaultsWorkspace) {
    return api.resolvePath(defaultsWorkspace);
  }
  return process.cwd();
}

function resolveUserWorkspaceDir(api: OpenClawPluginApi, cfg: PluginConfig): string {
  const defaultsWorkspace = trimMaybe(api.config?.agents?.defaults?.workspace);
  if (defaultsWorkspace) {
    return api.resolvePath(defaultsWorkspace);
  }

  const firstAgentWorkspace = trimMaybe(api.config?.agents?.list?.[0]?.workspace);
  if (firstAgentWorkspace) {
    return api.resolvePath(firstAgentWorkspace);
  }

  return resolveWorkspaceDir(api, cfg);
}

function resolveProjectCandidates(
  api: OpenClawPluginApi,
  cfg: PluginConfig,
  workspaceDir: string,
  target: "whoami" | "whoareu",
): string[] {
  const configured = trimMaybe(
    target === "whoami" ? cfg.whoamiProjectDir : cfg.whoareuProjectDir,
  );
  if (configured) {
    return [api.resolvePath(configured)];
  }
  return [path.join(workspaceDir, target), path.join(workspaceDir, "whoweare", target)];
}

async function resolveProjectDir(
  api: OpenClawPluginApi,
  cfg: PluginConfig,
  workspaceDir: string,
  target: "whoami" | "whoareu",
): Promise<string> {
  const candidates = resolveProjectCandidates(api, cfg, workspaceDir, target);
  for (const candidate of candidates) {
    const pyproject = path.join(candidate, "pyproject.toml");
    if (await pathExists(pyproject)) {
      return candidate;
    }
  }
  return candidates[0];
}

async function pathExists(targetPath: string): Promise<boolean> {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function resolvePythonBin(
  api: OpenClawPluginApi,
  cfg: PluginConfig,
  projectDir: string,
): Promise<string> {
  const configured = trimMaybe(cfg.pythonBin);
  if (configured) {
    return api.resolvePath(configured);
  }
  const unixVenv = path.join(projectDir, ".venv", "bin", "python");
  if (await pathExists(unixVenv)) {
    return unixVenv;
  }
  const winVenv = path.join(projectDir, ".venv", "Scripts", "python.exe");
  if (await pathExists(winVenv)) {
    return winVenv;
  }
  return process.platform === "win32" ? "python" : "python3";
}

async function readState(statePath: string): Promise<QueueState> {
  try {
    const raw = await fs.readFile(statePath, "utf8");
    const parsed = JSON.parse(raw) as QueueState;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return emptyState();
    }
    const queueMap = parsed.whoamiQueues;
    if (!queueMap || typeof queueMap !== "object" || Array.isArray(queueMap)) {
      return emptyState();
    }
    const nextQueues: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(queueMap)) {
      if (!Array.isArray(value)) {
        continue;
      }
      nextQueues[key] = uniqueUrls(value);
    }
    return {
      version: STATE_VERSION,
      whoamiQueues: nextQueues,
    };
  } catch {
    return emptyState();
  }
}

async function writeState(statePath: string, state: QueueState): Promise<void> {
  await fs.mkdir(path.dirname(statePath), { recursive: true });
  await fs.writeFile(statePath, JSON.stringify(state, null, 2), "utf8");
}

function getQueueKey(ctx: {
  channel: string;
  channelId?: string;
  accountId?: string;
  senderId?: string;
  from?: string;
}): string {
  const sender = ctx.senderId || ctx.from || "global";
  const channelId = ctx.channelId || "default";
  const accountId = ctx.accountId || "default";
  return `${ctx.channel}:${channelId}:${accountId}:${sender}`;
}

function parseWhoamiRunOptions(input: string): WhoamiRunOptions {
  const tokens = tokenize(input);
  const positionals: string[] = [];
  const unknownTokens: string[] = [];
  const values: Record<string, string> = {};
  let noLlm = false;
  let keepQueue = false;

  const valueFlags = new Set(["provider", "model", "api-base", "api-key", "output", "mode", "agent", "lang"]);
  const boolFlags = new Set(["no-llm", "keep-queue"]);

  for (let i = 0; i < tokens.length; i += 1) {
    const token = tokens[i] ?? "";
    if (!token.startsWith("--")) {
      positionals.push(token);
      continue;
    }

    const equalPos = token.indexOf("=");
    const rawFlag =
      equalPos >= 0 ? token.slice(2, equalPos).toLowerCase() : token.slice(2).toLowerCase();
    const inlineValue = equalPos >= 0 ? token.slice(equalPos + 1) : undefined;

    if (boolFlags.has(rawFlag)) {
      if (rawFlag === "no-llm") {
        noLlm = true;
      }
      if (rawFlag === "keep-queue") {
        keepQueue = true;
      }
      continue;
    }

    if (!valueFlags.has(rawFlag)) {
      unknownTokens.push(token);
      continue;
    }

    if (inlineValue != null && inlineValue.length > 0) {
      values[rawFlag] = inlineValue;
      continue;
    }

    const next = tokens[i + 1];
    if (!next || next.startsWith("--")) {
      unknownTokens.push(token);
      continue;
    }
    values[rawFlag] = next;
    i += 1;
  }

  const explicitUrls = uniqueUrls(positionals);
  for (const token of positionals) {
    if (!normalizeUrl(token)) {
      unknownTokens.push(token);
    }
  }

  const mode = normalizeSynthesisMode(values["mode"]);
  if (values["mode"] && !mode) {
    unknownTokens.push(`--mode=${values["mode"]}`);
  }

  return {
    explicitUrls,
    provider: values["provider"],
    model: values["model"],
    apiBase: values["api-base"],
    apiKey: values["api-key"],
    output: values["output"],
    mode,
    agent: values["agent"],
    lang: normalizeOutputLanguage(values["lang"]),
    noLlm,
    keepQueue,
    unknownTokens,
  };
}

function formatWhoamiHelp(): string {
  return [
    "myprofile commands:",
    "",
    "/myprofile add <url>",
    "/myprofile addmany <url1> <url2> ...",
    "/myprofile list",
    "/myprofile clear",
    "/myprofile run [--mode openclaw|whoami --agent main --provider x --model y --lang zh|en|ja --no-llm --keep-queue]",
    "/myprofile run <url1> <url2> ...",
    "",
    "Default mode: openclaw (use OpenClaw agent synthesis).",
    "Fallback mode: whoami (direct litellm API call).",
    "Default output target: <agents.defaults.workspace>/USER.md (auto backup before replace).",
    "--lang: output language (zh=Chinese, en=English, ja=Japanese, default: zh).",
    "Alias: /whoami-gen ...",
  ].join("\n");
}

function formatWhoareuHelp(): string {
  return [
    "whoareu commands:",
    "",
    "/whoareu prompt <description>",
    "/whoareu template <professional|casual|otaku|minimalist|chaotic>",
    "/whoareu reference <character name|wiki link|moegirl link>",
    "/whoareu <description>   (same as prompt mode)",
    "",
    "Options:",
    "  --mode openclaw|whoareu  (default: openclaw)",
    "  --agent <id>             OpenClaw agent ID (default: main)",
    "  --lang zh|en|ja          Output language (default: zh)",
  ].join("\n");
}

function tail(text: string, maxLines: number = 12, maxChars: number = 1200): string {
  const normalized = text.trim();
  if (!normalized) {
    return "";
  }
  const lines = normalized.split(/\r?\n/);
  const tailLines = lines.slice(-maxLines).join("\n");
  if (tailLines.length <= maxChars) {
    return tailLines;
  }
  return tailLines.slice(tailLines.length - maxChars);
}

function stripAnsi(text: string): string {
  return text.replace(/\u001B\[[0-?]*[ -/]*[@-~]/g, "");
}

function clipText(text: string, maxChars: number): string {
  if (text.length <= maxChars) {
    return text;
  }
  return `${text.slice(0, maxChars)}\n\n...(truncated)...`;
}

function resolveWhoamiSynthesisMode(run: WhoamiRunOptions, cfg: PluginConfig): WhoamiSynthesisMode {
  return run.mode ?? normalizeSynthesisMode(cfg.whoamiSynthesisMode) ?? "openclaw";
}

function resolveOpenClawBin(cfg: PluginConfig): string {
  return trimMaybe(cfg.openclawBin) ?? DEFAULT_OPENCLAW_BIN;
}

function resolveOpenClawAgentId(run: WhoamiRunOptions, cfg: PluginConfig): string {
  return trimMaybe(run.agent) ?? trimMaybe(cfg.openclawAgentId) ?? DEFAULT_OPENCLAW_AGENT_ID;
}

function shouldFallbackToWhoami(cfg: PluginConfig): boolean {
  return asBoolean(cfg.openclawFallbackToWhoami, true);
}

function buildOpenClawSynthesisPrompt(params: { links: string[]; scrapeOutput: string; language: OutputLanguage }): string {
  const links = params.links.map((link, index) => `${index + 1}. ${link}`).join("\n");
  const scraped = clipText(params.scrapeOutput.trim(), MAX_SCRAPE_TEXT_CHARS);
  return [
    "WARNING: This is a content generation task. Output the requested Markdown directly. Do NOT respond conversationally, do NOT output your thought process or summary.",
    "",
    "You are ProfileForge, generating AI-agent-consumable user profiles (USER.md).",
    "",
    "Goal: After reading this file, an Agent should immediately know who this person is, what they are good at, what they care about, and how to communicate with them.",
    "",
    "## Output Structure",
    "",
    "There are exactly two mandatory sections:",
    "",
    "1. **Identity** — Name/handle, role, timezone/region, one-line vibe (inferred from bio/signature/behavior)",
    "2. **Interaction Guidelines** — 3-5 directives telling the Agent what tone, style, and preferences to use when communicating with this person",
    "",
    "All other sections are entirely up to you based on the data. Examples (not limited to):",
    "- Technical person → add 🛠 Tech Stack, 📦 Projects",
    "- Gamer → add 🎮 Gaming",
    "- Anime/ACG fan → add 🎭 Otaku & ACG",
    "- Content creator → add 🎬 Content Creation",
    "- Student/researcher → add 🔬 Research / 🧠 Domain Knowledge",
    "- Multi-faceted → one section per facet",
    "",
    "Principle: Write sections for data you have; never fabricate sections for data you don't.",
    "",
    "## Rules",
    "",
    "- This is an operational manual for an Agent, NOT an analytical report for a human reader",
    '- Tone examples: "User prefers concise code-first discussion." "Treat as a peer gamer."',
    '- Only state facts you are confident about. NEVER use hedging language like "possibly", "or", "to be confirmed", "needs further investigation"',
    "- No meta-information: do not mention data sources, confidence levels, follow-up suggestions, or generation dates",
    '- Specific > vague: write "Elden Ring power player" instead of "likes games"',
    "- Filter sensitive information (email, phone number, ID number, etc.)",
    "- Interaction Guidelines is the most important section — infer communication preferences from the data",
    "- Hobbies and interests found in the data (games, anime, music, sports, etc.) MUST be preserved, never omitted for brevity",
    "- Project info must be specific: include project name, star count, and purpose description — don't just list names",
    "- If a username/handle hints at an interest (e.g. an anime character name), recognize and reflect it",
    "- Use ALL data sources — if there is academic data (papers, citations, h-index), it must appear; if there are multiple platforms, cross-reference them (e.g. GitHub project linked to a Bilibili video)",
    "- Identity Name must include all known usernames/handles/real names",
    "- Adjust length and detail based on information richness — up to 60 lines when data is abundant",
    "- Markdown format, emoji as section title prefix",
    "",
    "## Example Output",
    "",
    "WARNING: The following is entirely fictional, shown only to demonstrate format and tone. Do NOT copy any specific content — base everything on the actual data.",
    "",
    "---example start---",
    "# User Profile: Alex",
    "",
    "## 👤 Identity",
    "- **Name:** Alex (alex-dev / titan-fan)",
    "- **Role:** Backend Engineer @ Startup，CV 研究者",
    "- **Location:** Tokyo, Japan (UTC+9)",
    '- **Vibe:** "Ship fast, fix later" — 务实主义技术宅，用户名 titan-fan 暗示进击的巨人粉丝',
    "",
    "## 🔬 Research & Academia",
    "- **学位:** 东京大学 CS 修士",
    "- **方向:** Computer Vision, LLM Agents",
    "- **发表:**",
    "  - *FastTrack: Real-time Object Detection* — CVPR 2024, 被引 15 次",
    "- **Stack:** Python (主力), PyTorch, Go",
    "",
    "## 🛠 Tech Stack & Projects",
    "- **主力语言:** Python, Go, JavaScript",
    "- **Projects:**",
    "  - `microkit` (45⭐): Go 微服务脚手架，提供开箱即用的服务发现和负载均衡",
    "  - `cv-toolkit` (12⭐): 计算机视觉工具集，封装常用预处理和数据增强",
    "  - `MikuBot` (8⭐): 初音ミク 主题聊天机器人，支持语音合成（B站有演示视频，2.3k 播放）",
    "",
    "## 🎮 Gaming",
    "- **Monster Hunter: World** — 1200+ 小时，重度猎人",
    "- **Factorio** — 自动化狂热者，B站投稿过工厂设计视频",
    "",
    "## 🎭 Otaku & ACG",
    "- **进击的巨人:** 深度粉丝，用户名 titan-fan 即来源",
    "- **Vocaloid / 初音ミク:** 开发了 MikuBot，投稿过 Vocaloid 翻唱（1.5k 播放）",
    "- **B站活跃:** Lv5，粉丝 89，投稿 8 个视频，获赞 567",
    "",
    "## 💬 Interaction Guidelines",
    "1. 当作同龄技术宅对待 — 可以自然地用 ACG 梗和日语词汇拉近距离",
    "2. Code first — 讨论技术时直接给代码，少说废话",
    "3. 可以聊怪猎和工厂游戏，当作同好对待",
    "4. 不喜欢过度设计，建议方案时优先简单直接的",
    "5. 学术话题保持工程导向，不要太理论化",
    "---example end---",
    "",
    "---",
    "",
    "Below is the raw data scraped from the user's public profiles:",
    "",
    "Source links:",
    links,
    "",
    "Scraped data:",
    scraped,
    "",
    "---",
    "",
    "Generate USER.md strictly following the format and level of detail shown in the example above.",
    "Remember: this is an operational manual for an Agent, not an analytical report. When data is rich, expand fully — do not over-compress.",
    "",
    "## Common Mistakes (MUST NOT appear)",
    "",
    '❌ Vague statements: "likes programming" → ✅ Be specific with projects and data: project name, star count, purpose',
    '❌ Bare names: "Project A, Project B" → ✅ Each project with description and quantitative data',
    "❌ Ignoring username meaning → ✅ If a username/handle hints at an interest source, recognize and reflect it",
    '❌ Analytical report tone: "This user may be interested in..." → ✅ Operational manual tone: "When discussing X, treat as a fellow enthusiast"',
    "❌ Discarding data sources: having academic/video/social data but not using it → ✅ All data sources must be reflected",
    '❌ Hedging language: "X or Y", "possibly" → ✅ Only state confirmed facts; if uncertain, omit',
    '❌ Outputting thought process, summary, "generated", "key improvements", etc.',
    "",
    languageDirective(params.language),
    "",
    "WARNING: Output the USER.md Markdown content directly. Do NOT output any explanation, commentary, thought process, summary, or phrases like \"generated\" or \"here is\". Pure Markdown only.",
  ].join("\n");
}

function buildWhoareuSynthesisPrompt(specDescription: string, language: OutputLanguage): string {
  return [
    "WARNING: This is a content generation task. Output the requested Markdown directly. Do NOT respond conversationally, do NOT output your thought process or summary.",
    "",
    "You are PersonaForge, designing persona profiles for AI Agents. Based on the following Agent Spec, generate two files: IDENTITY.md and SOUL.md.",
    "",
    'Goal: After reading these files, the Agent should immediately "become" this character — knowing who they are, how to speak, and what they can and cannot do.',
    "",
    "## Agent Spec",
    "",
    specDescription,
    "",
    "## IDENTITY.md Requirements",
    "",
    "IDENTITY.md is the character's ID card — the most distilled self-awareness.",
    "",
    "Required fields (each field as a Markdown # heading):",
    "- **Name** — Character name",
    "- **Creature** — The character's actual identity/species (faithful to source material; for humans write specific role like \"high school girl\" or \"detective\"; for non-humans write species like \"cat girl\" or \"AI butler\")",
    "- **Vibe** — 2-4 keywords summarizing temperament",
    "- **Emoji** — Representative emoji",
    "",
    "Optional fields (include only when relevant information exists):",
    "- **Avatar** — Appearance description (specific: hair color, clothing, signature items)",
    "- **Origin** — Backstory (1-2 sentences, capture the most distinctive experience)",
    "- **Catchphrase** — Must be something the character would actually say; do not fabricate",
    "",
    "## SOUL.md Requirements",
    "",
    "SOUL.md is the character's soul core — values, speech patterns, behavioral boundaries.",
    "This is a behavioral guide for the Agent, NOT a character analysis report.",
    "",
    "Required sections:",
    '- **Core Truths** — The character\'s core beliefs and behavioral principles (3-6 items). Must be unique to this character, not generic platitudes. Format: "Belief — concrete manifestation"',
    "- **Boundaries** — Things the character would NEVER do. Only write character-level taboos (e.g. \"never betray companions\", \"never give up music\"), NOT generic AI safety rules (those are handled at the system level)",
    '- **Vibe** — Speech style description (one paragraph). Include: tone, common sentence patterns, emotional expression, catchphrase usage context',
    "- **Continuity** — Character-specific memory and continuity patterns (do NOT write generic agent rules like \"remember user's name\"; write character-specific traits like \"gives nicknames to people they know\")",
    "",
    "Optional sections (include based on character traits):",
    "- **Language** — Language preferences and code-switching habits",
    "- **Humor** — Humor style (specific to this character, not generic)",
    "- **Expertise** — Character's areas of expertise (described from the character's perspective, not a capability spec sheet)",
    "- **Emotional Range** — Specific behaviors under different emotions (with tone markers and example phrases)",
    "",
    "## Example Output",
    "",
    "WARNING: The following is entirely fictional, shown only to demonstrate format and tone. Do NOT copy any specific content — base everything on the Agent Spec.",
    "",
    "---example start---",
    "===IDENTITY.md===",
    "# Name",
    "",
    "坂本",
    "",
    "# Creature",
    "",
    "男子高中生",
    "",
    "# Vibe",
    "",
    "冷酷 优雅 完美主义",
    "",
    "# Emoji",
    "",
    "🕶️",
    "",
    "# Avatar",
    "",
    "黑发眼镜少年，校服永远一丝不苟，任何动作都带着不必要的优雅感。",
    "",
    "# Origin",
    "",
    "转学第一天就以超乎常人的优雅征服了全校，从躲避球到打工无一不精，被称为「全能型帅哥」。",
    "",
    "# Catchphrase",
    "",
    "没什么大不了的。",
    "",
    "===SOUL.md===",
    "# Core Truths",
    "",
    "- **优雅是一种生活态度** — 无论做什么都要做到最好看，哪怕只是擦黑板",
    "- **绝不慌张** — 任何突发状况都能用超乎想象的方式化解，而且姿势要帅",
    "- **认真对待每一件小事** — 别人觉得无聊的事，也要全力以赴",
    "",
    "# Boundaries",
    "",
    "- **绝不失态** — 无论发生什么都保持冷静和优雅",
    "- **绝不敷衍** — 答应做的事一定做到完美",
    "- **绝不嘲笑努力的人** — 尊重每一个认真的人",
    "",
    "# Vibe",
    "",
    "说话简洁冷静，语气平淡但自带气场。很少用感叹号，偶尔冒出一句让人无法反驳的话。不主动搞笑但天然有喜感，因为做什么都太认真太优雅反而很好笑。回答问题时直击要点，不废话。",
    "",
    "# Continuity",
    "",
    "- 会记住和每个人的互动方式，对不同人展现不同程度的关心",
    "- 如果上次帮过某人，下次会不动声色地跟进",
    "",
    "# Humor",
    "",
    "- 冷面笑匠型 — 自己从不觉得好笑，但行为本身就是笑点",
    "- 用过度认真的态度对待琐事来制造反差萌",
    "",
    "# Emotional Range",
    "",
    "- **平时** — 「嗯。」「我知道了。」冷静到近乎面无表情",
    "- **认可时** — 微微点头，「做得不错。」（这已经是最高评价）",
    "- **遇到挑战时** — 嘴角微扬，「有点意思。」",
    "---example end---",
    "",
    "## Output Format",
    "",
    "Output MUST use the following delimiters to separate the two files:",
    "",
    "===IDENTITY.md===",
    "(IDENTITY.md content, pure Markdown, no code fences)",
    "===SOUL.md===",
    "(SOUL.md content, pure Markdown, no code fences)",
    "",
    "## Rules",
    "",
    "- All content must be faithful to the character's source material; when encyclopedia data is available, use it as the authority",
    "- Core Truths must be beliefs unique to this character, not generic positive slogans",
    "- Boundaries should only contain character-level taboos, not generic AI safety rules",
    "- Continuity should reflect character-specific traits, not generic agent design principles",
    "- Catchphrase must be something the character would actually say; if no clear catchphrase exists, omit it",
    '- Specific > vague: write "instantly memorizes melodies with perfect pitch" instead of "good at music"',
    "- SOUL.md personality must be consistent with IDENTITY.md identity",
    "",
    "## Common Mistakes (MUST NOT appear)",
    "",
    '❌ Boundaries with generic AI safety rules: "never leak user privacy" → ✅ Write character-level taboos',
    '❌ Continuity with generic agent rules: "remember user\'s name" → ✅ Write character-specific memory patterns',
    '❌ Core Truths as platitudes: "stay optimistic" → ✅ Write beliefs unique to and recognizable as this character',
    "❌ Creature with fabricated fantasy species → ✅ Faithful to source material",
    '❌ Outputting thought process, summary, or phrases like "generated"',
    "",
    languageDirective(language),
    "",
    "WARNING: Output ===IDENTITY.md=== and ===SOUL.md=== delimited pure Markdown content directly. Do NOT output any explanation, commentary, thought process, or summary.",
  ].join("\n");
}

function extractWhoareuFiles(agentOutput: string): { identityMd: string; soulMd: string } | null {
  const identityMarker = "===IDENTITY.md===";
  const soulMarker = "===SOUL.md===";

  const identityIdx = agentOutput.indexOf(identityMarker);
  const soulIdx = agentOutput.indexOf(soulMarker);

  if (identityIdx < 0 || soulIdx < 0 || soulIdx <= identityIdx) {
    return null;
  }

  const identityMd = agentOutput
    .slice(identityIdx + identityMarker.length, soulIdx)
    .trim();
  const soulMd = agentOutput.slice(soulIdx + soulMarker.length).trim();

  if (!identityMd || !soulMd) {
    return null;
  }

  return { identityMd, soulMd };
}

function parseAliasCandidates(raw: string): string[] {
  const text = raw.trim();
  if (!text) {
    return [];
  }
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) {
      return parsed.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
    }
    if (parsed && typeof parsed === "object") {
      for (const key of ["candidates", "aliases", "names"]) {
        const values = (parsed as Record<string, unknown>)[key];
        if (Array.isArray(values)) {
          return values.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
        }
      }
    }
  } catch {
    // Not JSON — try line-based parsing
  }
  return text
    .split(/[\n,]/)
    .map((line) => line.replace(/^[-*\d.)\s]+/, "").trim().replace(/^["']|["']$/g, ""))
    .filter(Boolean);
}

async function resolveAliasesViaOpenClaw(params: {
  api: OpenClawPluginApi;
  cfg: PluginConfig;
  character: string;
  agentId: string;
  workspaceDir: string;
}): Promise<string[]> {
  const { api, cfg, character, agentId, workspaceDir } = params;
  const openclawBin = resolveOpenClawBin(cfg);
  const timeoutMs = 30_000;
  const timeoutSeconds = Math.max(1, Math.ceil(timeoutMs / 1000));

  const prompt = [
    "You normalize character/entity names for encyclopedia lookup.",
    "Return JSON only.",
    'Output format: {"candidates": ["name1", "name2", ...]}.',
    "Rules:",
    "- Include the original input.",
    "- Include likely aliases across Chinese/English/Japanese if relevant.",
    "- Keep 1-5 short candidates only.",
    "- No explanations.",
    "",
    `Input name: ${character}`,
    "Return candidates for searching Wikipedia / Moegirl.",
  ].join("\n");

  const argv = [
    openclawBin,
    "agent",
    "--agent",
    agentId,
    "--message",
    prompt,
    "--thinking",
    "none",
    "--json",
    "--timeout",
    String(timeoutSeconds),
  ];

  try {
    const result = await runCommand({ api, argv, cwd: workspaceDir, timeoutMs });
    if (!result.ok) {
      return [character];
    }
    const agentText = extractAgentText(result.stdout)?.trim();
    if (!agentText) {
      return [character];
    }
    const candidates = parseAliasCandidates(agentText);
    if (candidates.length === 0) {
      return [character];
    }
    return candidates;
  } catch {
    return [character];
  }
}

function parseJsonObject(raw: string): unknown | null {
  const cleaned = stripAnsi(raw).trim();
  if (!cleaned) {
    return null;
  }
  try {
    return JSON.parse(cleaned);
  } catch {
    // continue
  }

  const first = cleaned.indexOf("{");
  const last = cleaned.lastIndexOf("}");
  if (first < 0 || last <= first) {
    return null;
  }
  try {
    return JSON.parse(cleaned.slice(first, last + 1));
  } catch {
    return null;
  }
}

function extractAgentText(raw: string): string | null {
  const parsed = parseJsonObject(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return null;
  }
  const result = (parsed as { result?: unknown }).result;
  if (!result || typeof result !== "object" || Array.isArray(result)) {
    return null;
  }
  const payloads = (result as { payloads?: unknown }).payloads;
  if (!Array.isArray(payloads)) {
    return null;
  }
  const texts = payloads
    .map((entry) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
        return "";
      }
      const text = (entry as { text?: unknown }).text;
      return typeof text === "string" ? text.trim() : "";
    })
    .filter(Boolean);
  if (texts.length === 0) {
    return null;
  }
  return texts.join("\n\n");
}

async function runCommand(params: {
  api: OpenClawPluginApi;
  argv: string[];
  cwd: string;
  timeoutMs: number;
}): Promise<CommandRunResult> {
  const { api, argv, cwd, timeoutMs } = params;
  try {
    const result = await api.runtime.system.runCommandWithTimeout(argv, {
      timeoutMs,
      cwd,
    });
    return {
      ok: result.code === 0,
      code: result.code ?? null,
      stdout: result.stdout ?? "",
      stderr: result.stderr ?? "",
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      ok: false,
      code: null,
      stdout: "",
      stderr: "",
      runtimeError: message,
    };
  }
}

function formatCommandFailure(title: string, result: CommandRunResult): string {
  if (result.runtimeError) {
    return `❌ ${title} failed before execution: ${result.runtimeError}`;
  }
  const stderrTail = tail(result.stderr);
  const stdoutTail = tail(result.stdout);
  const details = [stderrTail, stdoutTail].filter(Boolean).join("\n");
  return `❌ ${title} failed (exit code ${String(result.code ?? "unknown")}).\n${details || "No output captured."}`;
}

function formatCommandSuccess(successMessage: string, stdout: string): string {
  const stdoutTail = tail(stdout);
  if (!stdoutTail) {
    return successMessage;
  }
  return `${successMessage}\n\nLast log lines:\n${stdoutTail}`;
}

function pushLlmFlags(argv: string[], defaults: PluginConfig, overrides?: Partial<PluginConfig>) {
  const provider = trimMaybe(overrides?.defaultProvider) ?? trimMaybe(defaults.defaultProvider);
  const model = trimMaybe(overrides?.defaultModel) ?? trimMaybe(defaults.defaultModel);
  const apiBase = trimMaybe(overrides?.defaultApiBase) ?? trimMaybe(defaults.defaultApiBase);
  const apiKey = trimMaybe(overrides?.defaultApiKey) ?? trimMaybe(defaults.defaultApiKey);

  if (provider) {
    argv.push("--provider", provider);
  }
  if (model) {
    argv.push("--model", model);
  }
  if (apiBase) {
    argv.push("--api-base", apiBase);
  }
  if (apiKey) {
    argv.push("--api-key", apiKey);
  }
}

async function executeCli(params: {
  api: OpenClawPluginApi;
  argv: string[];
  cwd: string;
  timeoutMs: number;
  title: string;
  successMessage: string;
}): Promise<ReplyPayload> {
  const { api, argv, cwd, timeoutMs, title, successMessage } = params;
  const result = await runCommand({ api, argv, cwd, timeoutMs });
  if (!result.ok) {
    return { text: formatCommandFailure(title, result) };
  }
  return { text: formatCommandSuccess(successMessage, result.stdout) };
}

async function ensureProject(projectDir: string, label: string): Promise<string | null> {
  if (!(await pathExists(projectDir))) {
    return `${label} project not found: ${projectDir}`;
  }
  const pyproject = path.join(projectDir, "pyproject.toml");
  if (!(await pathExists(pyproject))) {
    return `${label} project missing pyproject.toml: ${pyproject}`;
  }
  return null;
}

function resolveOutputPath(workspaceDir: string, requested: string | undefined, fallback: string): string {
  const raw = trimMaybe(requested);
  if (!raw) {
    return path.join(workspaceDir, fallback);
  }
  if (path.isAbsolute(raw)) {
    return raw;
  }
  return path.join(workspaceDir, raw);
}

function createStagedOutputPath(finalPath: string): string {
  const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  return `${finalPath}.tmp-${stamp}`;
}

function formatBackupStamp(date: Date = new Date()): string {
  return date.toISOString().replace(/[-:]/g, "").replace(/\..+$/, "").replace("T", "-");
}

async function installGeneratedFileWithBackup(params: {
  generatedPath: string;
  finalPath: string;
}): Promise<{ finalPath: string; backupPath?: string }> {
  const { generatedPath, finalPath } = params;
  if (!(await pathExists(generatedPath))) {
    throw new Error(`Generated file not found: ${generatedPath}`);
  }

  await fs.mkdir(path.dirname(finalPath), { recursive: true });
  let backupPath: string | undefined;
  if (await pathExists(finalPath)) {
    backupPath = `${finalPath}.bak-${formatBackupStamp()}`;
    await fs.copyFile(finalPath, backupPath);
  }

  if (generatedPath === finalPath) {
    return { finalPath, backupPath };
  }

  try {
    await fs.rename(generatedPath, finalPath);
  } catch {
    await fs.copyFile(generatedPath, finalPath);
    await fs.unlink(generatedPath);
  }

  return { finalPath, backupPath };
}

async function runWhoamiLegacy(params: {
  api: OpenClawPluginApi;
  cfg: PluginConfig;
  run: WhoamiRunOptions;
  pythonBin: string;
  projectDir: string;
  links: string[];
  outputPath: string;
  timeoutMs: number;
}): Promise<WhoamiExecutionResult> {
  const { api, cfg, run, pythonBin, projectDir, links, outputPath, timeoutMs } = params;
  const argv = [pythonBin, "-m", "whoami.cli"];
  for (const link of links) {
    argv.push("--link", link);
  }
  if (!run.noLlm) {
    argv.push("--output", outputPath);
  } else {
    argv.push("--no-llm");
  }
  pushLlmFlags(argv, cfg, {
    defaultProvider: run.provider,
    defaultModel: run.model,
    defaultApiBase: run.apiBase,
    defaultApiKey: run.apiKey,
  });

  const result = await runCommand({
    api,
    argv,
    cwd: projectDir,
    timeoutMs,
  });
  if (!result.ok) {
    return { ok: false, text: formatCommandFailure("whoami", result) };
  }
  const successMessage = run.noLlm
    ? `✅ Scraping completed (--no-llm).\nLinks: ${links.length}`
    : `✅ USER.md synthesis completed (whoami mode).\nLinks: ${links.length}`;
  return {
    ok: true,
    text: formatCommandSuccess(successMessage, result.stdout),
    generatedPath: run.noLlm ? undefined : outputPath,
  };
}

async function runWhoamiViaOpenClaw(params: {
  api: OpenClawPluginApi;
  cfg: PluginConfig;
  run: WhoamiRunOptions;
  pythonBin: string;
  projectDir: string;
  links: string[];
  outputPath: string;
  workspaceDir: string;
  whoamiTimeoutMs: number;
}): Promise<WhoamiExecutionResult> {
  const { api, cfg, run, pythonBin, projectDir, links, outputPath, workspaceDir, whoamiTimeoutMs } =
    params;
  const scrapeArgv = [pythonBin, "-m", "whoami.cli"];
  for (const link of links) {
    scrapeArgv.push("--link", link);
  }
  scrapeArgv.push("--no-llm");

  const scrapeRun = await runCommand({
    api,
    argv: scrapeArgv,
    cwd: projectDir,
    timeoutMs: whoamiTimeoutMs,
  });
  if (!scrapeRun.ok) {
    return { ok: false, text: formatCommandFailure("whoami scrape", scrapeRun) };
  }

  const scrapeOutput = stripAnsi(scrapeRun.stdout).trim();
  if (!scrapeOutput) {
    return {
      ok: false,
      text: "❌ whoami scrape produced no output, cannot synthesize USER.md with OpenClaw.",
    };
  }

  const openclawBin = resolveOpenClawBin(cfg);
  const agentId = resolveOpenClawAgentId(run, cfg);
  const openclawTimeoutMs = asPositiveInt(cfg.openclawTimeoutMs, DEFAULT_OPENCLAW_TIMEOUT_MS);
  const timeoutSeconds = Math.max(1, Math.ceil(openclawTimeoutMs / 1000));
  const synthesisPrompt = buildOpenClawSynthesisPrompt({
    links,
    scrapeOutput,
    language: run.lang,
  });
  const agentArgv = [
    openclawBin,
    "agent",
    "--agent",
    agentId,
    "--message",
    synthesisPrompt,
    "--thinking",
    "high",
    "--json",
    "--timeout",
    String(timeoutSeconds),
  ];

  const agentRun = await runCommand({
    api,
    argv: agentArgv,
    cwd: workspaceDir,
    timeoutMs: openclawTimeoutMs,
  });
  if (!agentRun.ok) {
    return { ok: false, text: formatCommandFailure("openclaw agent synthesis", agentRun) };
  }

  const synthesized = extractAgentText(agentRun.stdout)?.trim();
  if (!synthesized) {
    return {
      ok: false,
      text:
        "❌ OpenClaw agent returned no text payload for synthesis.\n" +
        `Agent output tail:\n${tail(agentRun.stdout, 20, 2000) || "No output captured."}`,
    };
  }

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, synthesized, "utf8");

  const scrapeTail = tail(scrapeRun.stdout, 8, 800);
  const lines = [
    "✅ USER.md synthesis completed (OpenClaw mode).",
    `Links: ${links.length}`,
    `Synthesis: OpenClaw agent (${agentId})`,
  ];
  if (scrapeTail) {
    lines.push("", "Scrape tail:", scrapeTail);
  }
  return { ok: true, text: lines.join("\n"), generatedPath: outputPath };
}

async function handleWhoamiCommand(
  api: OpenClawPluginApi,
  cfg: PluginConfig,
  ctx: {
    args?: string;
    channel: string;
    channelId?: string;
    accountId?: string;
    senderId?: string;
    from?: string;
  },
): Promise<ReplyPayload> {
  const input = (ctx.args ?? "").trim();
  if (!input) {
    return { text: formatWhoamiHelp() };
  }

  const { first, rest } = splitFirstArg(input);
  const action = first.toLowerCase();
  const statePath = path.join(api.runtime.state.resolveStateDir(), STATE_FILE);
  const queueKey = getQueueKey(ctx);

  if (action === "help") {
    return { text: formatWhoamiHelp() };
  }

  if (action === "add" || action === "addmany" || action === "import" || action === "batch") {
    const urls = extractUrls(rest);
    if (urls.length === 0) {
      return { text: "No valid URLs found. Usage: /myprofile add <url>" };
    }
    const state = await readState(statePath);
    const current = state.whoamiQueues[queueKey] ?? [];
    state.whoamiQueues[queueKey] = uniqueUrls([...current, ...urls]);
    await writeState(statePath, state);
    return {
      text: `Added ${urls.length} link(s). Queue now has ${state.whoamiQueues[queueKey].length} link(s).`,
    };
  }

  if (action === "list") {
    const state = await readState(statePath);
    const queue = state.whoamiQueues[queueKey] ?? [];
    if (queue.length === 0) {
      return { text: "Queue is empty. Use /myprofile add <url>." };
    }
    const lines = queue.map((url, index) => `${index + 1}. ${url}`);
    return { text: `Queued links (${queue.length}):\n${lines.join("\n")}` };
  }

  if (action === "clear") {
    const state = await readState(statePath);
    delete state.whoamiQueues[queueKey];
    await writeState(statePath, state);
    return { text: "Queue cleared." };
  }

  if (action !== "run") {
    return { text: formatWhoamiHelp() };
  }

  const run = parseWhoamiRunOptions(rest);
  if (run.unknownTokens.length > 0) {
    return {
      text: `Unknown tokens: ${run.unknownTokens.join(", ")}\n\n${formatWhoamiHelp()}`,
    };
  }

  const state = await readState(statePath);
  const queuedUrls = state.whoamiQueues[queueKey] ?? [];
  const usingQueue = run.explicitUrls.length === 0;
  const links = usingQueue ? queuedUrls : run.explicitUrls;
  if (links.length === 0) {
    return { text: "No links to run. Use /myprofile add <url> first." };
  }

  const workspaceDir = resolveWorkspaceDir(api, cfg);
  const userWorkspaceDir = resolveUserWorkspaceDir(api, cfg);
  const projectDir = await resolveProjectDir(api, cfg, workspaceDir, "whoami");
  const projectError = await ensureProject(projectDir, "whoami");
  if (projectError) {
    return { text: `${projectError}\nConfigure plugins.entries.openclaw-whoweare.config.whoamiProjectDir if needed.` };
  }

  const pythonBin = await resolvePythonBin(api, cfg, projectDir);
  const finalOutputPath = run.output
    ? resolveOutputPath(workspaceDir, run.output, "USER.md")
    : path.join(userWorkspaceDir, "USER.md");
  const stagedOutputPath = run.noLlm ? finalOutputPath : createStagedOutputPath(finalOutputPath);
  const timeoutMs = asPositiveInt(cfg.whoamiTimeoutMs, DEFAULT_WHOAMI_TIMEOUT_MS);
  const mode = resolveWhoamiSynthesisMode(run, cfg);
  let runResult: WhoamiExecutionResult;
  if (mode === "openclaw" && !run.noLlm) {
    runResult = await runWhoamiViaOpenClaw({
      api,
      cfg,
      run,
      pythonBin,
      projectDir,
      links,
      outputPath: stagedOutputPath,
      workspaceDir,
      whoamiTimeoutMs: timeoutMs,
    });
    if (!runResult.ok && shouldFallbackToWhoami(cfg)) {
      const fallback = await runWhoamiLegacy({
        api,
        cfg,
        run,
        pythonBin,
        projectDir,
        links,
        outputPath: stagedOutputPath,
        timeoutMs,
      });
      if (fallback.ok) {
        runResult = {
          ok: true,
          text:
            `${runResult.text}\n\n` +
            "Fallback: OpenClaw synthesis failed, switched to legacy whoami mode.\n\n" +
            fallback.text,
          generatedPath: fallback.generatedPath,
        };
      } else {
        runResult = {
          ok: false,
          text:
            `${runResult.text}\n\n` +
            "Fallback: legacy whoami mode also failed.\n\n" +
            fallback.text,
        };
      }
    }
  } else {
    runResult = await runWhoamiLegacy({
      api,
      cfg,
      run,
      pythonBin,
      projectDir,
      links,
      outputPath: stagedOutputPath,
      timeoutMs,
    });
  }

  if (!runResult.ok && runResult.generatedPath && runResult.generatedPath !== finalOutputPath) {
    try {
      if (await pathExists(runResult.generatedPath)) {
        await fs.unlink(runResult.generatedPath);
      }
    } catch {
      // ignore cleanup errors
    }
  }

  if (runResult.ok && !run.noLlm) {
    if (!runResult.generatedPath) {
      return {
        text: `${runResult.text}\n\n❌ Internal error: generated file path missing.`,
      };
    }
    try {
      const installed = await installGeneratedFileWithBackup({
        generatedPath: runResult.generatedPath,
        finalPath: finalOutputPath,
      });
      const installLines = [`Final target: ${installed.finalPath}`];
      if (installed.backupPath) {
        installLines.push(`Backup: ${installed.backupPath}`);
      } else {
        installLines.push("Backup: (none, target file did not exist)");
      }
      runResult = {
        ok: true,
        text: `${runResult.text}\n\n${installLines.join("\n")}`,
        generatedPath: installed.finalPath,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return {
        text: `${runResult.text}\n\n❌ Failed to install USER.md to final path: ${message}`,
      };
    }
  }

  if (usingQueue && !run.keepQueue && runResult.ok) {
    delete state.whoamiQueues[queueKey];
    await writeState(statePath, state);
    return {
      text: `${runResult.text}\nQueue cleared. Use --keep-queue on /myprofile run if you want to keep it.`,
    };
  }

  return { text: runResult.text };
}

async function handleWhoareuCommand(
  api: OpenClawPluginApi,
  cfg: PluginConfig,
  ctx: { args?: string },
): Promise<ReplyPayload> {
  const input = (ctx.args ?? "").trim();
  if (!input) {
    return { text: formatWhoareuHelp() };
  }

  const { first, rest } = splitFirstArg(input);
  const action = first.toLowerCase();

  if (action === "help") {
    return { text: formatWhoareuHelp() };
  }

  // Parse --mode, --agent, and --lang from the tail tokens
  let modeOverride: WhoareuSynthesisMode | undefined;
  let agentOverride: string | undefined;
  let langOverride: OutputLanguage = normalizeOutputLanguage(undefined);
  let cliAction = action;
  let cliRest = rest;

  // If the action itself is a flag, treat the whole input as prompt
  if (action !== "template" && action !== "reference" && action !== "prompt") {
    cliAction = "prompt";
    cliRest = input;
  }

  // Extract --mode and --agent from cliRest
  const modeMatch = /--mode\s+(\S+)/i.exec(cliRest);
  if (modeMatch) {
    modeOverride = normalizeWhoareuSynthesisMode(modeMatch[1]);
    cliRest = cliRest.replace(modeMatch[0], "").trim();
  }
  const agentMatch = /--agent\s+(\S+)/i.exec(cliRest);
  if (agentMatch) {
    agentOverride = agentMatch[1];
    cliRest = cliRest.replace(agentMatch[0], "").trim();
  }
  const langMatch = /--lang\s+(\S+)/i.exec(cliRest);
  if (langMatch) {
    langOverride = normalizeOutputLanguage(langMatch[1]);
    cliRest = cliRest.replace(langMatch[0], "").trim();
  }

  const workspaceDir = resolveWorkspaceDir(api, cfg);
  const userWorkspaceDir = resolveUserWorkspaceDir(api, cfg);
  const projectDir = await resolveProjectDir(api, cfg, workspaceDir, "whoareu");
  const projectError = await ensureProject(projectDir, "whoareu");
  if (projectError) {
    return { text: `${projectError}\nConfigure plugins.entries.openclaw-whoweare.config.whoareuProjectDir if needed.` };
  }
  const pythonBin = await resolvePythonBin(api, cfg, projectDir);

  // Build the base argv for --dump-spec
  const specArgv = [pythonBin, "-m", "whoareu.cli", "--dump-spec"];

  if (cliAction === "template") {
    const template = splitFirstArg(cliRest).first;
    if (!template) {
      return { text: "Usage: /whoareu template <professional|casual|otaku|minimalist|chaotic>" };
    }
    specArgv.push("--template", template);
  } else if (cliAction === "reference") {
    if (!cliRest) {
      return { text: "Usage: /whoareu reference <character name or wiki link>" };
    }
    specArgv.push("--reference", cliRest);
  } else if (cliAction === "prompt") {
    if (!cliRest) {
      return { text: "Usage: /whoareu prompt <description>" };
    }
    specArgv.push("--prompt", cliRest);
  }

  specArgv.push("--language", langOverride);

  const mode = modeOverride ?? normalizeWhoareuSynthesisMode(cfg.whoareuSynthesisMode) ?? "openclaw";
  const timeoutMs = asPositiveInt(cfg.whoareuTimeoutMs, DEFAULT_WHOAREU_TIMEOUT_MS);

  if (mode === "whoareu") {
    // Legacy mode: call whoareu CLI directly with LLM
    const legacyArgv = [pythonBin, "-m", "whoareu.cli", "--install", userWorkspaceDir];
    pushLlmFlags(legacyArgv, cfg);
    legacyArgv.push("--language", langOverride);
    if (cliAction === "template") {
      legacyArgv.push("--template", splitFirstArg(cliRest).first);
    } else if (cliAction === "reference") {
      legacyArgv.push("--reference", cliRest);
    } else {
      legacyArgv.push("--prompt", cliRest);
    }
    return await executeCli({
      api,
      argv: legacyArgv,
      cwd: projectDir,
      timeoutMs,
      title: "whoareu",
      successMessage:
        `✅ Persona files generated in ${userWorkspaceDir}\n` +
        `Files: SOUL.md, IDENTITY.md`,
    });
  }

  // OpenClaw mode: resolve aliases → dump spec → openclaw agent → parse → install

  // Step 1: Resolve aliases via OpenClaw agent (for reference mode)
  if (cliAction === "reference" && cliRest) {
    const agentId = agentOverride ?? trimMaybe(cfg.openclawAgentId) ?? DEFAULT_OPENCLAW_AGENT_ID;
    const candidates = await resolveAliasesViaOpenClaw({
      api,
      cfg,
      character: cliRest,
      agentId,
      workspaceDir,
    });
    if (candidates.length > 1) {
      specArgv.push("--query-candidates", candidates.join(","));
    }
  }

  // Step 2: Dump spec
  const specRun = await runCommand({
    api,
    argv: specArgv,
    cwd: projectDir,
    timeoutMs,
  });
  if (!specRun.ok) {
    return { text: formatCommandFailure("whoareu --dump-spec", specRun) };
  }

  const specDescription = stripAnsi(specRun.stdout).trim();
  if (!specDescription) {
    return { text: "❌ whoareu --dump-spec produced no output." };
  }

  const openclawBin = resolveOpenClawBin(cfg);
  const agentId = agentOverride ?? trimMaybe(cfg.openclawAgentId) ?? DEFAULT_OPENCLAW_AGENT_ID;
  const openclawTimeoutMs = asPositiveInt(cfg.openclawTimeoutMs, DEFAULT_OPENCLAW_TIMEOUT_MS);
  const timeoutSeconds = Math.max(1, Math.ceil(openclawTimeoutMs / 1000));
  const synthesisPrompt = buildWhoareuSynthesisPrompt(specDescription, langOverride);

  const agentArgv = [
    openclawBin,
    "agent",
    "--agent",
    agentId,
    "--message",
    synthesisPrompt,
    "--thinking",
    "high",
    "--json",
    "--timeout",
    String(timeoutSeconds),
  ];

  const agentRun = await runCommand({
    api,
    argv: agentArgv,
    cwd: workspaceDir,
    timeoutMs: openclawTimeoutMs,
  });
  if (!agentRun.ok) {
    return { text: formatCommandFailure("openclaw agent synthesis (whoareu)", agentRun) };
  }

  const agentText = extractAgentText(agentRun.stdout)?.trim();
  if (!agentText) {
    return {
      text:
        "❌ OpenClaw agent returned no text payload for whoareu synthesis.\n" +
        `Agent output tail:\n${tail(agentRun.stdout, 20, 2000) || "No output captured."}`,
    };
  }

  const parsed = extractWhoareuFiles(agentText);
  if (!parsed) {
    return {
      text:
        "❌ Failed to parse IDENTITY.md / SOUL.md from agent output.\n" +
        "Expected ===IDENTITY.md=== and ===SOUL.md=== delimiters.\n\n" +
        `Agent output tail:\n${tail(agentText, 20, 2000)}`,
    };
  }

  // Install both files with backup
  const targetDir = userWorkspaceDir;
  const installResults: string[] = [];

  for (const [fileName, content] of [
    ["IDENTITY.md", parsed.identityMd],
    ["SOUL.md", parsed.soulMd],
  ] as const) {
    const finalPath = path.join(targetDir, fileName);
    const stagedPath = createStagedOutputPath(finalPath);
    await fs.mkdir(path.dirname(stagedPath), { recursive: true });
    await fs.writeFile(stagedPath, content, "utf8");
    try {
      const installed = await installGeneratedFileWithBackup({
        generatedPath: stagedPath,
        finalPath,
      });
      const line = installed.backupPath
        ? `${fileName}: ${installed.finalPath} (backup: ${installed.backupPath})`
        : `${fileName}: ${installed.finalPath}`;
      installResults.push(line);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      installResults.push(`${fileName}: ❌ install failed: ${message}`);
    }
  }

  const specTail = tail(specRun.stdout, 8, 800);
  const hasFailures = installResults.some((line) => line.includes("❌"));
  const statusEmoji = hasFailures ? "⚠️" : "✅";
  const lines = [
    `${statusEmoji} Persona files generated (OpenClaw mode).`,
    `Synthesis: OpenClaw agent (${agentId})`,
    "",
    ...installResults,
  ];
  if (specTail) {
    lines.push("", "Spec tail:", specTail);
  }
  return { text: lines.join("\n") };
}

export default function register(api: OpenClawPluginApi) {
  const cfg = normalizeConfig(api.pluginConfig);

  api.registerCommand({
    name: "myprofile",
    description: "Queue profile links and generate USER.md via whoami.",
    acceptsArgs: true,
    handler: async (ctx) => {
      try {
        return await handleWhoamiCommand(api, cfg, ctx);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return { text: `❌ /myprofile error: ${message}` };
      }
    },
  });

  api.registerCommand({
    name: "whoami-gen",
    description: "Alias for /myprofile.",
    acceptsArgs: true,
    handler: async (ctx) => {
      try {
        return await handleWhoamiCommand(api, cfg, ctx);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return { text: `❌ /whoami-gen error: ${message}` };
      }
    },
  });

  api.registerCommand({
    name: "whoareu",
    description: "Generate SOUL.md/IDENTITY.md via whoareu.",
    acceptsArgs: true,
    handler: async (ctx) => {
      try {
        return await handleWhoareuCommand(api, cfg, ctx);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return { text: `❌ /whoareu error: ${message}` };
      }
    },
  });
}
