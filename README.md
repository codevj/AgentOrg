# AgentOrg

Build AI organizations that learn. Multiple orgs, multiple projects, multiple teams — each getting smarter with every task.

<p align="center">
  <img src="images/agentorg-overview.svg" alt="AgentOrg — teams, projects, intelligence loop, backends" width="850"/>
</p>

```bash
fleet run "Add rate limiting to the API"
```

A PM scopes it. An architect designs it. A developer builds it. A tester and reviewer check it — in parallel. Each role hands off structured artifacts to the next. Quality gates block bad work. And the whole org learns from every run.

## Why

You wouldn't ship code that only one person looked at. Why accept that from AI?

One agent gives you one shot. AgentOrg gives you an organization — roles that plan, build, test, and review each other's work. The reviewer catches what the developer missed. The tester finds edge cases the architect didn't anticipate. Quality gates block bad work from moving forward.

And your org remembers. Every run teaches it something. Your architect learns your codebase. Your reviewer learns your common mistakes. Learnings condense over time — signal stays, noise goes. Run 20 is better than run 1, automatically.

Define your org once. Use it everywhere — Claude Code, Cursor, or Copilot.

- **Multiple perspectives** — an architect catches what a developer misses
- **Quality gates** — a reviewer blocks bad code before it ships
- **Institutional memory** — learnings from past runs make future runs better
- **Parallel execution** — independent roles run simultaneously, not sequentially
- **Different work, different teams** — product delivery for features, strategy analysis for decisions, content production for writing. Switch with one command.
- **Projects remember your codebase** — architecture, build commands, domain terms, failure modes. Fill in once, every task in that project gets the context automatically.
- **Skills are reusable** — code review, risk assessment, deployment procedures. Assign them to roles or keep them project-specific.
- **Personal and work, separated** — multiple orgs with their own roles, knowledge, and history. Your side project doesn't mix with your day job.
- **One command** — `fleet run` handles everything. You watch the team work.

## Install

```bash
# Install uv if you don't have it (https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install AgentOrg (requires Python 3.11+)
uv sync && uv pip install -e .
```

## Get started

```bash
# 1. Initialize (required — all other commands need this first)
fleet init
```

```
Welcome to AgentOrg

Detected backends:
  + claude — Claude Code — native agent teams
  + cursor — Cursor — native subagent support
  - copilot (not installed)

Backend: claude
Default team [product-delivery]:
Reflection mode (auto, review, off) [auto]:

AgentOrg initialized.
  Backend: claude

Next:
  fleet run "your task"
```

```bash
# 2. Run a task
fleet run "Add a /health endpoint"
```

That's it. `fleet run` uses your default team and backend, syncs agents automatically, and executes. Override the team per-run with `--team <id>`, or change the default with `fleet config set team <id>` — see [Context switches](#context-switches). For Claude Code, agents land in `~/.claude/agents/` — available in every project you open.

After the run, `fleet` shows your current context:

```
AgentOrg

  Backend: claude    Project: (none)    Reflection: auto

  Roles: 19    Teams: 6    Skills: 4    Runs: 1

Teams
  product-delivery       program-manager architect developer tester code-reviewer
  content-production     researcher writer editor fact-checker
  ...

Roles
  architect              [starter]  [1 skills]  Produce a minimal, safe implementation design.
  developer              [starter]              Implement approved design with minimal scoped changes.
  ...
```

---

## Three ways to give work

### 1. Quick task — a sentence

```bash
fleet run "Add a /health endpoint that returns uptime and version"
```

Good for small, obvious work. Agents are synced automatically before execution.

### 2. Task spec — a markdown file

For features with scope, constraints, or acceptance criteria, scaffold a spec:

```bash
fleet project task "add rate limiting"
```

This creates a task spec with the right sections:

```
Created: ~/.agent-org/projects/my-api/tasks/add-rate-limiting.md
Edit the spec, then run:
  fleet run ~/.agent-org/projects/my-api/tasks/add-rate-limiting.md
```

The scaffolded spec looks like:

```markdown
# Task: Add Rate Limiting

## Problem
What's wrong or missing? Why does this matter?

## Solution
What should be built? High-level approach.

## Rabbit Holes
- Things to avoid or not over-engineer

## No-gos
- Hard boundaries — what must NOT change

## Acceptance Criteria
- [ ] First criterion
- [ ] Second criterion

## Validation Commands
```bash
# Commands the tester should run
```
```

Fill it in and run:

```bash
fleet run ~/.agent-org/projects/my-api/tasks/add-rate-limiting.md
```

