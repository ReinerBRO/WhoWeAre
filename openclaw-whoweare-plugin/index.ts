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

  const valueFlags = new Set(["provider", "model", "api-base", "api-key", "output", "mode", "agent"]);
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
    "/myprofile run [--mode openclaw|whoami --agent main --provider x --model y --no-llm --keep-queue]",
    "/myprofile run <url1> <url2> ...",
    "",
    "Default mode: openclaw (use OpenClaw agent synthesis).",
    "Fallback mode: whoami (direct litellm API call).",
    "Default output target: <agents.defaults.workspace>/USER.md (auto backup before replace).",
    "Alias: /whoami-gen ...",
    "Tip: 先 add 多个链接，再 run 一次生成 USER.md。",
  ].join("\n");
}

function formatWhoareuHelp(): string {
  return [
    "whoareu commands:",
    "",
    "/whoareu prompt <描述>",
    "/whoareu template <professional|casual|otaku|minimalist|chaotic>",
    "/whoareu reference <角色参考>",
    "/whoareu <描述>   (等同于 prompt 模式)",
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

function buildOpenClawSynthesisPrompt(params: { links: string[]; scrapeOutput: string }): string {
  const links = params.links.map((link, index) => `${index + 1}. ${link}`).join("\n");
  const scraped = clipText(params.scrapeOutput.trim(), MAX_SCRAPE_TEXT_CHARS);
  return [
    "You are ProfileForge, generating a USER.md that an AI Agent can directly consume.",
    "Goal: After reading this file, the Agent instantly knows who this person is, what they're good at, what they care about, and how to talk to them.",
    "",
    "## Output Structure",
    "",
    "Two fixed sections:",
    "1. 👤 Identity — name/alias, role, timezone/location, one-line vibe (inferred from bio/behavior)",
    "2. 💬 Interaction Guidelines — 3-5 directives telling the Agent what tone, style, and preferences to use",
    "",
    "All other sections are dynamically decided by YOU based on the data. Examples:",
    "- Tech person → add 🛠 Tech Stack, 📦 Projects",
    "- Gamer → add 🎮 Gaming",
    "- Content creator → add 🎬 Content Creation",
    "- Student/researcher → add 🔬 Research",
    "- Mix of everything → one section per aspect",
    "",
    "Principle: only create sections for data you actually have. Never fabricate.",
    "",
    "## Rules",
    "",
    "- This is an operation manual for an Agent, NOT an analysis report for humans",
    "- Tone examples: \"User prefers concise code-first discussion.\" \"Treat as a peer gamer.\"",
    "- Only write confirmed facts. Skip anything uncertain rather than guessing.",
    "- No meta-info: no data sources, confidence levels, follow-up suggestions, or generation dates",
    "- Specific > vague: write \"Elden Ring 深度玩家\" not \"喜欢游戏\"",
    "- Use short phrases, keywords, dashes. No paragraphs.",
    "- Filter sensitive info (email, phone, ID numbers)",
    "- Interaction Guidelines is the MOST IMPORTANT section — infer communication preferences from data",
    "- Length adapts to data volume, max 30 lines",
    "- Markdown format, emoji prefixes on section headers",
    "- Use Chinese by default",
    "",
    "Source links:",
    links,
    "",
    "Scraped data:",
    scraped,
  ].join("\n");
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
  });
  const agentArgv = [
    openclawBin,
    "agent",
    "--agent",
    agentId,
    "--message",
    synthesisPrompt,
    "--thinking",
    "low",
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
  const workspaceDir = resolveWorkspaceDir(api, cfg);
  const projectDir = await resolveProjectDir(api, cfg, workspaceDir, "whoareu");
  const projectError = await ensureProject(projectDir, "whoareu");
  if (projectError) {
    return { text: `${projectError}\nConfigure plugins.entries.openclaw-whoweare.config.whoareuProjectDir if needed.` };
  }
  const pythonBin = await resolvePythonBin(api, cfg, projectDir);

  const argv = [pythonBin, "-m", "whoareu.cli", "--install", workspaceDir];
  pushLlmFlags(argv, cfg);

  if (action === "help") {
    return { text: formatWhoareuHelp() };
  }

  if (action === "template") {
    const template = splitFirstArg(rest).first;
    if (!template) {
      return { text: "Usage: /whoareu template <professional|casual|otaku|minimalist|chaotic>" };
    }
    argv.push("--template", template);
  } else if (action === "reference") {
    if (!rest) {
      return { text: "Usage: /whoareu reference <角色参考>" };
    }
    argv.push("--reference", rest);
  } else if (action === "prompt") {
    if (!rest) {
      return { text: "Usage: /whoareu prompt <描述>" };
    }
    argv.push("--prompt", rest);
  } else {
    argv.push("--prompt", input);
  }

  const timeoutMs = asPositiveInt(cfg.whoareuTimeoutMs, DEFAULT_WHOAREU_TIMEOUT_MS);
  return await executeCli({
    api,
    argv,
    cwd: projectDir,
    timeoutMs,
    title: "whoareu",
    successMessage:
      `✅ Persona files generated in ${workspaceDir}\n` +
      `Files: AGENTS.md, SOUL.md, IDENTITY.md`,
  });
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
    description: "Generate AGENTS.md/SOUL.md/IDENTITY.md via whoareu.",
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
