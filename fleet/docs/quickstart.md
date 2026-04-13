# Quickstart

## First run (recommended)

1. Run one quick task immediately:
   ```bash
   fleet/scripts/quick-task.sh team product-delivery "Implement X"
   ```
2. Create your own reusable team:
   ```bash
   fleet/scripts/new-team.sh my-team
   fleet/scripts/validate-team-config.sh fleet/core/teams/my-team.yaml
   ```
3. Add a reusable persona (optional):
   ```bash
   fleet/scripts/new-persona.sh domain-expert
   ```
4. Start any task with one command (auto-validates team config):
   ```bash
   fleet/scripts/start-task.sh team my-team projects/my-project/tasks/feature-start.md
   ```

## Fastest path (single task, no project setup)

```bash
fleet/scripts/quick-task.sh team product-delivery "Implement X"
```

This creates `.tmp/quick-task.md` and prints a ready-to-paste prompt.

## Create a project scaffold

```bash
fleet/scripts/new-project.sh my-project
```

## Team workflow

```bash
fleet/scripts/start-task.sh team product-delivery projects/my-project/tasks/feature-start.md
```

## Solo workflow

```bash
fleet/scripts/start-task.sh solo _ projects/my-project/tasks/bugfix-start.md
```
