#!/usr/bin/env bash
#
# Assemblix remote bootstrap — clone the repo and run setup.sh in one line:
#
#   curl -fsSL https://raw.githubusercontent.com/nmamizerov/assemblix/main/install.sh | bash
#
# Installs the latest release tag (a stable, frozen snapshot — not the moving
# main branch). Override with ASSEMBLIX_REF to pin a specific tag or branch:
#   curl -fsSL .../install.sh | ASSEMBLIX_REF=v0.1.3 bash
#   curl -fsSL .../install.sh | ASSEMBLIX_REF=main bash      # bleeding edge
#
# Optional: pass a target directory and/or setup.sh flags, e.g.
#   curl -fsSL .../install.sh | bash -s -- ./my-assemblix --auto

set -euo pipefail

REPO_URL="https://github.com/nmamizerov/assemblix.git"

err()  { printf '\033[31m✗\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[33m!\033[0m %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

command -v git    >/dev/null 2>&1 || die "git not found. Install git and retry."
command -v docker >/dev/null 2>&1 || die \
  "Docker not found. Install Docker Desktop: https://docs.docker.com/get-docker/"

# First non-flag arg = target dir; the rest pass through to setup.sh.
TARGET="assemblix"
SETUP_ARGS=()
for arg in "$@"; do
  case "$arg" in
    -*) SETUP_ARGS+=("$arg") ;;
    *)  TARGET="$arg" ;;
  esac
done

if [ -e "$TARGET" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null)" ]; then
  die "Directory '$TARGET' exists and isn't empty. Pick another path or remove it."
fi

# Pick the ref to install: an explicit ASSEMBLIX_REF wins; otherwise the latest
# release tag (git's own version sort, newest first). Empty = no tags yet.
REF="${ASSEMBLIX_REF:-}"
if [ -z "$REF" ]; then
  REF="$(git ls-remote --tags --refs --sort=-v:refname "$REPO_URL" 'v*' 2>/dev/null \
         | head -1 | awk -F/ '{print $NF}')"
fi

if [ -n "$REF" ]; then
  printf '→ Cloning %s@%s into %s…\n' "$REPO_URL" "$REF" "$TARGET"
  git clone --depth 1 --branch "$REF" "$REPO_URL" "$TARGET"
else
  printf '→ No release tags — cloning the default branch: %s into %s…\n' "$REPO_URL" "$TARGET"
  git clone --depth 1 "$REPO_URL" "$TARGET"
fi

cd "$TARGET"

# Safety net: a tag predating the installer would lack setup.sh — fall back to
# the default branch so the one-liner still works.
if [ ! -f setup.sh ]; then
  warn "'$REF' has no setup.sh — falling back to the default branch."
  cd ..
  rm -rf "$TARGET"
  git clone --depth 1 "$REPO_URL" "$TARGET"
  cd "$TARGET"
fi

exec bash setup.sh "${SETUP_ARGS[@]}"
