# AgentOrg Fleet

AgentOrg Fleet is a workflow system for running single-agent and multi-agent teams in Cursor, Claude, and future UX clients.

## Design goals

- Simple daily usage (mode + team + task)
- Advanced customization (personas, policies, overlays)
- Cross-platform UX readiness (CLI, desktop, web)

## Structure

- `core/` - canonical contracts and reusable building blocks
- `docs/` - onboarding, architecture, customization
- `examples/` - runnable task workflows
- `scripts/` - prompt generation and config helpers
- `ux/` - product contracts for future cross-platform interfaces
- `../projects/` - per-project overlays and task starter packs

## Quick start

```bash
fleet/scripts/new-project.sh my-project

fleet/scripts/generate-run-prompt.sh \
  --mode team \
  --team product-delivery \
  --task projects/my-project/tasks/feature-start.md
```

## Important docs

- `fleet/docs/quickstart.md`
- `fleet/docs/getting-started-project.md`
- `fleet/docs/advanced-customization.md`
- `fleet/docs/architecture.md`
- `fleet/docs/migration-map-from-mydots.md`
