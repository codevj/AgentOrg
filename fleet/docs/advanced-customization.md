# Advanced Customization

This guide explains how to customize AgentOrg without breaking simple usage.

## Layered config model

1. Global AgentOrg defaults (`~/.agent-org`)
2. Repo checked-in config (`fleet/`)
3. Personal project extensions (`~/.agent-org/projects/<project-id>/`)

## Common advanced actions

### Add a new team

1. Copy `fleet/core/teams/product-delivery.yaml` to `fleet/core/teams/<new-team>.yaml`
2. Change `personas`, `governance_profile`, `execution_profile`
3. Validate with `fleet/scripts/validate-team-config.sh`

### Add project-only skills

Create `fleet/skills/<skill-id>.md` in repo or personal extension and reference it in `required_skills` or `optional_skills`.

### Override role order for one project

In personal extension team file, override only role-order fields and keep inherited defaults for everything else.

### Use different governance by task type

Use task tags and map them to policy profiles in team config.

Example:

- `risk=high` -> `quality_first`
- `risk=low` -> `speed_first`

## Recommended guardrails

- Keep repo `build/test/lint` commands authoritative
- Never weaken reviewer/tester requirements for risky changes
- Keep personal overrides minimal and documented
