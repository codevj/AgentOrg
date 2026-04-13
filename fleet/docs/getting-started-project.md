# Project Setup Guide

Use this when onboarding a new large repository into AgentOrg.

## Step 1: Add project context

Create a project scaffold:

```bash
fleet/scripts/new-project.sh <project-id>
```

Then fill:

- `projects/<project-id>/context/architecture.md`
- `projects/<project-id>/commands/build-test-lint.md`
- `projects/<project-id>/context/domain-glossary.md`

Minimum content:

- architecture map and owned modules
- canonical build/test/lint commands
- common failure points and known quirks

## Step 2: Add project starter task specs

Create:

- `projects/<project-id>/tasks/feature-start.md`
- `projects/<project-id>/tasks/bugfix-start.md`
- `projects/<project-id>/tasks/refactor-start.md`

These should include project-specific validations and constraints.

## Step 3: Select team defaults

Start with:

- `fleet/core/teams/product-delivery.yaml` for code changes
- `fleet/core/teams/docs-enablement.yaml` for docs/process changes

## Step 4: Validate config

```bash
fleet/scripts/validate-team-config.sh fleet/core/teams/product-delivery.yaml
fleet/scripts/resolve-config-order.sh . <project-id>
```

## Step 5: Run first task

```bash
fleet/scripts/generate-run-prompt.sh \
  --mode team \
  --team product-delivery \
  --task projects/<project-id>/tasks/feature-start.md
```
