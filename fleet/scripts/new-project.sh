#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: $0 <project-id> [--repo]" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATE_DIR="$ROOT_DIR/projects/_template"

TARGET_ROOT="${AGENT_ORG_PROJECTS_DIR:-$HOME/.agent-org/projects}"
if [[ "${2:-}" == "--repo" ]]; then
  TARGET_ROOT="$ROOT_DIR/projects"
fi
TARGET_DIR="$TARGET_ROOT/$PROJECT_ID"

if [[ ! -d "$TEMPLATE_DIR" ]]; then
  echo "Template directory missing: $TEMPLATE_DIR" >&2
  exit 1
fi

if [[ -e "$TARGET_DIR" ]]; then
  echo "Project already exists: $TARGET_DIR" >&2
  exit 1
fi

mkdir -p "$TARGET_ROOT"
mkdir -p "$TARGET_DIR"
cp -r "$TEMPLATE_DIR"/. "$TARGET_DIR"/

echo "Created project scaffold: $TARGET_DIR"
echo "Next:"
echo "1) Fill context and commands files"
echo "2) Start with tasks/feature-start.md"
echo "3) Run generate-run-prompt.sh with your task file"
