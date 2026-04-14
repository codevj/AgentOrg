"""CLI entry point — composition root and Click commands."""

from __future__ import annotations

from pathlib import Path

import click

from agentorg.cli import output as o
from agentorg.domain.models import ItemSource
from agentorg.config import (
    Config,
    ReflectionMode,
    get_active_backend,
    get_condense_after,
    get_reflection_mode,
    set_active_backend,
    set_condense_after,
    set_reflection_mode,
)


def _build_context() -> dict:
    """Wire all dependencies. Called once per CLI invocation."""
    from agentorg.config import NotInitializedError
    try:
        config = Config.load()
    except NotInitializedError:
        # Pre-init state: return a placeholder config pointing at a
        # not-yet-created org. The fleet() group init check will route to
        # `fleet init` before any real work runs.
        from agentorg.config import _root_dir
        placeholder = _root_dir() / "orgs" / "__uninitialized__"
        config = Config(
            starters_dir=Path(__file__).resolve().parents[1] / "starters",
            org_home=placeholder,
        )

    # Adapters
    from agentorg.adapters.executor import SubprocessExecutor
    from agentorg.adapters.filesystem.knowledge_store import FileKnowledgeStore
    from agentorg.adapters.filesystem.persona_repo import FilePersonaRepository
    from agentorg.adapters.filesystem.policy_repo import FilePolicyRepository
    from agentorg.adapters.filesystem.run_store import FileRunStore
    from agentorg.adapters.filesystem.skill_repo import FileSkillRepository
    from agentorg.adapters.filesystem.team_repo import FileTeamRepository
    from agentorg.adapters.rendering.jinja_renderer import JinjaRenderer


    persona_repo = FilePersonaRepository(config)
    team_repo = FileTeamRepository(config)
    skill_repo = FileSkillRepository(config)
    policy_repo = FilePolicyRepository(config)
    knowledge_store = FileKnowledgeStore(config)
    run_store = FileRunStore(config)
    renderer = JinjaRenderer(user_dir=config.user_templates_dir)
    executor = SubprocessExecutor()

    # Backends
    from agentorg.adapters.backends.claude import ClaudeBackend
    from agentorg.adapters.backends.copilot import CopilotBackend
    from agentorg.adapters.backends.cursor import CursorBackend
    from agentorg.adapters.backends.registry import BackendRegistry

    # Resolve org_name for backend agent file prefixing.
    # Read .active-org from AGENT_ORG_HOME (tests) or the standard root (users).
    # If it can't be resolved, backends get None — they MUST handle this by
    # erroring before doing anything that needs a name. No silent fallbacks.
    import os as _os
    from pathlib import Path as _Path
    org_name: str | None = None
    # AGENT_ORG_ROOT is always where .active-org lives (tests set it explicitly).
    # AGENT_ORG_HOME points to the active org dir.
    if env_root := _os.environ.get("AGENT_ORG_ROOT"):
        active_file = _Path(env_root) / ".active-org"
        if active_file.is_file():
            org_name = active_file.read_text().strip() or None
    else:
        from agentorg.config import get_active_org
        try:
            org_name = get_active_org()
        except Exception:
            # Not initialized yet — init flow will run before any backend use.
            org_name = None

    backend_kwargs = dict(
        org_name=org_name,
        persona_repo=persona_repo,
        team_repo=team_repo,
        skill_repo=skill_repo,
        knowledge_store=knowledge_store,
        executor=executor,
        contracts_dir=config.contracts_dir,
    )
    registry = BackendRegistry()
    registry.register(ClaudeBackend(renderer=renderer, **backend_kwargs))
    registry.register(CopilotBackend(renderer=renderer, **backend_kwargs))
    registry.register(CursorBackend(renderer=renderer, **backend_kwargs))

    # Services
    from agentorg.services.build_service import BuildService
    from agentorg.services.org_service import OrgService
    from agentorg.services.reflect_service import ReflectService
    from agentorg.services.run_service import RunService
    from agentorg.services.sync_service import SyncService

    reflect_svc = ReflectService(persona_repo, knowledge_store, run_store, renderer)
    run_svc = RunService(
        persona_repo, team_repo, skill_repo, policy_repo, knowledge_store,
        run_store, renderer, reflect_svc,
    )
    org_svc = OrgService(persona_repo, team_repo, skill_repo, knowledge_store, run_store)
    build_svc = BuildService(persona_repo, team_repo, skill_repo, knowledge_store)
    sync_svc = SyncService(registry.as_dict())

    from agentorg.services.project_service import ProjectService

    project_svc = ProjectService(config)

    return {
        "config": config,
        "run_service": run_svc,
        "org_service": org_svc,
        "build_service": build_svc,
        "sync_service": sync_svc,
        "reflect_service": reflect_svc,
        "project_service": project_svc,
        "registry": registry,
    }


class FleetGroup(click.Group):
    """Custom group that routes unrecognized commands to smart dispatch / ask."""

    def resolve_command(self, ctx, args):
        # Try normal command resolution first
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            # Unrecognized command — try smart dispatch (role/team/project/org/skill),
            # else fall back to natural language via `ask`.
            if args and len(args) == 1 and not args[0].startswith("-"):
                # Single-arg form: `fleet <name>` — route to dispatcher.
                return "_dispatch", self.commands["_dispatch"], args
            return "ask", self.commands["ask"], args


_INIT_NOT_REQUIRED = {"init", "ask"}


@click.group(cls=FleetGroup, invoke_without_command=True)
@click.pass_context
def fleet(ctx: click.Context) -> None:
    """AgentOrg — Build and run your AI organization."""
    from agentorg.config import detect_legacy_layout, is_initialized

    ctx.ensure_object(dict)

    # Handle legacy layout migration before anything else
    if not is_initialized() and detect_legacy_layout():
        _migrate_legacy_layout_interactive()

    ctx.obj.update(_build_context())

    # Check if init has been done (skip for init itself and ask)
    config = ctx.obj["config"]
    needs_init = not is_initialized() or not config.settings_file.is_file()
    if ctx.invoked_subcommand not in _INIT_NOT_REQUIRED and needs_init:
        click.echo(o.warn("AgentOrg is not initialized. Run 'fleet init' first."))
        click.echo()
        ctx.invoke(init)
        # After init, rebuild context so downstream commands see fresh config
        ctx.obj.clear()
        ctx.obj.update(_build_context())
        if ctx.invoked_subcommand is None:
            ctx.invoke(status)
        return

    if ctx.invoked_subcommand is None:
        ctx.invoke(status)


def _migrate_legacy_layout_interactive() -> None:
    """Prompt user to migrate a pre-named-org layout into orgs/<name>/."""
    from agentorg.config import migrate_legacy_to_named_org

    click.echo(o.warn("Legacy layout detected at ~/.agent-org/."))
    click.echo("AgentOrg now requires every org to have a name.")
    click.echo()
    import getpass
    default_name = _normalize_org_name(getpass.getuser() or "main")
    name = click.prompt("Name for your existing org", default=default_name)
    name = _normalize_org_name(name)
    target = migrate_legacy_to_named_org(name)
    click.echo(o.success(f"Migrated to: {target}"))
    click.echo()


def _normalize_org_name(name: str) -> str:
    """Normalize an org name — lowercase, hyphen-separated."""
    return name.strip().lower().replace(" ", "-")


def _parse_budget_from_spec(task: str) -> dict | None:
    """Extract budget overrides from a '## Budget' section in a task spec.

    Expected format:
        ## Budget
        max_calls: 20
        reflection: true
        interactions: 5

    Returns None if no Budget section found, else a dict with any of the
    three keys that were present.
    """
    lines = task.splitlines()
    in_budget = False
    result: dict = {}
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## budget"):
            in_budget = True
            continue
        if in_budget:
            # Stop at the next heading
            if stripped.startswith("## ") or stripped.startswith("# "):
                break
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip().lower().replace("-", "_")
                value = value.strip()
                if key == "max_calls":
                    try:
                        result["max_calls"] = int(value)
                    except ValueError:
                        pass
                elif key == "reflection":
                    result["reflection"] = value.lower() in ("true", "yes", "1", "on")
                elif key == "interactions":
                    try:
                        result["interactions"] = int(value)
                    except ValueError:
                        pass
    return result or None


