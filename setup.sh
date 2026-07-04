#!/usr/bin/env bash
#
# Assemblix one-command bootstrap.
#
# Verifies Docker, generates the two required secrets, writes .env, and brings the
# stack up. Run after cloning:
#
#   ./setup.sh              # interactive — pick Auto or Detailed
#   ./setup.sh --auto       # no prompts: lean prod stack, sensible defaults
#   ./setup.sh --detailed   # full prompts: mode, ports, queue tier, LLM keys
#
# Prompts read from /dev/tty, so this works under `curl -fsSL .../install.sh | bash`.

set -euo pipefail

# --- Resolve repo root (the dir holding this script) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Colours (disabled when not a TTY) ---
if [ -t 1 ]; then
  BOLD="$(printf '\033[1m')"; DIM="$(printf '\033[2m')"; RED="$(printf '\033[31m')"
  GREEN="$(printf '\033[32m')"; YELLOW="$(printf '\033[33m')"; CYAN="$(printf '\033[36m')"
  RESET="$(printf '\033[0m')"
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; RESET=""
fi

info()  { printf '%s\n' "$*"; }
ok()    { printf '%s✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn()  { printf '%s!%s %s\n' "$YELLOW" "$RESET" "$*"; }
err()   { printf '%s✗%s %s\n' "$RED" "$RESET" "$*" >&2; }
step()  { printf '%s→%s %s\n' "$CYAN" "$RESET" "$*"; }
die()   { err "$*"; exit 1; }

# --- Read a prompt from the terminal even when stdin is a pipe (curl | bash) ---
# Probe /dev/tty in a subshell: it can exist yet fail to open with no controlling
# terminal (some non-interactive contexts), so a perms check alone isn't enough.
TTY="/dev/tty"
have_tty() { ( exec 3<>"$TTY" ) >/dev/null 2>&1; }

ask() {
  # ask <varname> <prompt> [default]
  local __var="$1" __prompt="$2" __default="${3:-}" __reply=""
  local __hint=""
  [ -n "$__default" ] && __hint=" ${DIM}[$__default]${RESET}"
  if have_tty; then
    printf '%s%s: ' "$__prompt" "$__hint" > "$TTY"
    IFS= read -r __reply < "$TTY" || __reply=""
  fi
  [ -z "$__reply" ] && __reply="$__default"
  printf -v "$__var" '%s' "$__reply"
}

ask_secret() {
  # ask_secret <varname> <prompt> — silent input, no default
  local __var="$1" __prompt="$2" __reply=""
  if have_tty; then
    printf '%s %s(Enter to skip)%s: ' "$__prompt" "$DIM" "$RESET" > "$TTY"
    IFS= read -rs __reply < "$TTY" || __reply=""
    printf '\n' > "$TTY"
  fi
  printf -v "$__var" '%s' "$__reply"
}

# --- Flags ---
MODE_FLAG=""        # auto | detailed | "" (ask)
DEPLOY=""           # prod | dev
DO_BUILD=1

usage() {
  cat <<EOF
${BOLD}Assemblix bootstrap${RESET}

Usage: ./setup.sh [options]

  --auto, -y, --yes   No prompts: generate secrets, lean prod stack, bring it up.
  --detailed          Full prompts: mode, ports, queue tier, LLM keys.
  --mode prod|dev     Force deploy mode (skips the mode question).
  --no-build          Skip the image --build step (faster re-runs).
  -h, --help          Show this help.

With no flags you're asked to pick Auto or Detailed.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --auto|-y|--yes) MODE_FLAG="auto" ;;
    --detailed)      MODE_FLAG="detailed" ;;
    --mode)          shift; DEPLOY="${1:-}" ;;
    --mode=*)        DEPLOY="${1#*=}" ;;
    --no-build)      DO_BUILD=0 ;;
    -h|--help)       usage; exit 0 ;;
    *)               die "Unknown option: $1 (try --help)" ;;
  esac
  shift
done

if [ -n "$DEPLOY" ] && [ "$DEPLOY" != "prod" ] && [ "$DEPLOY" != "dev" ]; then
  die "--mode must be 'prod' or 'dev'"
fi

# No TTY and no explicit mode → fall back to auto so CI/pipes don't hang.
if [ -z "$MODE_FLAG" ] && ! have_tty; then
  MODE_FLAG="auto"
fi

printf '\n%s╔══════════════════════════════════════╗%s\n' "$BOLD" "$RESET"
printf '%s║        Assemblix · bootstrap         ║%s\n' "$BOLD" "$RESET"
printf '%s╚══════════════════════════════════════╝%s\n\n' "$BOLD" "$RESET"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Preflight: Docker
# ─────────────────────────────────────────────────────────────────────────────
step "Checking Docker…"

