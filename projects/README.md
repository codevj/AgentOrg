# Projects

`projects/` holds project-specific overlays that extend `fleet/core`.

## Quick start

Create a new project from template:

```bash
fleet/scripts/new-project.sh <project-id>
```

Then fill:

- `projects/<project-id>/context/`
- `projects/<project-id>/commands/`
- `projects/<project-id>/tasks/`
- `projects/<project-id>/teams/`
- `projects/<project-id>/runbooks/`

## Resolution model

1. `fleet/core` (global defaults in this repo)
2. `projects/<project-id>` (repo project overlay)
3. `~/.agent-org/projects/<project-id>` (personal extension)