def _env_home_set() -> bool:
    import os as _os
    return bool(_os.environ.get("AGENT_ORG_HOME"))


def _has_active_org_file() -> bool:
    from agentorg.config import _active_org_file
    return _active_org_file().is_file()


def _display_org_name() -> str:
    """Resolve an org name to display. Handles env-override and uninitialized states."""
    from agentorg.config import get_active_org
    if _has_active_org_file():
        try:
            return get_active_org()
        except Exception:
            pass
    if _env_home_set():
        return "(env override)"
    return "(none)"


def _build_cli_reference() -> str:
    """Generate CLI reference dynamically from Click's command registry."""
    lines = []

    def _walk(group, prefix="fleet"):
        for name, cmd in sorted(group.commands.items()):
            if getattr(cmd, "hidden", False):
                continue
            full = f"{prefix} {name}"
            help_text = (cmd.get_short_help_str(limit=60) or "").strip()
            if isinstance(cmd, click.Group):
                lines.append(f"  {full:<45} {help_text}")
                _walk(cmd, full)
            else:
                # Include params
                params = []
                for p in cmd.params:
                    if isinstance(p, click.Argument):
                        params.append(f"<{p.name}>")
                    elif isinstance(p, click.Option) and not p.hidden:
                        params.append(p.opts[0])
                param_str = " ".join(params)
                full_with_params = f"{full} {param_str}".strip()
                lines.append(f"  {full_with_params:<45} {help_text}")

    _walk(fleet)
    return "\n".join(lines)


_FLEET_HELPER_PROMPT = """\
Translate a natural language request into EITHER a complete fleet CLI command OR a help message.

Output exactly ONE line. No reasoning, no markdown fences.

## Decide first: is this a "how do I" / "what is" question, or an action request?

- "how do I create a project" → HELP: fleet project create <project-id>   # then edit ~/.agent-org/.../context files
- "what does fleet run do" → HELP: fleet run <task>   # runs the active team against the task
- "how to switch teams" → HELP: fleet config set team <team-id>

For a HELP answer, start with "HELP: " — do NOT actually run anything.

For an ACTION, the command MUST include all required arguments. If the user didn't supply them, fall back to a HELP response instead.

## Action mappings (when the user has given you what's needed):

- "show/view learnings" → fleet learnings
- "show/view/inspect role X" or "show X learnings" → fleet inspect X
- "list roles" → fleet org roles
- "list teams" → fleet org teams
- "switch to X project" → fleet config set project X
- "switch to X backend" → fleet config set backend X
- "switch to X team" → fleet config set team X
- "create project X" → fleet project create X
- "run/build/implement X" → fleet run "X"
- "show config/context" → fleet config
- "list projects" → fleet project list
- "create task X" → fleet project task "X"

## Rules

- If required arguments are missing, output "HELP: <usage>" — never a bare incomplete command.
- For actions, output just the command (one line, no "fleet" prefix doubled).

Current context:
{context}

Full CLI reference:
{cli_reference}

User request: {query}

Answer:"""


@fleet.command(hidden=True)
@click.argument("query", nargs=-1, required=True)
@click.pass_context
def ask(ctx: click.Context, query: tuple[str, ...]) -> None:
    """Translate natural language to a fleet command and run it."""
    config = ctx.obj["config"]
    sync_svc = ctx.obj["sync_service"]
    proj_svc = ctx.obj["project_service"]
    # Build context string
    active_project = proj_svc.get_active()
    context_lines = [
        f"  team: {config.default_team}",
        f"  backend: {get_active_backend(config)}",
        f"  project: {active_project.id if active_project else '(none)'}",
        f"  reflection: {get_reflection_mode(config).value}",
        f"  org: {_display_org_name()}",
    ]

    query_str = " ".join(query)
    prompt = _FLEET_HELPER_PROMPT.format(
        context="\n".join(context_lines),
        cli_reference=_build_cli_reference(),
        query=query_str,
    )

    # Send prompt to backend (no sync, no team — just a raw LLM call)
    backend_name = get_active_backend(config)
    b = sync_svc.get_backend(backend_name)
    if b is None:
        click.echo(o.error(f"Backend not found: {backend_name}"), err=True)
        raise SystemExit(1)

    try:
        raw_command = b.prompt(prompt).strip()
    except RuntimeError as e:
        click.echo(o.error(f"Could not interpret: {e}"), err=True)
        raise SystemExit(1)

    # Clean up — LLM might wrap in backticks, add explanation, or multi-line
    answer = ""
    for line in raw_command.splitlines():
        line = line.strip().strip("`").strip()
        if not line:
            continue
        # Skip reasoning lines
        if any(line.lower().startswith(w) for w in ("wait", "let me", "actually", "i ", "the ")):
            continue
        answer = line
        break

    if not answer:
        click.echo(o.error(f"Could not translate: {query_str}"), err=True)
        raise SystemExit(1)

    # HELP: response — show usage, don't execute
    if answer.upper().startswith("HELP:"):
        help_text = answer[5:].strip()
        click.echo(o.bold("How to do it:"))
        click.echo(f"  {help_text}")
        return

    # Action — strip redundant 'fleet ' prefix and show the command
    command = answer
    if command.startswith("fleet "):
        command = command[6:]
    click.echo(f"→ fleet {command}")


# ── Dispatcher: fleet <name> ──

def _edit_file(path: Path) -> bool:
    """Open a file in $EDITOR (fall back to nano). Returns True if opened."""
    import os as _os
    editor = _os.environ.get("EDITOR") or "nano"
    try:
        click.edit(filename=str(path), editor=editor)
        return True
    except click.UsageError as e:
        click.echo(o.error(f"Could not open editor: {e}"), err=True)
        return False


def _show_role_details(ctx: click.Context, role_id: str) -> int:
    org = ctx.obj["org_service"]
    data = org.inspect_persona(role_id)
    if data is None:
        return 1
    lc = o.level_color(data["level"])
    click.echo()
    level_val = data["level"].value
    click.echo(f"{o.bold(data['id'])} {click.style(f'[{level_val}]', fg=lc)}")
    click.echo(o.dim(data["mission"]))
    click.echo()
    click.echo(f"  Source: {data['source'].value}")
    click.echo(f"  Skills: {', '.join(data['skill_ids']) or o.dim('none')}")
    click.echo(f"  Teams:  {', '.join(data['teams']) or o.dim('none')}")
    click.echo()
    if data['has_knowledge'] and data.get('knowledge_preview'):
        click.echo(o.bold("  Learnings"))
        for line in data['knowledge_preview'].strip().splitlines():
            click.echo(f"  {line}")
    else:
        click.echo(o.dim("  No learnings yet."))
    click.echo()
    return 0


def _show_team_details(ctx: click.Context, team_id: str) -> int:
    build = ctx.obj["build_service"]
    team = build._teams.get(team_id)
    if team is None:
        return 1
    source = build._teams.source(team_id)
    click.echo()
    click.echo(f"{o.bold(team_id)} {o.dim(f'[{team.governance_profile}]')}")
    click.echo()
    click.echo(f"  Source:     {source.value}")
    click.echo(f"  Mode:       {team.mode_default.value}")
    click.echo(f"  Execution:  {team.execution_profile}")
    click.echo(f"  Roles:      {' → '.join(team.persona_ids)}")
    click.echo(f"  Gates:      reviewer={team.gates.reviewer_required} tester={team.gates.tester_required}")
    click.echo(f"  Budget:     max_calls={team.budget.max_calls} reflection={team.budget.reflection} interactions={team.budget.interactions}")
    stages = team.execution_stages()
    if stages:
        click.echo()
        click.echo(o.bold("  Stages"))
        for i, stage in enumerate(stages, 1):
            marker = "⚡" if len(stage) > 1 else " "
            click.echo(f"    {i}: {marker} {', '.join(stage)}")
    click.echo()
    return 0


