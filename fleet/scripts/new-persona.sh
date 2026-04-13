#!/usr/bin/env bash
set -euo pipefail

PERSONA_ID="${1:-}"
if [[ -z "$PERSONA_ID" ]]; then
  echo "Usage: $0 <persona-id>" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PERSONA_FILE="$ROOT_DIR/fleet/core/personas/${PERSONA_ID}.md"

if [[ -e "$PERSONA_FILE" ]]; then
  echo "Persona already exists: $PERSONA_FILE" >&2
  exit 1
fi

cat > "$PERSONA_FILE" <<EOF
# Persona: ${PERSONA_ID}

## Mission

Describe this persona's responsibility.

## Required inputs

- Task spec
- Team profile
- Project context

## Output format

Must follow \`fleet/core/contracts/handoff-schema.md\`.

## Exit criteria

- Deliverables completed
- Risks documented
- Exit status set correctly

## Non-goals

- List responsibilities this persona should not perform
EOF

echo "Created persona: $PERSONA_FILE"
echo "Next: add this persona ID to a team file under fleet/core/teams/"
