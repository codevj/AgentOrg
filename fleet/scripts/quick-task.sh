#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-team}"
TEAM="${2:-product-delivery}"
TITLE="${3:-Quick task}"

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_DIR="$ROOT_DIR/.tmp"
TASK_FILE="$TMP_DIR/quick-task.md"

mkdir -p "$TMP_DIR"

cat > "$TASK_FILE" <<EOF
# Quick Task Spec

## Objective

$TITLE

## Scope

- In scope:
- Out of scope:

## Acceptance criteria

- [ ] Task objective is complete
- [ ] No unrelated files changed

## Validation commands

\`\`\`bash
# add command(s) if needed
\`\`\`
EOF

if [[ "$MODE" == "solo" ]]; then
  "$ROOT_DIR/fleet/scripts/generate-run-prompt.sh" \
    --mode solo \
    --task "$TASK_FILE"
else
  "$ROOT_DIR/fleet/scripts/generate-run-prompt.sh" \
    --mode team \
    --team "$TEAM" \
    --task "$TASK_FILE"
fi

echo
echo "Task file created at: $TASK_FILE"
echo "Edit it if needed, then paste the generated prompt into Cursor/Claude."