def _show_project_details(ctx: click.Context, project_id: str) -> int:
    proj_svc = ctx.obj["project_service"]
    p = proj_svc.get(project_id)
    if p is None:
        return 1
    active = proj_svc.get_active()
    is_active = active is not None and active.id == p.id
    click.echo()
    marker = " " + click.style("(active)", fg="green") if is_active else ""
    click.echo(f"{o.bold(p.id)}{marker}")
    click.echo(o.dim(f"  {p.root}"))
    click.echo()
    if p.repo_paths:
        click.echo(o.bold("  Repos"))
        for rp in p.repo_paths:
            click.echo(f"    {rp}")
    else:
        click.echo(o.dim("  No repos attached. Use: fleet project add-repo <path>"))
    click.echo()
    # Context files
    context_dir = p.root / "context"
    if context_dir.is_dir():
        files = sorted(context_dir.glob("*.md"))
        if files:
            click.echo(o.bold("  Context"))
            for f in files:
                click.echo(f"    {f.name}")
            click.echo()
    tasks_dir = p.root / "tasks"
    if tasks_dir.is_dir():
        specs = sorted(tasks_dir.glob("*.md"))
        if specs:
            click.echo(o.bold("  Tasks"))
            for f in specs:
                click.echo(f"    {f.name}")
            click.echo()
    return 0


def _show_org_details(ctx: click.Context, name: str) -> int:
    from agentorg.config import list_orgs
    orgs = list_orgs()
    if name not in orgs:
        return 1
    active = _display_org_name()
    marker = " " + click.style("(active)", fg="green") if name == active else ""
    click.echo()
    click.echo(f"{o.bold(name)}{marker}")
    click.echo(o.dim(f"  Switch with: fleet org use {name}"))
    click.echo()
    return 0


def _show_skill_details(ctx: click.Context, skill_id: str) -> int:
    skill_repo = ctx.obj["build_service"]._skills
    persona_repo = ctx.obj["build_service"]._personas
    s = skill_repo.get(skill_id)
    if s is None:
        return 1
    click.echo()
    click.echo(o.bold(s.metadata.name or s.id))
    click.echo(o.dim(s.metadata.description))
    click.echo()
    click.echo(s.body)
    click.echo()
    click.echo(o.bold("Used by:"))
    found = False
    for pid in persona_repo.list_ids():
        p = persona_repo.get(pid)
        if p and skill_id in p.skill_ids:
            click.echo(f"  - {pid}")
            found = True
    if not found:
        click.echo(o.dim(f"  (none — use 'fleet skill add-to-role <persona> {skill_id}')"))
    click.echo()
    return 0


@fleet.command("_dispatch", hidden=True)
@click.argument("name", nargs=-1, required=True)
@click.pass_context
def _dispatch(ctx: click.Context, name: tuple[str, ...]) -> None:
    """Smart dispatcher for `fleet <name>` — resolves to role/team/project/org/skill."""
    target = " ".join(name).strip()
    build = ctx.obj["build_service"]
    proj_svc = ctx.obj["project_service"]

    # 1. role
    if build._personas.exists(target):
        if _show_role_details(ctx, target) == 0:
            return
    # 2. team
    if build._teams.exists(target):
        if _show_team_details(ctx, target) == 0:
            return
    # 3. project
    if proj_svc.get(target) is not None:
        if _show_project_details(ctx, target) == 0:
            return
    # 4. org
    from agentorg.config import list_orgs
    if target in list_orgs():
        if _show_org_details(ctx, target) == 0:
            return
    # 5. skill
    if build._skills.exists(target):
        if _show_skill_details(ctx, target) == 0:
            return

    # Fall through to natural-language ask
    ctx.invoke(ask, query=name)


# ── Init + Config ──

