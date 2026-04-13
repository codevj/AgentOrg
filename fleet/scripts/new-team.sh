#!/usr/bin/env bash
set -euo pipefail

TEAM_ID="${1:-}"
if [[ -z "$TEAM_ID" ]]; then
  echo "Usage: $0 <team-id>" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TEAM_FILE="$ROOT_DIR/fleet/core/teams/${TEAM_ID}.yaml"

if [[ -e "$TEAM_FILE" ]]; then
  echo "Team already exists: $TEAM_FILE" >&2
  exit 1
fi

cat > "$TEAM_FILE" <<EOF
team_id: ${TEAM_ID}
mode_default: team
personas:
  - program-manager
  - architect
  - developer
  - tester
  - code-reviewer
governance_profile: quality_first
execution_profile: local_default
gates:
  reviewer_required: true
  tester_required: true
EOF

echo "Created team: $TEAM_FILE"
echo "Next: customize personas/policies, then run validate-team-config.sh"
