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

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CORE_DIR="$ROOT_DIR/fleet/core"

# Resolve task file path (absolute or relative to pwd)
if [[ "$TASK" != /* ]]; then
  TASK="$(pwd)/$TASK"
fi

if [[ ! -f "$TASK" ]]; then
  echo "Task file not found: $TASK" >&2
  exit 1
fi

# --- Helper: read file or die ---
read_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Required file not found: $path" >&2
    exit 1
  fi
  cat "$path"
}

# --- Helper: read persona by id ---
read_persona() {
  local id="$1"
  read_file "$CORE_DIR/personas/${id}.md"
}

# --- Helper: extract personas list from team YAML ---
get_team_personas() {
  local team_file="$1"
  grep -E '^\s+-\s+' "$team_file" | sed 's/^[[:space:]]*-[[:space:]]*//' | sed 's/[[:space:]]*$//' | head -20
}

# --- Helper: extract governance profile from team YAML ---
get_team_field() {
  local team_file="$1"
  local field="$2"
  grep -E "^${field}:" "$team_file" | sed "s/^${field}:[[:space:]]*//" | sed 's/[[:space:]]*$//' | head -1
}

# --- Helper: extract gate value ---
get_gate() {
  local team_file="$1"
  local gate="$2"
  grep -E "^[[:space:]]+${gate}:" "$team_file" | sed "s/^.*${gate}:[[:space:]]*//" | sed 's/[[:space:]]*$//' | head -1
}

# =====================================================================
# Compile the prompt
# =====================================================================

if [[ "$MODE" == "solo" ]]; then
  # ----- SOLO MODE PROMPT -----
  cat <<'PROMPT_HEADER'
You are executing a solo workflow. Complete the task below by following these steps in order.

## Workflow

1. Read and understand the task spec
2. Implement scoped changes — only touch what the task requires
3. Run all validation commands and verify they pass
4. Produce a run summary (format below)

## Rules

- Do not modify files outside the task scope
- Do not skip validation commands
- If validation fails, fix the issue and re-validate before summarizing

PROMPT_HEADER

  echo "## Task"
  echo ""
  read_file "$TASK"
  echo ""

  cat <<'PROMPT_FOOTER'
## Run Summary Format

When complete, output a summary with these sections:

```
## Run Summary
- **Mode**: solo
- **Changed files**: list each file modified
- **Validation results**: pass/fail for each command with output
- **Residual risks**: anything the user should know
- **Next actions**: follow-ups if any
```
PROMPT_FOOTER

else
  # ----- TEAM MODE PROMPT -----
  TEAM_FILE="$CORE_DIR/teams/${TEAM}.yaml"
  if [[ ! -f "$TEAM_FILE" ]]; then
    echo "Team file not found: $TEAM_FILE" >&2
    exit 1
  fi

  GOV_PROFILE="$(get_team_field "$TEAM_FILE" "governance_profile")"
  REVIEWER_REQUIRED="$(get_gate "$TEAM_FILE" "reviewer_required")"
  TESTER_REQUIRED="$(get_gate "$TEAM_FILE" "tester_required")"

  cat <<PROMPT_HEADER
You are executing a team workflow. You will assume each role in sequence, producing a structured handoff after completing each role before moving to the next.

## How This Works

You are one agent playing multiple roles. For each role:
1. Read the task spec and all prior handoffs
2. Do the work defined by that role's mission
3. Output a handoff (format below) before moving to the next role
4. Do not proceed if your exit_status is \`blocked\`

## Governance: ${GOV_PROFILE}

- Reviewer required: ${REVIEWER_REQUIRED}
- Tester required: ${TESTER_REQUIRED}
PROMPT_HEADER

  # Gate rules
  if [[ "$GOV_PROFILE" == "quality_first" ]]; then
    cat <<'GATE_RULES'
- Every role must produce a complete handoff — no skipped sections
- If Code Reviewer finds high or medium severity issues, loop back: Developer -> Tester -> Code Reviewer, until clean
- Tester must provide actual command output as evidence
GATE_RULES
  elif [[ "$GOV_PROFILE" == "speed_first" ]]; then
    cat <<'GATE_RULES'
- Minimize iteration — fix obvious issues inline rather than looping
- Reviewer is optional; skip if changes are low-risk
- Tester must still provide command evidence
GATE_RULES
  fi

  echo ""

  # Handoff schema
  cat <<'HANDOFF'
## Handoff Contract

After completing each role, output a handoff block in this exact format:

```
### Handoff: [Role Name]

**input_digest**: What I received and understood
**decision**: What I decided to do (or approve/reject)
**rationale**: Why — the key tradeoffs or reasoning
**artifacts**: What I produced (files, designs, test results, findings)
**risks**: What could go wrong, what's uncertain
**exit_status**: pass | blocked
```

### Severity scale (for Tester and Code Reviewer findings)

- **high**: release-blocking — correctness or safety risk
- **medium**: must-fix before merge
- **low**: non-blocking improvement

### Enforcement

- Cannot advance to the next role if exit_status is `blocked`
- Reviewer high/medium findings trigger a loop back through Developer -> Tester -> Reviewer
- Developer must stay within the file scope approved by Architect
- Tester must show actual command output, not just "tests passed"

HANDOFF

  # Roles section
  echo "## Roles (execute in this order)"
  echo ""

  ROLE_NUM=1
  while IFS= read -r persona_id; do
    # Skip empty lines
    [[ -z "$persona_id" ]] && continue

    echo "### ${ROLE_NUM}. $(echo "$persona_id" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2)}1')"
    echo ""
    # Read persona file, skip the H1 title line to avoid redundancy
    read_persona "$persona_id" | tail -n +3
    echo ""
    ROLE_NUM=$((ROLE_NUM + 1))
  done < <(get_team_personas "$TEAM_FILE")

  # Task section
  echo "## Task"
  echo ""
  read_file "$TASK"
  echo ""

  # Final output format
  cat <<'PROMPT_FOOTER'
## Final Run Summary

After all roles complete, output a final summary:

```
## Run Summary
- **Mode**: team
- **Team**: [team-id]
- **Roles completed**: list each role and its exit_status
- **Changed files**: list each file modified
- **Validation results**: pass/fail for each command with evidence
- **Review findings**: list by severity (high/medium/low)
- **Residual risks**: anything unresolved
- **Next actions**: follow-ups if any
```
PROMPT_FOOTER

fi