Each section shapes a different role. Architect respects Rabbit Holes. Developer respects No-gos. Tester checks Acceptance Criteria. Reviewer verifies Validation Commands passed.

### 3. Project — persistent codebase context

If you run many tasks against the same codebase, set up a project. Every task automatically gets your codebase context.

```bash
# Create a project (records current directory as the repo)
cd ~/git/my-api
fleet project create my-api

# Activate it
fleet project use my-api

# Now every task includes project context
fleet run "Add rate limiting"
```

Fill in the scaffolded context files once — architecture, domain terms, build commands, known failure modes. The more you fill in, the better every run gets.

See [Projects](#projects) below for details.

See [`agentorg/starters/examples/`](agentorg/starters/examples/) for more task spec examples.

### Natural language (uses your backend LLM)

Don't remember the exact command? Just say what you want:

```bash
fleet "show me all my projects"
fleet "switch to the strategy team"
fleet "what has my org learned"
```

Fleet sends your query to the active backend's LLM, which translates it into the right `fleet` command and runs it. You'll see the translated command before it executes:

```
→ fleet project list
  ...
```

This costs one LLM call per query. For commands you know, use them directly — it's faster and free.

---

## What happens when you run a task

`fleet run` syncs your agents, then hands off to your backend (Claude Code, Cursor, or Copilot). The backend runs the team — fleet doesn't stay in the middle.

```
fleet run "your task"
  → Syncs agents to ~/.claude/agents/ (or ~/.cursor/agents/, ~/.squad/)
  → Launches: claude --agent fleet-product-delivery-lead "your task"
  → Claude Code takes over — you see live output
  → fleet-lead orchestrates the team:

      Stage 1:            PM → scopes the work
      Stage 2:            Architect → designs the implementation
      Stage 3:            Developer → writes code, runs validation
      Stage 4 (parallel): Tester + Reviewer → both run at the same time
      If issues found:    loops back through developer + reviewer

  → Final result: what was done, files changed, how to verify
  → Reflection → learnings saved for next time
```

**Roles run in parallel when they can.** Teams define a dependency graph — roles with the same dependencies run simultaneously. The fleet-lead spawns them using Claude Code's Agent tool, which handles parallel execution natively.

For the best visual experience with parallel agents, enable tmux mode in Claude Code:

```json
// ~/.claude.json
{ "teammateMode": "tmux" }
```

Each role produces a structured **handoff** before the next stage starts. Quality gates enforce that blocked roles stop the pipeline.

---

## Context switches

`fleet config` shows and changes everything that affects how `fleet run` behaves:

```bash
fleet config                               # show current config and context
```

```
  team:              product-delivery
  backend:           claude
  project:           my-api
  org:               default
  reflection:        auto
  condense_after:    5
  org_home:          ~/.agent-org
```

```bash
fleet config set team strategy-analysis    # switch team
fleet config set backend cursor            # switch backend
fleet config set project my-api            # switch project
fleet config set reflection review         # switch reflection mode
fleet config set condense_after 10         # condense learnings every 10 reflections
fleet config clear project                 # deactivate project (one-off mode)
```

Then just work:

```bash
fleet run "do the thing"        # uses all the context above
fleet reflect                   # reflects on active project
fleet learnings                 # shows active org's learnings
```

No flags needed. Override per-run with `--team <id>` or `--solo` when you need a different team for one task.

Use `fleet sync` manually only when you want to update agents without running a task — e.g., after hiring a new role or changing a team.

---

## Concepts

### Projects

A project is the institutional memory of a codebase. Three things make your org smarter about *this specific system*:

- **Context** — architecture, domain glossary, system boundaries. You write this once.
- **Knowledge** — learnings accumulated from running tasks. Grows automatically with every run.
- **Skills** — procedures specific to this codebase. Just create a `SKILL.md` in the project's `skills/` directory.

```bash
fleet project create my-api               # create (records cwd as repo path)
fleet project create my-api --path ~/git/my-api  # or specify the path
fleet project use my-api                  # activate
fleet project clear                       # deactivate (one-off mode)
fleet project list                        # list all
fleet project                             # show active
```

**Multi-repo projects:** a project can span multiple repositories.

```bash
fleet project use payments
fleet project add-repo ~/git/billing-service
fleet project add-repo ~/git/shared-types
```

Creating a project scaffolds:

```
~/.agent-org/projects/my-api/
  project.yaml              ← repo paths
  context/
    architecture.md         ← how the system is structured
    domain-glossary.md      ← terms your team should know
  commands/
    build-test-lint.md      ← what the developer/tester should run
  runbooks/
    common-failures.md      ← known issues and workarounds
  skills/                   ← project-specific procedures (SKILL.md files)
  knowledge/
    learnings.md            ← accumulated from runs (auto-updated)
  tasks/                    ← task specs + run history
```

**Projects are opt-in.** No project active = one-off mode, no project context. Activate one and everything flows.

### What your org knows during a run

```
┌──────────────────────────────────────────────┐
│  Project skills      deploy, run-migrations  │  ← this codebase's playbooks
│  Project knowledge   "auth middleware is..."  │  ← learned from past runs here
│  Project context     architecture, glossary   │  ← you wrote this once
├──────────────────────────────────────────────┤
│  Org knowledge       cross-project patterns   │  ← learned across all projects
│  Role knowledge      role-specific patterns   │  ← learned for this role
│  Role skills         code-review, research    │  ← assigned org-wide skills
│  Role definition     mission, exit criteria   │  ← the persona itself
└──────────────────────────────────────────────┘
```

Switch projects, and the bottom layers stay — the roles bring their general expertise. The top layers change to the memory of *that* codebase.

### Roles

A role defines what an agent does — mission, required inputs, exit criteria, skills.

```bash
fleet hire content-editor                 # create
fleet adopt persona architect             # copy starter for customization
fleet inspect architect                   # view details + knowledge
```

19 starter roles across software, content, strategy, research, ops, and docs.

### Teams

A dependency graph of roles with quality gates. Roles with the same dependencies run in parallel.

```bash
fleet team content-pipeline
```

```yaml
team_id: content-pipeline
roles:
  - id: researcher
  - id: writer
    depends_on: [researcher]
  - id: editor
    depends_on: [writer]
  - id: fact-checker
    depends_on: [writer]       # editor + fact-checker run in parallel
gates:
  reviewer_required: true
  tester_required: false
```

6 starter teams. Flat `personas:` lists (no `depends_on`) still work — they're treated as sequential.

### Skills

Reusable procedural knowledge — how to do code review, risk assessment, research, etc.

```bash
fleet skill                              # list
fleet skill add architect risk-assessment
fleet skill create api-design
```

4 starters: `code-review`, `research`, `risk-assessment`, `fact-checking`.

Project-specific skills go in the project's `skills/` directory as `SKILL.md` files — they're automatically available to all roles when that project is active.

### Intelligence loop

After each run, reflection analyzes what worked and what didn't:

```
Task executes → output saved
  → Reflection analyzes the run
  → Role learnings    → the role gets smarter at its job
  → Project learnings → this codebase's institutional memory grows
  → Org learnings     → cross-project patterns accumulate
  → Role levels updated (starter → practiced → experienced → expert)
  → Next run includes all new knowledge
```

| Layer | What it captures | Example |
|-------|-----------------|---------|
| **Role** | Role-specific patterns | "Validate inputs before handoff" |
| **Project** | Codebase-specific patterns | "Auth middleware has a race condition under load" |
| **Org** | Cross-project patterns | "Vague tasks produce worse output" |

Reflection behavior is configurable:

```bash
fleet config set reflection auto           # default — automatic after every run
fleet config set reflection review         # show learnings for approval before saving
fleet config set reflection off            # no automatic reflection
```

### Backends

Fleet defines the org. The backend runs it. `fleet run` syncs agents and then **hands off to the backend** — fleet doesn't stay in the middle.

```bash
fleet backend                              # show active
fleet backend use copilot                  # switch
fleet backends                             # list all + install status
```

| Backend | Agents written to | How `fleet run` executes |
|---------|------------------|--------------------------|
| **Claude Code** | `~/.claude/agents/fleet-*.md` | `claude --agent fleet-{team}-lead "task"` |
| **Cursor** | `~/.cursor/agents/fleet-*.md` | `cursor --chat` with team prompt |
| **Copilot** | `~/.squad/` | `squad run` or `copilot -p` |

For Claude Code, `fleet run` launches Claude Code interactively with the team lead agent. The lead spawns subagents (one per role), manages handoffs, runs stages in parallel, and produces the final result. You see everything live in your terminal.

Agents are named `fleet-{role}.md` by default. Team leads are `fleet-{team}-lead.md`. If you use multiple orgs, named orgs get `fleet-{org}-{role}.md` to avoid collisions.

### Settings

```bash
fleet config                               # view all
fleet config set default_team strategy-analysis
fleet config set reflection review         # auto, review, or off
```

---

## Starter teams

| Team | Roles | Parallel stages | Domain |
|------|-------|----------------|--------|
| `product-delivery` | PM → Architect → Developer → Tester + Reviewer | Tester & Reviewer | Software |
| `content-production` | Researcher → Writer → Editor + Fact Checker | Editor & Fact Checker | Content |
| `strategy-analysis` | Analyst → Strategist → Critic → Decision Maker | | Strategy |
| `research-synthesis` | Question Framer → Researcher → Synthesizer → Critic | | Research |
| `incident-response` | Triager → Root Cause → Resolution Drafter → Reviewer | | Ops |
| `docs-enablement` | PM → Developer → Docs Reviewer | | Docs |

---

## CLI reference

```
Setup:
  fleet init                                 First-time setup
  fleet config                               View settings
  fleet config set <key> <value>             Change a setting

Context:
  fleet config                               Show all settings and active context
  fleet config set <key> <value>             Set team, backend, project, reflection, org, condense_after
  fleet config clear <key>                   Clear project or org

Projects:
  fleet project create <id> [--path <dir>]   Create a project
  fleet project task <name>                  Scaffold a task spec
  fleet project add-repo <path>              Add a repo to active project
  fleet project list                         List all projects

Status:
  fleet                                      Show org status + active context
  fleet org roles                            List roles
  fleet org teams                            List teams
  fleet org history                          View recent runs
  fleet inspect <role>                       Role details + knowledge
  fleet learnings                            What your org has learned
  fleet backends                             List all backends + install status

Run:
  fleet run <task>                           Execute via active backend
  fleet run --team <id> <task>               Through a specific team
  fleet run --solo <task>                    Single-role
  fleet run path/to/task.md                  From file
  fleet run --prompt <task>                  Output prompt without executing
  fleet summon <role> <task>                 Ask one role

Build:
  fleet hire <id>                            Create role
  fleet team <id>                            Create team
  fleet adopt <persona|team|skill> <id>      Copy starter to customize
  fleet contribute <persona|team|skill> <id> Copy to repo to share

Skills:
  fleet skill                                List org skills
  fleet skill add <role> <skill>             Assign to role
  fleet skill remove <role> <skill>          Remove from role
  fleet skill create <id>                    Create org skill

Sync:
  fleet sync                                 Sync to active backend
  fleet sync <team>                          Sync specific team

Reflect:
  fleet reflect                              Reflect and apply learnings
  fleet reflect --write-back                 Force write-back regardless of mode
  fleet reflect --prompt                     Output reflection prompt only

Advanced:
  fleet org use <name>                       Switch to a named org
  fleet org default                          Switch back to default org
  fleet org list                             List all orgs
```

---

## Where things live

| What | Where |
|------|-------|
| Framework | `agentorg/` |
| Starters | `agentorg/starters/` |
| Settings | `~/.agent-org/settings.yaml` |
| Org data | `~/.agent-org/` (default) or `~/.agent-org/orgs/<name>/` |
| Claude agents | `~/.claude/agents/fleet-*.md` |
| Cursor agents | `~/.cursor/agents/fleet-*.md` |
| Copilot squad | `~/.squad/` |

Inside each org:

| What | Path |
|------|------|
| Roles | `personas/<id>/persona.md` |
| Teams | `teams/<id>.yaml` |
| Skills | `skills/<id>/SKILL.md` |
| Knowledge | `knowledge/` |
| Runs (one-off) | `runs/` |
| Projects | `projects/<id>/` |

Inside each project:

| What | Path |
|------|------|
| Repo paths | `project.yaml` |
| Architecture, glossary | `context/` |
| Build/test/lint commands | `commands/` |
| Known issues, workarounds | `runbooks/` |
| Project-specific procedures | `skills/<id>/SKILL.md` |
| Accumulated learnings | `knowledge/learnings.md` |
| Task specs + run output | `tasks/` |

---

## Development

```bash
git clone https://github.com/codevj/AgentOrg.git && cd AgentOrg && uv sync

uv run pytest                    # all 181 tests (<0.5s)
uv run pytest tests/unit/        # domain + services
uv run pytest tests/e2e/         # CLI + mock exec loop
```

## Architecture

```
agentorg/
  domain/       Pure logic, zero I/O
  ports/        Protocol interfaces
  services/     Orchestration
  adapters/     Filesystem, backends, Jinja2 rendering
  cli/          Click commands
  starters/     Ships with package (read-only)
```

## Contributing

1. Fork, branch, make changes, add tests, `uv run pytest`
2. Keep layers clean: domain → ports → services → adapters → CLI
3. PR