@fleet.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Set up AgentOrg for first use."""
    from agentorg.config import (
        is_initialized,
        save_settings,
        set_active_org,
    )

    config = ctx.obj["config"]

    # If already initialized with a real org and settings.yaml, bail.
    if is_initialized() and config.settings_file.is_file():
        click.echo(o.dim(f"Settings already exist: {config.settings_file}"))
        click.echo(o.dim("Use 'fleet config' to view or change settings."))
        return

    click.echo(o.bold("Welcome to AgentOrg"))
    click.echo()

    # Prompt for org name (default: username)
    import getpass
    default_name = _normalize_org_name(getpass.getuser() or "main")
    org_name_input = click.prompt(
        "Name your first org",
        default=default_name,
    )
    org_name = _normalize_org_name(org_name_input)

    # Create the org directory and mark it active BEFORE loading settings,
    # so the settings file lands in the right place.
    import os as _os
    if not _os.environ.get("AGENT_ORG_HOME"):
        set_active_org(org_name)
        # Reload config so org_home points to the new org dir
        config = Config.load()
        ctx.obj["config"] = config

    if config.settings_file.is_file():
        click.echo(o.dim(f"Settings already exist: {config.settings_file}"))
        click.echo(o.dim("Use 'fleet config' to view or change settings."))
        return

    # Detect available backends
    sync_svc = ctx.obj["sync_service"]
    all_backends = sync_svc.list_backends()
    installed = [b for b in all_backends if b.installed]
    not_installed = [b for b in all_backends if not b.installed]

    if installed:
        click.echo("Detected backends:")
        for b in installed:
            click.echo(f"  {click.style('+', fg='green')} {b.name} — {b.description}")
        if not_installed:
            for b in not_installed:
                click.echo(f"  {o.dim(f'- {b.name} (not installed)')}")
        click.echo()
    else:
        click.echo(o.warn("No backends detected."))
        click.echo("Install at least one: Claude Code, Cursor, or Copilot.")
        click.echo()

    # Pick backend
    installed_names = [b.name for b in installed]
    default_backend = installed_names[0] if installed_names else config.default_backend

    if len(installed_names) == 1:
        backend = installed_names[0]
        click.echo(f"Backend: {o.bold(backend)}")
    else:
        backend = click.prompt(
            f"Backend ({', '.join(b.name for b in all_backends)})",
            default=default_backend,
        )
        if backend not in [b.name for b in all_backends]:
            click.echo(o.warn(f"Unknown backend: {backend}. Using {default_backend}."))
            backend = default_backend
        if backend not in installed_names:
            click.echo(o.warn(f"'{backend}' is not installed. You'll need to install it before running tasks."))

    # Default team
    default_team = click.prompt(
        "Default team",
        default=config.default_team,
    )

    # Reflection mode
    reflection = click.prompt(
        "Reflection mode (auto, review, off)",
        default="auto",
    )
    try:
        ReflectionMode(reflection)
    except ValueError:
        reflection = "auto"

    # Condense threshold
    condense_after_str = click.prompt(
        "Condense learnings after N reflections (0 = disabled)",
        default="5",
    )
    try:
        condense_after_val = int(condense_after_str)
    except ValueError:
        condense_after_val = 5

    # Scratch dir — where tasks run when no project is active
    default_scratch = str(Path(config.org_home).expanduser() / "scratch")
    scratch = click.prompt(
        "Scratch directory (where tasks run without an active project)",
        default=default_scratch,
    )

    from pathlib import Path as _Path
    new_config = Config(
        starters_dir=config.starters_dir,
        org_home=_Path(config.org_home).expanduser(),
        default_backend=backend,
        default_team=default_team,
        reflection=reflection,
    )
    save_settings(new_config)
    set_condense_after(new_config, condense_after_val)
    from agentorg.config import set_scratch_dir
    set_scratch_dir(new_config, scratch)

    # Create directories
    new_config.org_home.mkdir(parents=True, exist_ok=True)

    # Set active backend
    from agentorg.config import set_active_backend
    set_active_backend(new_config, backend)

    click.echo()
    click.echo(o.success("AgentOrg initialized."))
    click.echo(f"  Backend: {backend}")
    click.echo(o.dim(f"  Settings: {new_config.settings_file}"))
    click.echo()
    click.echo("Next:")
    click.echo(f"  fleet run --team {default_team} \"your task\"")


@fleet.group(invoke_without_command=True, name="config")
@click.pass_context
def config_cmd(ctx: click.Context) -> None:
    """View or change settings and active context."""
    if ctx.invoked_subcommand is None:
        config = ctx.obj["config"]

        active_backend = get_active_backend(config)
        proj_svc = ctx.obj["project_service"]
        active_project = proj_svc.get_active()
        active_org_name = _display_org_name()
        mode = get_reflection_mode(config)
        condense = get_condense_after(config)
        from agentorg.config import get_scratch_dir
        scratch = get_scratch_dir(config)

        click.echo()
        click.echo(o.bold("Settings") + "  " + o.dim(str(config.settings_file)))
        click.echo()
        click.echo(f"  team:              {o.bold(config.default_team)}")
        click.echo(f"  backend:           {o.bold(active_backend)}")
        project_str = o.bold(active_project.id) if active_project else o.dim("(none)")
        click.echo(f"  project:           {project_str}")
        click.echo(f"  org:               {o.bold(active_org_name)}")
        click.echo(f"  reflection:        {mode.value}")
        click.echo(f"  condense_after:    {condense}")
        click.echo(f"  scratch_dir:       {scratch}")
        click.echo(f"  org_home:          {config.org_home}")
        click.echo()
        if not config.settings_file.is_file():
            click.echo(o.dim("  No settings file yet. Run 'fleet init' to create one."))
            click.echo()


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set a configuration value (team, backend, project, reflection, org, condense_after, org_home)."""
    from agentorg.config import save_settings

    config = ctx.obj["config"]
    valid_keys = {
        "team", "default_team", "backend", "default_backend",
        "project", "reflection", "org", "condense_after", "scratch_dir", "org_home",
    }

    if key not in valid_keys:
        click.echo(o.error(f"Unknown key: {key}. Valid: {', '.join(sorted(valid_keys))}"), err=True)
        raise SystemExit(1)

    # team / default_team
    if key in ("team", "default_team"):
        # Validate team exists
        team_repo = ctx.obj["build_service"]._teams
        if not team_repo.exists(value):
            click.echo(o.error(f"Team not found: {value}"), err=True)
            raise SystemExit(1)
        from pathlib import Path as _Path
        new_config = Config(
            starters_dir=config.starters_dir,
            org_home=_Path(config.org_home),
            default_backend=config.default_backend,
            default_team=value,
            reflection=config.reflection,
        )
        save_settings(new_config)
        click.echo(o.success(f"team = {value}"))

    # backend / default_backend
    elif key in ("backend", "default_backend"):
        sync_svc = ctx.obj["sync_service"]
        known = [info.name for info in sync_svc.list_backends()]
        if value not in known:
            click.echo(o.error(f"Unknown backend: {value}. Available: {', '.join(known)}"), err=True)
            raise SystemExit(1)
        set_active_backend(config, value)
        click.echo(o.success(f"backend = {value}"))

    # project
    elif key == "project":
        proj_svc = ctx.obj["project_service"]
        try:
            proj_svc.activate(value)
            click.echo(o.success(f"project = {value}"))
        except ValueError as e:
            click.echo(o.error(str(e)), err=True)
            raise SystemExit(1)

    # reflection
    elif key == "reflection":
        try:
            mode = ReflectionMode(value)
        except ValueError:
            click.echo(o.error(f"Invalid reflection mode: {value}. Use: auto, review, off"), err=True)
            raise SystemExit(1)
        set_reflection_mode(config, mode)
        click.echo(o.success(f"reflection = {value}"))

    # org
    elif key == "org":
        from agentorg.config import set_active_org
        set_active_org(value)
        click.echo(o.success(f"org = {value}"))
        click.echo(o.dim("Restart fleet for the change to take effect."))

    # condense_after
    elif key == "condense_after":
        try:
            int_val = int(value)
        except ValueError:
            click.echo(o.error(f"condense_after must be an integer, got: {value}"), err=True)
            raise SystemExit(1)
        if int_val < 0:
            click.echo(o.error("condense_after must be non-negative"), err=True)
            raise SystemExit(1)
        set_condense_after(config, int_val)
        click.echo(o.success(f"condense_after = {int_val}"))

    # scratch_dir
    elif key == "scratch_dir":
        from agentorg.config import set_scratch_dir
        set_scratch_dir(config, value)
        click.echo(o.success(f"scratch_dir = {value}"))

    # org_home
    elif key == "org_home":
        from pathlib import Path as _Path
        new_config = Config(
            starters_dir=config.starters_dir,
            org_home=_Path(value).expanduser(),
            default_backend=config.default_backend,
            default_team=config.default_team,
            reflection=config.reflection,
        )
        save_settings(new_config)
        click.echo(o.success(f"org_home = {value}"))


@config_cmd.command("clear")
@click.argument("key", type=click.Choice(["project"]))
@click.pass_context
def config_clear(ctx: click.Context, key: str) -> None:
    """Clear a context value (project only — orgs are always named)."""
    if key == "project":
        ctx.obj["project_service"].deactivate()
        click.echo(o.success("project cleared — running in one-off mode."))


# ── Status ──

