# Migration Map From mydots

Nothing was removed functionally; paths were reorganized for productization.

## Path mapping

- `agent/fleet/contracts/*` -> `fleet/core/contracts/*`
- `agent/fleet/modes/*` -> `fleet/core/modes/*`
- `agent/fleet/personas/*` -> `fleet/core/personas/*`
- `agent/fleet/policies/*` -> `fleet/core/policies/*`
- `agent/fleet/teams/*` -> `fleet/core/teams/*`
- `agent/fleet/templates/*` -> `fleet/core/templates/*`
- `agent/fleet/quickstart.md` -> `fleet/docs/quickstart.md`
- `agent/fleet/getting-started-project.md` -> `fleet/docs/getting-started-project.md`
- `agent/fleet/advanced-customization.md` -> `fleet/docs/advanced-customization.md`
- `agent/fleet/architecture/*` -> `fleet/docs/architecture.md`
- `agent/fleet/examples/*` -> `fleet/examples/*`
- `agent/fleet/scripts/*` -> `fleet/scripts/*`

## Why this reorganization

- `core/` stays stable for contracts/config
- `docs/` becomes product documentation for users
- `ux/` is reserved for future cross-platform interface specs