command -v docker >/dev/null 2>&1 || die \
  "Docker not found. Install Docker Desktop: https://docs.docker.com/get-docker/"

if ! docker compose version >/dev/null 2>&1; then
  die "Docker Compose v2 is required (the 'docker compose' command). Update Docker Desktop."
fi

if ! docker info >/dev/null 2>&1; then
  warn "Docker is installed but the daemon isn't running."
  case "$(uname -s)" in
    Darwin)
      step "Trying to start Docker Desktop…"
      open -a Docker >/dev/null 2>&1 || true
      printf '  waiting for the daemon'
      for _ in $(seq 1 60); do
        if docker info >/dev/null 2>&1; then printf '\n'; break; fi
        printf '.'; sleep 1
      done
      ;;
    Linux)
      info "  Start the daemon: ${BOLD}sudo systemctl start docker${RESET}"
      ;;
  esac
  docker info >/dev/null 2>&1 || die "Docker daemon isn't running. Start Docker and retry."
fi
ok "Docker ready ($(docker --version | awk '{print $3}' | tr -d ','))"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Secret generation (no host Python required)
# ─────────────────────────────────────────────────────────────────────────────
gen_jwt() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 48 | tr -d '\n'
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  else
    die "openssl or python3 is required to generate secrets."
  fi
}

gen_fernet() {
  # Fernet key = urlsafe-base64 of 32 random bytes.
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n'
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  else
    die "openssl or python3 is required to generate secrets."
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. .env helpers
# ─────────────────────────────────────────────────────────────────────────────
ENV_FILE=".env"
EXAMPLE_FILE=".env.example"

# set_env KEY VALUE — replace `^KEY=` line in .env (awk -v keeps special chars safe).
set_env() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  awk -v k="$key" -v v="$value" '
    $0 ~ "^" k "=" { print k "=" v; found=1; next }
    { print }
    END { if (!found) print k "=" v }
  ' "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
}

# get_env KEY — print current value (empty if unset/blank), strips trailing comments.
get_env() {
  local key="$1"
  awk -v k="$key" '
    $0 ~ "^" k "=" {
      sub("^" k "=", "")
      sub(/[ \t]+#.*$/, "")
      gsub(/[ \t]+$/, "")
      print
      exit
    }
  ' "$ENV_FILE"
}

# ─────────────────────────────────────────────────────────────────────────────
# 4. Create or reuse .env
# ─────────────────────────────────────────────────────────────────────────────
step "Preparing .env…"

REGEN_ENV=1
if [ -f "$ENV_FILE" ]; then
  if [ "$MODE_FLAG" = "auto" ]; then
    REGEN_ENV=0
  else
    ask REUSE ".env already exists. Use it? (y/n)" "y"
    case "$REUSE" in y|Y|yes) REGEN_ENV=0 ;; *) REGEN_ENV=1 ;; esac
  fi
fi

if [ "$REGEN_ENV" = "1" ]; then
  [ -f "$EXAMPLE_FILE" ] || die "$EXAMPLE_FILE not found — run this from the repo root."
  # Strip inline `# ...` comments from KEY=value lines: Docker Compose's env_file
  # parser keeps them as part of the value (e.g. a blank REDIS_URL= would arrive
  # as its comment string and break Redis detection). Full-line comments stay.
  awk '
    /^[A-Za-z_][A-Za-z0-9_]*=/ { sub(/[ \t]+#.*$/, ""); sub(/[ \t]+$/, "") }
    { print }
  ' "$EXAMPLE_FILE" > "$ENV_FILE"
  set_env JWT_SECRET_KEY "$(gen_jwt)"
  set_env ENCRYPTION_KEY "$(gen_fernet)"
  ok ".env created, secrets generated"
else
  # Reusing: make sure the two required secrets are present.
  [ -n "$(get_env JWT_SECRET_KEY)" ] || { set_env JWT_SECRET_KEY "$(gen_jwt)"; warn "JWT_SECRET_KEY was empty — generated"; }
  [ -n "$(get_env ENCRYPTION_KEY)" ] || { set_env ENCRYPTION_KEY "$(gen_fernet)"; warn "ENCRYPTION_KEY was empty — generated"; }
  ok "Using existing .env"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 5. Mode selection
# ─────────────────────────────────────────────────────────────────────────────
if [ -z "$MODE_FLAG" ]; then
  printf '\n%sHow do you want to deploy?%s\n' "$BOLD" "$RESET"
  printf '  %s[1] Auto%s        — secrets + lean prod (postgres + api + web), no questions\n' "$BOLD" "$RESET"
  printf '  %s[2] Detailed%s    — pick mode, ports, queue (Redis+worker), LLM keys\n\n' "$BOLD" "$RESET"
  ask MODE_CHOICE "Choice" "1"
  case "$MODE_CHOICE" in 2|detailed) MODE_FLAG="detailed" ;; *) MODE_FLAG="auto" ;; esac
