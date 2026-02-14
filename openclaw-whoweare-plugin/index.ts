import fs from "node:fs/promises";
import path from "node:path";
import type { OpenClawPluginApi, ReplyPayload } from "openclaw/plugin-sdk";

const STATE_FILE = "openclaw-whoweare-state.json";
const STATE_VERSION = 1;
const URL_REGEX = /https?:\/\/[^\s]+/g;
const DEFAULT_WHOAMI_TIMEOUT_MS = 10 * 60_000;
const DEFAULT_WHOAREU_TIMEOUT_MS = 10 * 60_000;

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
  noLlm: boolean;
  keepQueue: boolean;
  unknownTokens: string[];
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

function trimMaybe(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
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

  const valueFlags = new Set(["provider", "model", "api-base", "api-key", "output"]);
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

  return {
    explicitUrls,
    provider: values["provider"],
    model: values["model"],
    apiBase: values["api-base"],
    apiKey: values["api-key"],
    output: values["output"],
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
    "/myprofile run [--provider x --model y --no-llm --keep-queue]",
    "/myprofile run <url1> <url2> ...",
    "",
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
  try {
    const result = await api.runtime.system.runCommandWithTimeout(argv, {
      timeoutMs,
      cwd,
    });
    if (result.code === 0) {
      const stdoutTail = tail(result.stdout);
      if (!stdoutTail) {
        return { text: successMessage };
      }
      return { text: `${successMessage}\n\nLast log lines:\n${stdoutTail}` };
    }

    const stderrTail = tail(result.stderr);
    const stdoutTail = tail(result.stdout);
    const details = [stderrTail, stdoutTail].filter(Boolean).join("\n");
    return {
      text: `❌ ${title} failed (exit code ${String(result.code ?? "unknown")}).\n${details || "No output captured."}`,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { text: `❌ ${title} failed before execution: ${message}` };
  }
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
  const projectDir = await resolveProjectDir(api, cfg, workspaceDir, "whoami");
  const projectError = await ensureProject(projectDir, "whoami");
  if (projectError) {
    return { text: `${projectError}\nConfigure plugins.entries.openclaw-whoweare.config.whoamiProjectDir if needed.` };
  }

  const pythonBin = await resolvePythonBin(api, cfg, projectDir);
  const outputPath = resolveOutputPath(workspaceDir, run.output, "USER.md");
  const argv = [pythonBin, "-m", "whoami.cli"];
  for (const link of links) {
    argv.push("--link", link);
  }
  argv.push("--output", outputPath);
  if (run.noLlm) {
    argv.push("--no-llm");
  }
  pushLlmFlags(argv, cfg, {
    defaultProvider: run.provider,
    defaultModel: run.model,
    defaultApiBase: run.apiBase,
    defaultApiKey: run.apiKey,
  });

  const timeoutMs = asPositiveInt(cfg.whoamiTimeoutMs, DEFAULT_WHOAMI_TIMEOUT_MS);
  const result = await executeCli({
    api,
    argv,
    cwd: projectDir,
    timeoutMs,
    title: "whoami",
    successMessage: `✅ USER.md generated at ${outputPath}\nLinks: ${links.length}`,
  });

  if (usingQueue && !run.keepQueue && result.text?.startsWith("✅")) {
    delete state.whoamiQueues[queueKey];
    await writeState(statePath, state);
    return {
      text: `${result.text}\nQueue cleared. Use --keep-queue on /myprofile run if you want to keep it.`,
    };
  }

  return result;
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
