#!/usr/bin/env bash
set -euo pipefail

TEAM_FILE="${1:-}"
if [[ -z "$TEAM_FILE" ]]; then
  echo "Usage: $0 <team-yaml-path>" >&2
  exit 1
fi

for key in team_id mode_default personas governance_profile execution_profile gates; do
  if ! grep -Eq "^$key:" "$TEAM_FILE"; then
    echo "Missing key: $key" >&2
    exit 1
  fi
done

echo "OK: $TEAM_FILE"
