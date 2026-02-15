#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${WHOWEARE_REPO_URL:-https://github.com/ReinerBRO/WhoWeAre.git}"
BRANCH="${WHOWEARE_BRANCH:-main}"
INSTALL_DIR="${WHOWEARE_DIR:-$HOME/WhoWeAre}"
OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
WHOAMI_SYNTHESIS_MODE="${WHOWEARE_WHOAMI_SYNTHESIS_MODE:-openclaw}"
OPENCLAW_AGENT_ID="${WHOWEARE_OPENCLAW_AGENT_ID:-main}"
OPENCLAW_FALLBACK_TO_WHOAMI="${WHOWEARE_OPENCLAW_FALLBACK_TO_WHOAMI:-1}"
PYTHON_BIN="${WHOWEARE_PYTHON_BIN:-python3}"
VENV_DIR="${WHOWEARE_VENV_DIR:-$INSTALL_DIR/.venv}"
WORKSPACE_DIR="${WHOWEARE_WORKSPACE_DIR:-$INSTALL_DIR/output}"
WHOAMI_DIR="${WHOWEARE_WHOAMI_DIR:-$INSTALL_DIR/whoami}"
WHOAREU_DIR="${WHOWEARE_WHOAREU_DIR:-$INSTALL_DIR/whoareu}"
PLUGIN_DIR="${WHOWEARE_PLUGIN_DIR:-$INSTALL_DIR/openclaw-whoweare-plugin}"
NO_RESTART="${WHOWEARE_NO_RESTART:-0}"

log() {
  printf '[WhoWeAre] %s\n' "$*"
}

fail() {
  printf '[WhoWeAre] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"
}

set_config() {
  local key="$1"
  local value="$2"
  "$OPENCLAW_BIN" config set "$key" "$value" >/dev/null
  log "Config set: $key"
}

require_cmd git
require_cmd "$PYTHON_BIN"
require_cmd "$OPENCLAW_BIN"
OPENCLAW_BIN_PATH="$(command -v "$OPENCLAW_BIN")"

log "Preparing source at $INSTALL_DIR"
if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

log "Creating Python virtual environment"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install -U pip setuptools wheel

log "Installing Python packages"
"$VENV_DIR/bin/python" -m pip install -e "$INSTALL_DIR/llmkit" -e "$WHOAMI_DIR" -e "$WHOAREU_DIR"

log "Installing OpenClaw plugin"
if "$OPENCLAW_BIN" plugins info openclaw-whoweare >/dev/null 2>&1; then
  "$OPENCLAW_BIN" plugins uninstall openclaw-whoweare --keep-files --force >/dev/null 2>&1 || true
fi
"$OPENCLAW_BIN" plugins install -l "$PLUGIN_DIR"

mkdir -p "$WORKSPACE_DIR"

log "Writing plugin config"
set_config "plugins.entries.openclaw-whoweare.config.pythonBin" "$VENV_DIR/bin/python"
set_config "plugins.entries.openclaw-whoweare.config.whoamiProjectDir" "$WHOAMI_DIR"
set_config "plugins.entries.openclaw-whoweare.config.whoareuProjectDir" "$WHOAREU_DIR"
set_config "plugins.entries.openclaw-whoweare.config.workspaceDir" "$WORKSPACE_DIR"
set_config "plugins.entries.openclaw-whoweare.config.whoamiSynthesisMode" "$WHOAMI_SYNTHESIS_MODE"
set_config "plugins.entries.openclaw-whoweare.config.openclawBin" "$OPENCLAW_BIN_PATH"
set_config "plugins.entries.openclaw-whoweare.config.openclawAgentId" "$OPENCLAW_AGENT_ID"
if [ "$OPENCLAW_FALLBACK_TO_WHOAMI" = "0" ]; then
  set_config "plugins.entries.openclaw-whoweare.config.openclawFallbackToWhoami" false
else
  set_config "plugins.entries.openclaw-whoweare.config.openclawFallbackToWhoami" true
fi

if [ -n "${WHOWEARE_DEFAULT_PROVIDER:-}" ]; then
  set_config "plugins.entries.openclaw-whoweare.config.defaultProvider" "$WHOWEARE_DEFAULT_PROVIDER"
fi
if [ -n "${WHOWEARE_DEFAULT_MODEL:-}" ]; then
  set_config "plugins.entries.openclaw-whoweare.config.defaultModel" "$WHOWEARE_DEFAULT_MODEL"
fi
if [ -n "${WHOWEARE_DEFAULT_API_BASE:-}" ]; then
  set_config "plugins.entries.openclaw-whoweare.config.defaultApiBase" "$WHOWEARE_DEFAULT_API_BASE"
fi
if [ -n "${WHOWEARE_DEFAULT_API_KEY:-}" ]; then
  "$OPENCLAW_BIN" config set \
    "plugins.entries.openclaw-whoweare.config.defaultApiKey" \
    "$WHOWEARE_DEFAULT_API_KEY" >/dev/null
  log "Config set: plugins.entries.openclaw-whoweare.config.defaultApiKey"
fi

if [ "$NO_RESTART" = "1" ]; then
  log "Gateway restart skipped (WHOWEARE_NO_RESTART=1)."
else
  log "Restarting OpenClaw gateway"
  if "$OPENCLAW_BIN" gateway restart >/dev/null 2>&1; then
    log "Gateway restarted."
  else
    log "Gateway restart command failed. Please restart manually."
  fi
fi

log "Done."
printf '\n'
printf 'Try these commands in OpenClaw chat:\n'
printf '  /myprofile add https://github.com/yourname\n'
printf '  /myprofile run\n'
printf '  /myprofile run --lang en\n'
printf '  /whoareu prompt A cyber ghost named Sayo, sharp-tongued but kind\n'
printf '  /whoareu reference Jarvis --lang en\n'