@fleet.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show org status — roles, teams, runs."""
    org = ctx.obj["org_service"]
    s = org.status()
    config = ctx.obj["config"]

    active_backend = get_active_backend(config)
    active_org_name = _display_org_name()
    mode = get_reflection_mode(config)

    proj_svc = ctx.obj["project_service"]
    active_project = proj_svc.get_active()
    project_str = active_project.id if active_project else o.dim("(none)")
    org_str = active_org_name

    click.echo()
    click.echo(o.bold("AgentOrg"))
    click.echo()
    click.echo(
        f"  Backend: {active_backend}        "
        f"Project: {project_str}        "
        f"Org: {org_str}        "
        f"Reflection: {mode.value}"
    )
    click.echo(
        f"  Roles: {s.persona_count}    Teams: {s.team_count}    "
        f"Skills: {s.skill_count}    Runs: {s.run_count}"
    )
    click.echo()

    click.echo(o.bold("Teams"))
    for tv in org.list_teams():
        personas = " ".join(tv.persona_ids)
        click.echo(f"  {o.bold(tv.id):<30} {o.dim(f'[{tv.governance_profile}]'):<20} {personas}{o.source_tag(tv.source)}")
    click.echo()

    click.echo(o.bold("Roles"))
    for pv in org.list_personas():
        lc = o.level_color(pv.level)
        level_str = click.style(f"[{pv.level.value}]", fg=lc)
        skills = o.dim(f" [{pv.skill_count} skills]") if pv.skill_count else ""
        click.echo(f"  {o.bold(pv.id):<30} {level_str:<20}{skills}{o.source_tag(pv.source)} {o.dim(pv.mission)}")
    click.echo()


# ── Run ──

@fleet.command()
@click.argument("task", nargs=-1, required=False)
@click.option("--team", "-t", default=None, help="Team to run through")
@click.option("--role", "role_id", default=None, help="Single role to execute (replaces 'summon')")
@click.option("--project", "-p", "project_arg", default=None,
              help="Project to run in (creates it if missing, cwd as repo path)")
@click.option("--solo", is_flag=True, help="Single-role execution")
@click.option("--prompt", "prompt_only", is_flag=True, help="Output the prompt without executing")
@click.option("--budget", "budget_calls", type=int, default=None,
              help="Override max_calls budget for this run")
@click.option("--no-reflect", is_flag=True, help="Skip reflection for this run")
@click.option("--new", "new_spec", default=None,
              help="Scaffold a task spec in the active project, then run it.")
@click.option("--no-run", is_flag=True,
              help="With --new: scaffold only, don't run the task.")
@click.pass_context
def run(ctx: click.Context, task: tuple[str, ...], team: str | None, role_id: str | None,
        project_arg: str | None, solo: bool,
        prompt_only: bool, budget_calls: int | None, no_reflect: bool,
        new_spec: str | None, no_run: bool) -> None:
    """Run a task through your org."""
    run_svc = ctx.obj["run_service"]

    # --new: scaffold a task spec in the active project, optionally run it.
    if new_spec:
        proj_svc = ctx.obj["project_service"]
        try:
            task_file = proj_svc.create_task(new_spec)
        except ValueError as e:
            click.echo(o.error(str(e)), err=True)
            raise SystemExit(1)
        click.echo(o.success(f"Created: {task_file}"))
        _edit_file(task_file)
        if no_run:
            return
        if not click.confirm("Run this task now?", default=True):
            return
        task = (str(task_file),)

    if not task:
        click.echo(o.error("Missing task. Usage: fleet run <task> [--role <id>] [--team <id>] [--new <name>]"), err=True)
        raise SystemExit(1)

    task_str = " ".join(task)

    # --role: single-role execution (replaces `fleet summon`).
    if role_id:
        proj_svc = ctx.obj["project_service"]
        active_project = proj_svc.get_active()
        project_root = active_project.root if active_project else None
        try:
            prompt = run_svc.build_summon_prompt(role_id, task_str, project_root=project_root)
        except ValueError as e:
            click.echo(o.error(str(e)), err=True)
            raise SystemExit(1)
        if prompt_only:
            click.echo(prompt)
            return
        backend_name = get_active_backend(ctx.obj["config"])
        sync_svc = ctx.obj["sync_service"]
        b = sync_svc.get_backend(backend_name)
        if b is None:
            click.echo(o.error(f"Backend not found: {backend_name}"), err=True)
            raise SystemExit(1)
        try:
            output = b.execute("summon", prompt, "summon")
        except RuntimeError as e:
            click.echo(o.error(f"Execution failed: {e}"), err=True)
            raise SystemExit(1)
        click.echo(output)
        return

    # If the task is a file path, read its content as the task
    task_path = Path(task_str)
    if task_path.is_file():
        task_str = task_path.read_text()

    # Parse budget override from task spec if present
    spec_budget = _parse_budget_from_spec(task_str)

    # Build the budget override: CLI flag > spec > team default
    budget_override = None
    if budget_calls is not None or spec_budget or no_reflect:
        from agentorg.domain.models import Budget
        # Start from spec values, then apply CLI flags
        base = spec_budget or {}
        budget_override = Budget(
            max_calls=budget_calls if budget_calls is not None else base.get("max_calls", 15),
            reflection=(not no_reflect) and base.get("reflection", True),
            interactions=base.get("interactions", 3),
        )

    # Resolve project: --project arg wins; else the active project.
    # If --project names one that doesn't exist, create it with cwd as the repo.
    proj_svc = ctx.obj["project_service"]
    if project_arg:
        proj = proj_svc.get(project_arg)
        if proj is None:
            click.echo(o.dim(f"Project '{project_arg}' not found — creating with {Path.cwd()} as repo path..."), err=True)
            try:
                proj = proj_svc.create(project_arg, repo_path=Path.cwd())
                click.echo(o.success(f"Created project: {project_arg}"), err=True)
            except ValueError as e:
                click.echo(o.error(str(e)), err=True)
                raise SystemExit(1)
        active_project = proj
    else:
        active_project = proj_svc.get_active()
    project_root = active_project.root if active_project else None
    project_id = active_project.id if active_project else None

    if prompt_only:
        if solo:
            prompt = run_svc.build_solo_prompt(task_str, project_root=project_root)
        else:
            prompt = run_svc.build_team_prompt(team or ctx.obj["config"].default_team, task_str, project_root=project_root)
        click.echo(prompt)
    else:
        backend_name = get_active_backend(ctx.obj["config"])
        sync_svc = ctx.obj["sync_service"]
        b = sync_svc.get_backend(backend_name)
        if b is None:
            click.echo(o.error(f"Backend not found: {backend_name}"), err=True)
            raise SystemExit(1)

        mode = get_reflection_mode(ctx.obj["config"])
        team_id = team or ctx.obj["config"].default_team
        condense = get_condense_after(ctx.obj["config"])

        # Resolve workdir: project's repos if a project is active, else scratch_dir
        from agentorg.config import get_scratch_dir
        project_repo_paths = active_project.repo_paths if active_project and active_project.repo_paths else None
        scratch = get_scratch_dir(ctx.obj["config"])
        workdir = project_repo_paths[0] if project_repo_paths else scratch

        # Pre-flight: adopt starters so the user sees everything we'll use.
        # Do this BEFORE handing off to the backend so the messages appear up front.
        if not solo and team_id:
            build = ctx.obj["build_service"]
            adopted_team = build.adopt_team_if_missing(team_id)
            team_obj = build._teams.get(team_id)
            adopted_personas = []
            if team_obj:
                for pid in team_obj.persona_ids:
                    if build.adopt_persona_if_missing(pid):
                        adopted_personas.append(pid)
            if adopted_team:
                click.echo(
                    o.success(f"Copied team '{team_id}' to your org (teams/{team_id}.yaml) for editing."),
                    err=True,
                )
            if adopted_personas:
                click.echo(
                    o.success(f"Copied personas to your org for editing: {', '.join(adopted_personas)}"),
                    err=True,
                )

        # Print full run context so the user can see what's happening.
        click.echo(o.bold("Run context"), err=True)
        click.echo(f"  backend:  {backend_name}", err=True)
        click.echo(f"  team:     {team_id}", err=True)
        if team_obj := (ctx.obj["build_service"]._teams.get(team_id) if team_id else None):
            click.echo(f"  roles:    {' → '.join(team_obj.persona_ids)}", err=True)
            stages = team_obj.execution_stages()
            for i, stage in enumerate(stages, 1):
                marker = "⚡" if len(stage) > 1 else " "
                click.echo(f"  stage {i}: {marker} {', '.join(stage)}", err=True)
        if active_project:
            click.echo(f"  project:  {active_project.id}", err=True)
        click.echo(f"  workdir:  {workdir}", err=True)
        click.echo(o.dim("  Handing off to backend..."), err=True)
        click.echo()

        try:
            result = run_svc.execute(
                backend=b, team_id=team_id, task=task_str, solo=solo,
                reflection_mode=mode,
                project_root=project_root,
                project_id=project_id,
                project_repo_paths=project_repo_paths,
                scratch_dir=scratch,
                condense_after=condense,
                budget_override=budget_override,
            )
        except RuntimeError as e:
            click.echo(o.error(f"Execution failed: {e}"), err=True)
            raise SystemExit(1)
        if result.output:
            click.echo(result.output)
        click.echo(o.success("Run complete.") + f" {o.dim(result.budget_summary)}", err=True)


# ── Skills ──

@fleet.group(invoke_without_command=True)
@click.pass_context
def skill(ctx: click.Context) -> None:
    """Manage skills."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(skill_list)


@skill.command("list")
@click.pass_context
def skill_list(ctx: click.Context) -> None:
    """List all available skills."""
    skill_repo = ctx.obj["build_service"]._skills
    click.echo()
    click.echo(o.bold("Skills"))
    click.echo()
    for sid in skill_repo.list_ids():
        s = skill_repo.get(sid)
        if s:
            desc = s.metadata.description or ""
            click.echo(f"  {o.bold(sid):<25} {o.dim(desc)}")
    click.echo()


@skill.command("create")
@click.argument("skill_id")
@click.pass_context
def skill_create(ctx: click.Context, skill_id: str) -> None:
    """Create a new skill."""
    build = ctx.obj["build_service"]
    try:
        s = build.create_skill(skill_id)
        click.echo(o.success(f"Created skill: {skill_id}"))
        click.echo(o.dim(f"Stored at: {ctx.obj['config'].user_skills_dir / skill_id}"))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@skill.command("edit")
