#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-team}"
TEAM="${2:-product-delivery}"
TASK="${3:-}"

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ -z "$TASK" ]]; then
  echo "Usage:"
  echo "  $0 team <team-id> <task-file>"
  echo "  $0 solo _ <task-file>"
  exit 1
fi

if [[ "$MODE" == "team" ]]; then
  TEAM_FILE="$ROOT_DIR/fleet/core/teams/${TEAM}.yaml"
  if [[ ! -f "$TEAM_FILE" ]]; then
    echo "Team file not found: $TEAM_FILE" >&2
    exit 1
  fi
  "$ROOT_DIR/fleet/scripts/validate-team-config.sh" "$TEAM_FILE"
  "$ROOT_DIR/fleet/scripts/generate-run-prompt.sh" --mode team --team "$TEAM" --task "$TASK"
elif [[ "$MODE" == "solo" ]]; then
  "$ROOT_DIR/fleet/scripts/generate-run-prompt.sh" --mode solo --task "$TASK"
else
  echo "Invalid mode: $MODE (expected team or solo)" >&2
  exit 1
fi
