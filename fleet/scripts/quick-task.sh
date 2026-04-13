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

- In scope: whatever is needed to achieve the objective
- Out of scope: unrelated changes

## Acceptance criteria

- [ ] Task objective is complete
- [ ] No unrelated files changed

## Validation commands

\`\`\`bash
# add command(s) if needed
\`\`\`
EOF

echo "--- Task file: $TASK_FILE ---" >&2
echo "--- Edit it if needed, then use the prompt below ---" >&2
echo "" >&2

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
