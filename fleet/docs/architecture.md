# Architecture

## Resolution order

1. Global AgentOrg defaults (`~/.agent-org`)
2. Repo checked-in config (`fleet/`)
3. Repo project overlay (`projects/<project-id>/`)
4. Personal project extension (`~/.agent-org/projects/<project-id>/`)
5. Task overrides

## Merge strategy (per_key)

- `personas`: union by ID
- `teams`: merge by `team_id`
- `skills.required`: append and dedupe
- `skills.optional`: append and dedupe
- `workflow.role_order`: repo default unless explicitly overridden
- `policies.governance`: override allowed
- `policies.execution`: override allowed
- `commands`: repo wins
- `project_context`: repo wins, personal may add local notes
- `gates`: stricter rule wins