@click.argument("skill_id")
@click.pass_context
def skill_edit(ctx: click.Context, skill_id: str) -> None:
    """Open a skill's SKILL.md in $EDITOR."""
    config = ctx.obj["config"]
    build = ctx.obj["build_service"]
    if not build._skills.exists(skill_id):
        click.echo(o.error(f"Skill not found: {skill_id}"), err=True)
        raise SystemExit(1)
    # Prefer user-level file; if starter-only, adopt by copying first.
    user_path = config.user_skills_dir / skill_id / "SKILL.md"
    if not user_path.is_file():
        starter_path = config.starter_skills_dir / skill_id / "SKILL.md"
        if starter_path.is_file():
            user_path.parent.mkdir(parents=True, exist_ok=True)
            user_path.write_text(starter_path.read_text())
            click.echo(o.dim(f"Copied starter to your org for editing: {user_path}"), err=True)
    _edit_file(user_path)


@skill.command("remove")
@click.argument("skill_id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def skill_delete(ctx: click.Context, skill_id: str, yes: bool) -> None:
    """Remove a skill from your local org (starters untouched)."""
    import shutil
    config = ctx.obj["config"]
    user_dir = config.user_skills_dir / skill_id
    if not user_dir.is_dir():
        click.echo(o.error(f"Skill not in your org: {skill_id}"), err=True)
        raise SystemExit(1)
    if not yes and not click.confirm(f"Remove skill '{skill_id}' from your org?"):
        click.echo("Aborted.")
        return
    shutil.rmtree(user_dir)
    click.echo(o.success(f"Removed: {skill_id}"))


@skill.command("add-to-role")
@click.argument("role_id")
@click.argument("skill_id")
@click.pass_context
def skill_add_to_role(ctx: click.Context, role_id: str, skill_id: str) -> None:
    """Attach a skill to a role."""
    build = ctx.obj["build_service"]
    try:
        build.add_skill_to_persona(role_id, skill_id)
        click.echo(o.success(f"Added '{skill_id}' to {role_id}"))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@skill.command("remove-from-role")
@click.argument("role_id")
@click.argument("skill_id")
@click.pass_context
def skill_remove_from_role(ctx: click.Context, role_id: str, skill_id: str) -> None:
    """Detach a skill from a role."""
    build = ctx.obj["build_service"]
    try:
        build.remove_skill_from_persona(role_id, skill_id)
        click.echo(o.success(f"Removed '{skill_id}' from {role_id}"))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@skill.command("adopt")
@click.argument("skill_id")
@click.pass_context
def skill_adopt(ctx: click.Context, skill_id: str) -> None:
    """Copy a starter skill to your org for editing."""
    build = ctx.obj["build_service"]
    config = ctx.obj["config"]
    if build._skills.source(skill_id) == ItemSource.USER:
        click.echo(o.error(f"Already in your org: {skill_id}"), err=True)
        raise SystemExit(1)
    s = build._skills.get(skill_id)
    if s is None:
        click.echo(o.error(f"Starter not found: {skill_id}"), err=True)
        raise SystemExit(1)
    build._skills.save_to_user(s)
    click.echo(o.success(f"Adopted: {skill_id}"))
    click.echo(o.dim(f"Stored at: {config.user_skills_dir / skill_id}"))


@skill.command("contribute")
@click.argument("skill_id")
@click.pass_context
def skill_contribute(ctx: click.Context, skill_id: str) -> None:
    """Copy a skill from your org to the repo for sharing."""
    build = ctx.obj["build_service"]
    try:
        build.contribute_skill(skill_id)
        click.echo(o.success(f"Contributed: {skill_id}"))
        click.echo(o.dim("Now commit to share with your team."))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


# ── Sync ──

@fleet.command()
@click.argument("team_id", required=False)
@click.pass_context
def sync(ctx: click.Context, team_id: str | None) -> None:
    """Sync org to the active backend's user-level agent directory."""
    sync_svc = ctx.obj["sync_service"]
    backend_name = get_active_backend(ctx.obj["config"])
    try:
        count = sync_svc.sync(backend_name, team_id)
        info = sync_svc.get_backend(backend_name).info()
        click.echo(o.success(f"Synced {count} agent(s) to {backend_name}.") + f" {o.dim(info.agent_dir)}", err=True)
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)
    except RuntimeError as e:
        click.echo(o.error(f"Sync failed: {e}"), err=True)
        raise SystemExit(1)


# ── Org ──

def _print_roles_section(ctx: click.Context) -> None:
    org_svc = ctx.obj["org_service"]
    click.echo(o.bold("Roles"))
    for pv in org_svc.list_personas():
        lc = o.level_color(pv.level)
        click.echo(f"  {o.bold(pv.id):<30} {click.style(f'[{pv.level.value}]', fg=lc):<20}{o.source_tag(pv.source)} {o.dim(pv.mission)}")


def _print_teams_section(ctx: click.Context) -> None:
    org_svc = ctx.obj["org_service"]
    click.echo(o.bold("Teams"))
    for tv in org_svc.list_teams():
        click.echo(f"  {o.bold(tv.id):<30} {o.dim(f'[{tv.governance_profile}]'):<20} {' '.join(tv.persona_ids)}{o.source_tag(tv.source)}")


def _print_history_section(ctx: click.Context) -> None:
    run_store = ctx.obj["run_service"]._runs
    runs = run_store.list_recent(count=10)
    click.echo(o.bold("Run History"))
    if not runs:
        click.echo(o.dim("  No runs yet."))
    else:
        for run in runs:
            team_str = run.team_id or "solo"
            click.echo(f"  {o.dim(run.id):<30} {team_str:<22} {run.status.value}")


@fleet.group(invoke_without_command=True)
@click.pass_context
def org(ctx: click.Context) -> None:
    """Manage organizations (overview shows roles, teams, and recent runs)."""
    if ctx.invoked_subcommand is None:
        click.echo()
        click.echo(o.bold(f"Org: {_display_org_name()}"))
        click.echo()
        _print_roles_section(ctx)
        click.echo()
        _print_teams_section(ctx)
        click.echo()
        _print_history_section(ctx)
        click.echo()


@org.command("create")
@click.argument("name")
@click.pass_context
def org_create(ctx: click.Context, name: str) -> None:
    """Create a new org (and switch to it)."""
    from agentorg.config import set_active_org
    normalized = _normalize_org_name(name)
    org_dir = set_active_org(normalized)
    click.echo(o.success(f"Created and switched to org: {normalized}"))
    click.echo(o.dim(f"Data: {org_dir}"))


@org.command("list")
@click.pass_context
def org_list(ctx: click.Context) -> None:
    """List all named orgs."""
    from agentorg.config import list_orgs
    active = _display_org_name()
    orgs = list_orgs()
    click.echo()
    click.echo(o.bold("Orgs"))
    click.echo()
    if not orgs:
        click.echo(o.dim("  No orgs yet. Run 'fleet init' to create one."))
    for name in orgs:
        marker = " " + click.style("(active)", fg="green") if name == active else ""
        click.echo(f"  {name}{marker}")
    click.echo()


@org.command("edit")
@click.argument("name")
@click.pass_context
def org_edit(ctx: click.Context, name: str) -> None:
    """Open the org's settings.yaml in $EDITOR."""
    from agentorg.config import _root_dir
    settings_path = _root_dir() / "orgs" / name / "settings.yaml"
    if not settings_path.is_file():
        click.echo(o.error(f"Org settings not found: {settings_path}"), err=True)
        raise SystemExit(1)
    _edit_file(settings_path)


@org.command("use")
@click.argument("name")
@click.pass_context
def org_use(ctx: click.Context, name: str) -> None:
    """Switch to a named org."""
    from agentorg.config import set_active_org
    org_dir = set_active_org(name)
    click.echo(o.success(f"Switched to org: {name}"))
    click.echo(o.dim(f"Data: {org_dir}"))


