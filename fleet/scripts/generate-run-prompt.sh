#!/usr/bin/env bash
set -euo pipefail

MODE=""
TEAM=""
TASK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --team) TEAM="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$MODE" || -z "$TASK" ]]; then
  echo "Usage: $0 --mode <solo|team> [--team <team-id>] --task <task-file>" >&2
  exit 1
fi

if [[ "$MODE" == "team" && -z "$TEAM" ]]; then
  echo "--team required for team mode" >&2
  exit 1
fi

echo "Run in $MODE mode"
echo "Task spec: $TASK"
if [[ "$MODE" == "team" ]]; then
  echo "Team: fleet/core/teams/$TEAM.yaml"
  echo "Role order: PM -> Architect -> Developer -> Tester -> Reviewer"
fi
echo "Use contract: fleet/core/contracts/handoff-schema.md"
