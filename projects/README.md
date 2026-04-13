# Projects

`projects/` keeps only the reusable template committed in git.

Project-specific overlays (for Helios or any other repo) should live in:

- `~/.agent-org/projects/<project-id>/`

## Quick start

Create a new project from template:

```bash
fleet/scripts/new-project.sh <project-id>
```

Then fill:

- `~/.agent-org/projects/<project-id>/context/`
- `~/.agent-org/projects/<project-id>/commands/`
- `~/.agent-org/projects/<project-id>/tasks/`
- `~/.agent-org/projects/<project-id>/teams/`
- `~/.agent-org/projects/<project-id>/runbooks/`

Optional: to scaffold inside this repo (not recommended), use:

```bash
fleet/scripts/new-project.sh <project-id> --repo
```

## Resolution model

1. `fleet/core` (global defaults in this repo)
2. `~/.agent-org/projects/<project-id>` (project overlay, local only)