fi

# Defaults
[ -z "$DEPLOY" ] && DEPLOY="prod"

if [ "$MODE_FLAG" = "detailed" ]; then
  printf '\n%sDetailed setup%s %s(Enter — keep the default)%s\n\n' \
    "$BOLD" "$RESET" "$DIM" "$RESET"

  # a. Deploy mode
  ask DM "Mode: [1] prod (lean) / [2] dev (HMR)" "1"
  case "$DM" in 2|dev) DEPLOY="dev" ;; *) DEPLOY="prod" ;; esac

  # b. Ports
  ask WEB_P "Web UI port (prod only)" "$(get_env WEB_PORT)"
  [ -n "$WEB_P" ] && set_env WEB_PORT "$WEB_P"
  ask API_P "API port" "$(get_env API_PORT)"
  [ -n "$API_P" ] && set_env API_PORT "$API_P"

  # c. Queue tier
  ask QUEUE "Enable the Redis + worker queue? (y/n)" "n"
  case "$QUEUE" in
    y|Y|yes)
      set_env COMPOSE_PROFILES "queue"
      set_env REDIS_URL "redis://redis:6379/0"
      set_env EXECUTION_QUEUE_ENABLED "true"
      ok "Queue enabled (queue profile)"
      ;;
  esac

  # d. Optional system LLM keys
  printf '\n%sSystem LLM keys%s %s(optional — you can add them later in the UI)%s\n' \
    "$BOLD" "$RESET" "$DIM" "$RESET"
  ask_secret K_OPENAI   "  OpenAI";          [ -n "$K_OPENAI" ]   && set_env SYSTEM_OPENAI_API_KEY "$K_OPENAI"
  ask_secret K_GEMINI   "  Gemini";          [ -n "$K_GEMINI" ]   && set_env SYSTEM_GEMINI_API_KEY "$K_GEMINI"
  ask_secret K_DEEPSEEK "  DeepSeek";        [ -n "$K_DEEPSEEK" ] && set_env SYSTEM_DEEPSEEK_API_KEY "$K_DEEPSEEK"
  ask_secret K_TAVILY   "  Tavily (search)"; [ -n "$K_TAVILY" ]   && set_env TAVILY_API_KEY "$K_TAVILY"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 6. Bring the stack up
# ─────────────────────────────────────────────────────────────────────────────
API_PORT="$(get_env API_PORT)"; [ -z "$API_PORT" ] && API_PORT="8000"
WEB_PORT="$(get_env WEB_PORT)"; [ -z "$WEB_PORT" ] && WEB_PORT="8080"

COMPOSE=(docker compose)
[ "$DEPLOY" = "dev" ] && COMPOSE=(docker compose -f docker-compose.dev.yml)

UP_ARGS=(up -d)
[ "$DO_BUILD" = "1" ] && UP_ARGS+=(--build)

printf '\n'
step "Bringing the stack up (${BOLD}${DEPLOY}${RESET})… the first build may take a couple of minutes."
"${COMPOSE[@]}" "${UP_ARGS[@]}"

# ─────────────────────────────────────────────────────────────────────────────
# 7. Wait for health
# ─────────────────────────────────────────────────────────────────────────────
HEALTH_URL="http://localhost:${API_PORT}/health"
step "Waiting for the API to be ready ($HEALTH_URL)…"
HEALTHY=0
if command -v curl >/dev/null 2>&1; then
  printf '  '
  for _ in $(seq 1 120); do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then HEALTHY=1; printf '\n'; break; fi
    printf '.'; sleep 1
  done
else
  warn "curl not found — skipping the readiness check."
fi

WEB_URL="http://localhost:${WEB_PORT}"
[ "$DEPLOY" = "dev" ] && WEB_URL="http://localhost:5173"

printf '\n'
if [ "$HEALTHY" = "1" ] || ! command -v curl >/dev/null 2>&1; then
  printf '%s╔══════════════════════════════════════╗%s\n' "$GREEN" "$RESET"
  printf '%s║         Assemblix is running!        ║%s\n' "$GREEN" "$RESET"
  printf '%s╚══════════════════════════════════════╝%s\n\n' "$GREEN" "$RESET"
  ok "Open ${BOLD}${WEB_URL}${RESET} and register the first account"
  info "  (the organization and project are created automatically)"
else
  warn "The API didn't respond in time. The stack may still be building."
  info "  Check the logs and re-test $HEALTH_URL"
fi

printf '\n%sUseful commands:%s\n' "$BOLD" "$RESET"
if [ "$DEPLOY" = "dev" ]; then
  info "  make logs       — stack logs"
  info "  make down       — stop the stack"
else
  info "  make logs-prod  — stack logs"
  info "  make down-prod  — stop the stack"
fi
printf '\n'