@org.command("remove")
@click.argument("name")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def org_remove(ctx: click.Context, name: str, yes: bool) -> None:
    """Delete an org directory (irreversible)."""
    import shutil
    from agentorg.config import _root_dir
    org_dir = _root_dir() / "orgs" / name
    if not org_dir.is_dir():
        click.echo(o.error(f"Org not found: {name}"), err=True)
        raise SystemExit(1)
    if name == _display_org_name():
        click.echo(o.error(f"Cannot remove active org: {name}. Switch first."), err=True)
        raise SystemExit(1)
    if not yes and not click.confirm(f"Remove org '{name}' and all its data at {org_dir}?"):
        click.echo("Aborted.")
        return
    shutil.rmtree(org_dir)
    click.echo(o.success(f"Removed org: {name}"))


@org.command("history")
@click.pass_context
def org_history(ctx: click.Context) -> None:
    """View recent runs."""
    click.echo()
    _print_history_section(ctx)
    click.echo()


# ── Project ──

@fleet.group(invoke_without_command=True)
@click.pass_context
def project(ctx: click.Context) -> None:
    """Manage projects."""
    if ctx.invoked_subcommand is None:
        proj_svc = ctx.obj["project_service"]
        active = proj_svc.get_active()
        if active:
            click.echo(f"Active project: {o.bold(active.id)}")
            click.echo(o.dim(f"  {active.root}"))
        else:
            click.echo(o.dim("No active project. Tasks run in one-off mode."))
            click.echo(o.dim("  fleet project create <id>   Create one"))
            click.echo(o.dim("  fleet project use <id>      Activate one"))


@project.command("create")
@click.argument("project_id")
@click.option("--path", "repo_path", type=click.Path(exists=True, resolve_path=True), default=None,
              help="Path to the repo this project works on. Defaults to current directory.")
@click.pass_context
def project_create(ctx: click.Context, project_id: str, repo_path: str | None) -> None:
    """Create a new project with scaffolded directories."""
    proj_svc = ctx.obj["project_service"]
    path = Path(repo_path) if repo_path else Path.cwd()
    try:
        p = proj_svc.create(project_id, repo_path=path)
        click.echo(o.success(f"Created: {project_id}"))
        click.echo(f"  Repo: {path}")
        click.echo(o.dim(f"  Data: {p.root}"))
        click.echo()
        click.echo("Fill in the context files:")
        click.echo(f"  {p.root / 'context' / 'architecture.md'}")
        click.echo(f"  {p.root / 'context' / 'domain-glossary.md'}")
        click.echo(f"  {p.root / 'commands' / 'build-test-lint.md'}")
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@project.command("use")
@click.argument("project_id")
@click.pass_context
def project_use(ctx: click.Context, project_id: str) -> None:
    """Set a project as active."""
    proj_svc = ctx.obj["project_service"]
    try:
        proj_svc.activate(project_id)
        click.echo(o.success(f"Switched to: {project_id}"))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@project.command("add-repo")
@click.argument("repo_path", type=click.Path(exists=True, resolve_path=True))
@click.pass_context
def project_add_repo(ctx: click.Context, repo_path: str) -> None:
    """Add a repo to the active project (for multi-repo projects)."""
    proj_svc = ctx.obj["project_service"]
    active = proj_svc.get_active()
    if active is None:
        click.echo(o.error("No active project. Use: fleet project use <id>"), err=True)
        raise SystemExit(1)
    try:
        p = proj_svc.add_repo(active.id, Path(repo_path))
        click.echo(o.success(f"Added: {repo_path}"))
        click.echo(f"  Repos for {p.id}:")
        for rp in p.repo_paths:
            click.echo(f"    {rp}")
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@project.command("edit")
@click.argument("project_id")
@click.pass_context
def project_edit(ctx: click.Context, project_id: str) -> None:
    """Open the project's project.yaml in $EDITOR."""
    proj_svc = ctx.obj["project_service"]
    p = proj_svc.get(project_id)
    if p is None:
        click.echo(o.error(f"Project not found: {project_id}"), err=True)
        raise SystemExit(1)
    _edit_file(p.root / "project.yaml")


