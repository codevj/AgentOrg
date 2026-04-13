# AgentOrg

Build and run your personal AI organization.

AgentOrg is a workflow-first system for orchestrating single-agent and multi-agent teams across projects, tools, and domains.

## Repository structure

- `fleet/core/` - contracts, modes, personas, policies, teams, templates
- `fleet/docs/` - quickstart, architecture, onboarding, customization
- `fleet/examples/` - runnable solo/team examples
- `fleet/scripts/` - prompt generation and config validation helpers
- `fleet/ux/` - cross-platform product and config model docs
- `projects/` - committed template for local per-project overlays

## First run

```bash
fleet/scripts/quick-task.sh team product-delivery "Your task title"
```

Start from your own task with automatic team validation:

```bash
fleet/scripts/start-task.sh team product-delivery ~/.agent-org/projects/my-project/tasks/feature-start.md
```

Create reusable team/persona:

```bash
fleet/scripts/new-team.sh my-team
fleet/scripts/new-persona.sh domain-expert
```

Or full project workflow:

```bash
fleet/scripts/new-project.sh my-project

fleet/scripts/start-task.sh team product-delivery ~/.agent-org/projects/my-project/tasks/feature-start.md
```

## Vision

Every person can operate like a CEO with an expandable org of agents, while keeping daily usage simple.