@project.command("remove")
@click.argument("project_id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def project_remove(ctx: click.Context, project_id: str, yes: bool) -> None:
    """Delete a project (its directory in your org; repo code is untouched)."""
    import shutil
    proj_svc = ctx.obj["project_service"]
    p = proj_svc.get(project_id)
    if p is None:
        click.echo(o.error(f"Project not found: {project_id}"), err=True)
        raise SystemExit(1)
    if not yes and not click.confirm(f"Remove project '{project_id}' at {p.root}?"):
        click.echo("Aborted.")
        return
    active = proj_svc.get_active()
    if active and active.id == project_id:
        proj_svc.deactivate()
    shutil.rmtree(p.root)
    click.echo(o.success(f"Removed: {project_id}"))


@project.command("clear")
@click.pass_context
def project_clear(ctx: click.Context) -> None:
    """Clear the active project."""
    proj_svc = ctx.obj["project_service"]
    proj_svc.deactivate()
    click.echo(o.success("Project cleared. Running in one-off mode."))


@project.command("list")
@click.pass_context
def project_list(ctx: click.Context) -> None:
    """List all projects."""
    proj_svc = ctx.obj["project_service"]
    active = proj_svc.get_active()
    projects = proj_svc.list_projects()
    if not projects:
        click.echo(o.dim("No projects yet. Create one: fleet project create <id>"))
        return
    for p in projects:
        marker = " " + click.style("(active)", fg="green") if active and p.id == active.id else ""
        click.echo(f"  {o.bold(p.id)}{marker}")


# ── Role group ──

@fleet.group(invoke_without_command=True)
@click.pass_context
def role(ctx: click.Context) -> None:
    """Manage roles (personas)."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(role_list)


@role.command("list")
@click.pass_context
def role_list(ctx: click.Context) -> None:
    """List all roles."""
    click.echo()
    _print_roles_section(ctx)
    click.echo()


@role.command("create")
@click.argument("role_id")
@click.option("--non-interactive", is_flag=True, help="Skip prompts, use template defaults")
@click.pass_context
def role_create(ctx: click.Context, role_id: str, non_interactive: bool) -> None:
    """Create a new role in your org."""
    build = ctx.obj["build_service"]
    try:
        if non_interactive:
            build.hire(role_id)
        else:
            mission = click.prompt("What is this role's mission? (one sentence)", default="")
            required_inputs = click.prompt("What inputs does this role need? (comma-separated)", default="")
            exit_criteria = click.prompt("When is this role done? (comma-separated)", default="")
            non_goals = click.prompt("What should this role NOT do? (comma-separated)", default="")
            build.hire_interactive(
                role_id,
                mission=mission,
                required_inputs=[x.strip() for x in required_inputs.split(",") if x.strip()],
                exit_criteria=[x.strip() for x in exit_criteria.split(",") if x.strip()],
                non_goals=[x.strip() for x in non_goals.split(",") if x.strip()],
            )
        click.echo(o.success(f"Hired: {role_id}"))
        click.echo(o.dim(f"Stored at: {ctx.obj['config'].user_personas_dir / role_id}"))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@role.command("edit")
@click.argument("role_id")
@click.pass_context
def role_edit(ctx: click.Context, role_id: str) -> None:
    """Open a role's persona.md in $EDITOR. Copies starter to your org if needed."""
    config = ctx.obj["config"]
    build = ctx.obj["build_service"]
    if not build._personas.exists(role_id):
        click.echo(o.error(f"Role not found: {role_id}"), err=True)
        raise SystemExit(1)
    user_path = config.user_personas_dir / role_id / "persona.md"
    if not user_path.is_file():
        # Adopt the starter so the user edits their own copy.
        build.adopt_persona_if_missing(role_id)
        click.echo(o.dim(f"Copied starter to your org for editing: {user_path}"), err=True)
    _edit_file(user_path)


@role.command("remove")
@click.argument("role_id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def role_remove(ctx: click.Context, role_id: str, yes: bool) -> None:
    """Remove a role from your local org (starters are never touched)."""
    import shutil
    config = ctx.obj["config"]
    user_dir = config.user_personas_dir / role_id
    if not user_dir.is_dir():
        click.echo(o.error(f"Role not in your org: {role_id}"), err=True)
        raise SystemExit(1)
    if not yes and not click.confirm(f"Remove role '{role_id}' from your org?"):
        click.echo("Aborted.")
        return
    shutil.rmtree(user_dir)
    click.echo(o.success(f"Removed: {role_id}"))


@role.command("adopt")
@click.argument("role_id")
@click.pass_context
def role_adopt(ctx: click.Context, role_id: str) -> None:
    """Copy a starter role to your org for customization."""
    build = ctx.obj["build_service"]
    try:
        build.adopt_persona(role_id)
        click.echo(o.success(f"Adopted: {role_id}"))
        click.echo(o.dim("Edit to customize. Your version takes priority over the starter."))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@role.command("contribute")
@click.argument("role_id")
@click.pass_context
def role_contribute(ctx: click.Context, role_id: str) -> None:
    """Copy a role from your org to the repo for sharing."""
    build = ctx.obj["build_service"]
    try:
        build.contribute_persona(role_id)
        click.echo(o.success(f"Contributed: {role_id}"))
        click.echo(o.dim("Now commit to share with your team."))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


# ── Team group ──

@fleet.group(invoke_without_command=True)
@click.pass_context
def team(ctx: click.Context) -> None:
    """Manage teams."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(team_list)


@team.command("list")
@click.pass_context
def team_list(ctx: click.Context) -> None:
    """List all teams."""
    click.echo()
    _print_teams_section(ctx)
    click.echo()


@team.command("create")
@click.argument("team_id")
@click.pass_context
def team_create(ctx: click.Context, team_id: str) -> None:
    """Create a new team in your org."""
    build = ctx.obj["build_service"]
    try:
        build.create_team(team_id)
        click.echo(o.success(f"Team created: {team_id}"))
        click.echo(o.dim(f"Stored at: {ctx.obj['config'].user_teams_dir / f'{team_id}.yaml'}"))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@team.command("edit")
@click.argument("team_id")
@click.pass_context
def team_edit(ctx: click.Context, team_id: str) -> None:
    """Open a team's YAML in $EDITOR. Copies starter to your org if needed."""
    config = ctx.obj["config"]
    build = ctx.obj["build_service"]
    if not build._teams.exists(team_id):
        click.echo(o.error(f"Team not found: {team_id}"), err=True)
        raise SystemExit(1)
    user_path = config.user_teams_dir / f"{team_id}.yaml"
    if not user_path.is_file():
        build.adopt_team_if_missing(team_id)
        click.echo(o.dim(f"Copied starter to your org for editing: {user_path}"), err=True)
    _edit_file(user_path)


@team.command("remove")
@click.argument("team_id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def team_remove(ctx: click.Context, team_id: str, yes: bool) -> None:
    """Remove a team from your local org."""
    config = ctx.obj["config"]
    user_path = config.user_teams_dir / f"{team_id}.yaml"
    if not user_path.is_file():
        click.echo(o.error(f"Team not in your org: {team_id}"), err=True)
        raise SystemExit(1)
    if not yes and not click.confirm(f"Remove team '{team_id}' from your org?"):
        click.echo("Aborted.")
        return
    user_path.unlink()
    click.echo(o.success(f"Removed: {team_id}"))


@team.command("adopt")
@click.argument("team_id")
@click.pass_context
def team_adopt(ctx: click.Context, team_id: str) -> None:
    """Copy a starter team to your org for customization."""
    build = ctx.obj["build_service"]
    try:
        build.adopt_team(team_id)
        click.echo(o.success(f"Adopted: {team_id}"))
        click.echo(o.dim("Edit to customize. Your version takes priority over the starter."))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@team.command("contribute")
@click.argument("team_id")
@click.pass_context
def team_contribute(ctx: click.Context, team_id: str) -> None:
    """Copy a team from your org to the repo for sharing."""
    build = ctx.obj["build_service"]
    try:
        build.contribute_team(team_id)
        click.echo(o.success(f"Contributed: {team_id}"))
        click.echo(o.dim("Now commit to share with your team."))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


# ── Reflect ──

@fleet.command()
@click.option("--prompt", "prompt_only", is_flag=True, help="Output the reflection prompt without executing")
@click.option("--write-back", is_flag=True, help="Force write-back regardless of reflection mode")
@click.argument("role_id", required=False)
@click.pass_context
def reflect(ctx: click.Context, prompt_only: bool, write_back: bool, role_id: str | None) -> None:
    """Run a reflection cycle."""
    reflect_svc = ctx.obj["reflect_service"]
    config = ctx.obj["config"]

    # Resolve active project
    proj_svc = ctx.obj["project_service"]
    active_project = proj_svc.get_active()
    project_root = active_project.root if active_project else None
    project_id = active_project.id if active_project else None

    prompt = reflect_svc.generate_prompt(
        role_id=role_id, project_root=project_root, project_id=project_id,
    )

    if prompt_only:
        click.echo(prompt)
        return

    backend_name = get_active_backend(config)
    b = ctx.obj["sync_service"].get_backend(backend_name)
    if b is None:
        click.echo(o.error(f"Backend not found: {backend_name}"), err=True)
        raise SystemExit(1)

    try:
        output = b.execute("reflect", prompt, "reflect")
    except (RuntimeError, OSError) as e:
        click.echo(o.error(f"Reflection execution failed: {e}"), err=True)
        raise SystemExit(1)

    click.echo(output)

    def _do_write_back():
        result = reflect_svc.write_back(output, project_root=project_root)
        _report_reflection(result)
        # Check if condensation is needed
        condense = get_condense_after(config)
        if condense > 0:
            condensed_ids = reflect_svc.maybe_condense(
                backend=b, condense_after=condense,
            )
            if condensed_ids:
                click.echo(
                    o.dim(f"Condensed learnings for: {', '.join(condensed_ids)}"),
                    err=True,
                )

    if write_back:
        # Explicit --write-back always writes
        _do_write_back()
    else:
        # Check reflection mode
        mode = get_reflection_mode(config)
        if mode == ReflectionMode.AUTO:
            _do_write_back()
        elif mode == ReflectionMode.REVIEW:
            click.echo()
            click.echo(o.bold("Reflection complete. Review learnings before saving:"))
            click.echo()
            if click.confirm("Write these learnings back?"):
                _do_write_back()
            else:
                click.echo(o.dim("Learnings discarded."))
        # OFF mode: output was shown but nothing written


def _report_reflection(result) -> None:
    """Print a summary of how many learnings were written back."""
    n = (
        len(result.persona_learnings) + len(result.team_learnings)
        + len(result.org_learnings) + len(result.project_learnings)
    )
    click.echo(o.success(f"Reflection complete. {n} learning(s) written back."), err=True)


# ── Learnings ──

@fleet.command()
@click.pass_context
def learnings(ctx: click.Context) -> None:
    """Show what your org has learned."""
    org = ctx.obj["org_service"]
    config = ctx.obj["config"]

    click.echo()
    click.echo(o.bold("Learnings") + "  " + o.dim(f"(stored at {config.knowledge_dir})"))
    click.echo()

    personas = org.list_personas()
    with_knowledge = [p for p in personas if p.has_knowledge]
    if with_knowledge:
        for pv in with_knowledge:
            lc = o.level_color(pv.level)
            click.echo(f"  {click.style('+', fg='green')} {pv.id}  {click.style(f'[{pv.level.value}]', fg=lc)}")
    else:
        click.echo(o.dim("  No learnings yet. Run some tasks first."))
    click.echo()

