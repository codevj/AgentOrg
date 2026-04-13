"""CLI entry point — composition root and Click commands."""

from __future__ import annotations

from pathlib import Path

import click

from agentorg.cli import output as o
from agentorg.config import (
    Config,
    ReflectionMode,
    get_active_backend,
    get_reflection_mode,
    set_active_backend,
    set_reflection_mode,
)


def _build_context() -> dict:
    """Wire all dependencies. Called once per CLI invocation."""
    config = Config.load()

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
    renderer = JinjaRenderer()
    executor = SubprocessExecutor()

    # Backends
    from agentorg.adapters.backends.claude import ClaudeBackend
    from agentorg.adapters.backends.copilot import CopilotBackend
    from agentorg.adapters.backends.cursor import CursorBackend
    from agentorg.adapters.backends.registry import BackendRegistry

    from agentorg.config import get_active_org
    org_name = get_active_org() or "default"

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
    registry.register(CopilotBackend(**backend_kwargs))
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
    """Custom group that routes unrecognized commands to the 'ask' handler."""

    def resolve_command(self, ctx, args):
        # Try normal command resolution first
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            # Unrecognized command — treat entire args as a natural language query
            return "ask", self.commands["ask"], args


_INIT_NOT_REQUIRED = {"init", "ask"}


@click.group(cls=FleetGroup, invoke_without_command=True)
@click.pass_context
def fleet(ctx: click.Context) -> None:
    """AgentOrg — Build and run your AI organization."""
    ctx.ensure_object(dict)
    ctx.obj.update(_build_context())

    # Check if init has been done (skip for init itself and ask)
    config = ctx.obj["config"]
    if ctx.invoked_subcommand not in _INIT_NOT_REQUIRED and not config.settings_file.is_file():
        click.echo(o.warn("AgentOrg is not initialized. Run 'fleet init' first."))
        click.echo()
        ctx.invoke(init)
        return

    if ctx.invoked_subcommand is None:
        ctx.invoke(status)


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
Translate this natural language request into a fleet CLI command.

Rules:
- Output ONLY the command. One line. No explanation, no reasoning, no markdown.
- Do NOT output anything before or after the command.

Common mappings:
- "show/view learnings" → fleet learnings
- "show/view/inspect role X" or "show X learnings" → fleet inspect X
- "list roles" → fleet org roles
- "list teams" → fleet org teams
- "switch to X project" → fleet context set project X
- "switch to X backend" → fleet context set backend X
- "switch to X team" → fleet context set team X
- "create project X" → fleet project create X
- "run/build/implement X" → fleet run "X"
- "show context" → fleet context
- "list projects" → fleet project list
- "create task X" → fleet project task "X"

Current context:
{context}

Full CLI reference:
{cli_reference}

User request: {query}

Command:"""


@fleet.command(hidden=True)
@click.argument("query", nargs=-1, required=True)
@click.pass_context
def ask(ctx: click.Context, query: tuple[str, ...]) -> None:
    """Translate natural language to a fleet command and run it."""
    config = ctx.obj["config"]
    sync_svc = ctx.obj["sync_service"]
    proj_svc = ctx.obj["project_service"]
    from agentorg.config import get_active_org

    # Build context string
    active_project = proj_svc.get_active()
    context_lines = [
        f"  team: {config.default_team}",
        f"  backend: {get_active_backend(config)}",
        f"  project: {active_project.id if active_project else '(none)'}",
        f"  reflection: {get_reflection_mode(config).value}",
        f"  org: {get_active_org() or 'default'}",
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
    # Take only the first line that looks like a fleet command
    command = ""
    for line in raw_command.splitlines():
        line = line.strip().strip("`").strip()
        if not line:
            continue
        if line.startswith("fleet "):
            line = line[6:]
        # Skip lines that look like reasoning, not commands
        if any(line.lower().startswith(w) for w in ("wait", "let me", "actually", "i ", "the ")):
            continue
        command = line
        break

    if not command:
        click.echo(o.error(f"Could not translate: {query_str}"), err=True)
        raise SystemExit(1)

    click.echo(f"→ fleet {command}")


# ── Init + Config ──

@fleet.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Set up AgentOrg for first use."""
    from agentorg.config import save_settings

    config = ctx.obj["config"]

    if config.settings_file.is_file():
        click.echo(o.dim(f"Settings already exist: {config.settings_file}"))
        click.echo(o.dim("Use 'fleet config' to view or change settings."))
        return

    click.echo(o.bold("Welcome to AgentOrg"))
    click.echo()

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

    from pathlib import Path as _Path
    new_config = Config(
        starters_dir=config.starters_dir,
        org_home=_Path(config.org_home).expanduser(),
        default_backend=backend,
        default_team=default_team,
        reflection=reflection,
    )
    save_settings(new_config)

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
    """View or change settings."""
    if ctx.invoked_subcommand is None:
        config = ctx.obj["config"]
        click.echo()
        click.echo(o.bold("Settings") + "  " + o.dim(str(config.settings_file)))
        click.echo()
        mode = get_reflection_mode(config)
        click.echo(f"  org_home:          {config.org_home}")
        click.echo(f"  default_backend:   {config.default_backend}")
        click.echo(f"  default_team:      {config.default_team}")
        click.echo(f"  reflection:        {mode.value}")
        click.echo()
        if not config.settings_file.is_file():
            click.echo(o.dim("  No settings file yet. Run 'fleet init' to create one."))
            click.echo()


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set a configuration value."""
    from agentorg.config import save_settings

    config = ctx.obj["config"]
    valid_keys = {"default_backend", "default_team", "reflection", "org_home"}

    if key not in valid_keys:
        click.echo(o.error(f"Unknown key: {key}. Valid: {', '.join(sorted(valid_keys))}"), err=True)
        raise SystemExit(1)

    # Reflection mode has its own setter (preserves other settings)
    if key == "reflection":
        try:
            mode = ReflectionMode(value)
        except ValueError:
            click.echo(o.error(f"Invalid reflection mode: {value}. Use: auto, review, off"), err=True)
            raise SystemExit(1)
        set_reflection_mode(config, mode)
        click.echo(o.success(f"reflection = {value}"))
        return

    parsed = value

    from pathlib import Path as _Path
    kwargs = {
        "starters_dir": config.starters_dir,
        "org_home": _Path(config.org_home) if key != "org_home" else _Path(parsed).expanduser(),
        "default_backend": config.default_backend if key != "default_backend" else parsed,
        "default_team": config.default_team if key != "default_team" else parsed,
        "reflection": config.reflection,
    }
    new_config = Config(**kwargs)
    save_settings(new_config)
    click.echo(o.success(f"Set {key} = {parsed}"))


# ── Status ──

@fleet.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show org status — roles, teams, runs."""
    from agentorg.config import get_active_org

    org = ctx.obj["org_service"]
    s = org.status()
    config = ctx.obj["config"]

    active_backend = get_active_backend(config)
    active_org_name = get_active_org() or "default"
    mode = get_reflection_mode(config)

    proj_svc = ctx.obj["project_service"]
    active_project = proj_svc.get_active()
    project_str = active_project.id if active_project else o.dim("(none)")
    org_str = o.dim(active_org_name) if active_org_name == "default" else active_org_name

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


# ── Context ──

@fleet.group(invoke_without_command=True)
@click.pass_context
def context(ctx: click.Context) -> None:
    """View or change active context (team, backend, project, reflection)."""
    if ctx.invoked_subcommand is not None:
        return
    config = ctx.obj["config"]
    from agentorg.config import get_active_org

    active_backend = get_active_backend(config)
    proj_svc = ctx.obj["project_service"]
    active_project = proj_svc.get_active()
    active_org_name = get_active_org() or "default"
    mode = get_reflection_mode(config)

    click.echo()
    click.echo(f"  team:       {o.bold(config.default_team)}")
    click.echo(f"  backend:    {o.bold(active_backend)}")
    project_str = o.bold(active_project.id) if active_project else o.dim("(none)")
    click.echo(f"  project:    {project_str}")
    click.echo(f"  reflection: {mode.value}")
    org_str = o.dim(active_org_name) if active_org_name == "default" else o.bold(active_org_name)
    click.echo(f"  org:        {org_str}")
    click.echo()


@context.command("set")
@click.argument("key", type=click.Choice(["team", "backend", "project", "reflection", "org"]))
@click.argument("value")
@click.pass_context
def context_set(ctx: click.Context, key: str, value: str) -> None:
    """Change a context value."""
    config = ctx.obj["config"]

    if key == "team":
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

    elif key == "backend":
        sync_svc = ctx.obj["sync_service"]
        known = [info.name for info in sync_svc.list_backends()]
        if value not in known:
            click.echo(o.error(f"Unknown backend: {value}. Available: {', '.join(known)}"), err=True)
            raise SystemExit(1)
        set_active_backend(config, value)
        click.echo(o.success(f"backend = {value}"))

    elif key == "project":
        proj_svc = ctx.obj["project_service"]
        try:
            proj_svc.activate(value)
            click.echo(o.success(f"project = {value}"))
        except ValueError as e:
            click.echo(o.error(str(e)), err=True)
            raise SystemExit(1)

    elif key == "reflection":
        try:
            mode = ReflectionMode(value)
        except ValueError:
            click.echo(o.error(f"Invalid: {value}. Use: auto, review, off"), err=True)
            raise SystemExit(1)
        set_reflection_mode(config, mode)
        click.echo(o.success(f"reflection = {value}"))

    elif key == "org":
        from agentorg.config import set_active_org
        set_active_org(value)
        click.echo(o.success(f"org = {value}"))
        click.echo(o.dim("Restart fleet for the change to take effect."))


@context.command("clear")
@click.argument("key", type=click.Choice(["project", "org"]))
@click.pass_context
def context_clear(ctx: click.Context, key: str) -> None:
    """Clear a context value (project or org)."""
    if key == "project":
        ctx.obj["project_service"].deactivate()
        click.echo(o.success("project cleared — running in one-off mode."))
    elif key == "org":
        from agentorg.config import clear_active_org
        clear_active_org()
        click.echo(o.success("org cleared — using default org."))
        click.echo(o.dim("Restart fleet for the change to take effect."))


# ── Run ──

@fleet.command()
@click.argument("task", nargs=-1, required=True)
@click.option("--team", "-t", default=None, help="Team to run through")
@click.option("--solo", is_flag=True, help="Single-role execution")
@click.option("--prompt", "prompt_only", is_flag=True, help="Output the prompt without executing")
@click.pass_context
def run(ctx: click.Context, task: tuple[str, ...], team: str | None, solo: bool, prompt_only: bool) -> None:
    """Run a task through your org."""
    run_svc = ctx.obj["run_service"]
    task_str = " ".join(task)

    # If the task is a file path, read its content as the task
    task_path = Path(task_str)
    if task_path.is_file():
        task_str = task_path.read_text()

    # Resolve active project
    proj_svc = ctx.obj["project_service"]
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
        click.echo(o.dim(f"Running via {backend_name} (team: {team_id})..."), err=True)
        click.echo()
        try:
            result = run_svc.execute(
                backend=b, team_id=team_id, task=task_str, solo=solo,
                reflection_mode=mode,
                project_root=project_root,
                project_id=project_id,
            )
        except RuntimeError as e:
            click.echo(o.error(f"Execution failed: {e}"), err=True)
            raise SystemExit(1)
        if result.output:
            click.echo(result.output)
        click.echo(o.success("Run complete.") + f" {o.dim(result.budget_summary)}", err=True)


# ── Summon ──

@fleet.command()
@click.argument("role")
@click.argument("task", nargs=-1, required=True)
@click.option("--prompt", "prompt_only", is_flag=True, help="Output the prompt without executing")
@click.pass_context
def summon(ctx: click.Context, role: str, task: tuple[str, ...], prompt_only: bool) -> None:
    """Summon a single role for a quick task."""
    run_svc = ctx.obj["run_service"]
    task_str = " ".join(task)

    # Resolve active project
    proj_svc = ctx.obj["project_service"]
    active_project = proj_svc.get_active()
    project_root = active_project.root if active_project else None

    try:
        prompt = run_svc.build_summon_prompt(role, task_str, project_root=project_root)
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)

    if prompt_only:
        click.echo(prompt)
    else:
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


# ── Build ──

@fleet.command()
@click.argument("role_id")
@click.option("--non-interactive", is_flag=True, help="Skip prompts, use template defaults")
@click.pass_context
def hire(ctx: click.Context, role_id: str, non_interactive: bool) -> None:
    """Create a new role in your local org."""
    build = ctx.obj["build_service"]
    try:
        if non_interactive:
            p = build.hire(role_id)
        else:
            mission = click.prompt("What is this role's mission? (one sentence)", default="")
            required_inputs = click.prompt("What inputs does this role need? (comma-separated)", default="")
            exit_criteria = click.prompt("When is this role done? (comma-separated)", default="")
            non_goals = click.prompt("What should this role NOT do? (comma-separated)", default="")

            p = build.hire_interactive(
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


@fleet.command("team")
@click.argument("team_id")
@click.pass_context
def create_team(ctx: click.Context, team_id: str) -> None:
    """Create a new team in your local org."""
    build = ctx.obj["build_service"]
    try:
        build.create_team(team_id)
        click.echo(o.success(f"Team created: {team_id}"))
        click.echo(o.dim(f"Stored at: {ctx.obj['config'].user_teams_dir / f'{team_id}.yaml'}"))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


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


@skill.command("show")
@click.argument("skill_id")
@click.pass_context
def skill_show(ctx: click.Context, skill_id: str) -> None:
    """Show skill details and which roles use it."""
    skill_repo = ctx.obj["build_service"]._skills
    persona_repo = ctx.obj["build_service"]._personas
    s = skill_repo.get(skill_id)
    if s is None:
        click.echo(o.error(f"Skill not found: {skill_id}"), err=True)
        raise SystemExit(1)
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
        click.echo(o.dim(f"  (none — use 'fleet skill add <persona> {skill_id}')"))
    click.echo()


@skill.command("add")
@click.argument("persona_id")
@click.argument("skill_id")
@click.pass_context
def skill_add(ctx: click.Context, persona_id: str, skill_id: str) -> None:
    """Give a skill to a role."""
    build = ctx.obj["build_service"]
    try:
        build.add_skill_to_persona(persona_id, skill_id)
        click.echo(o.success(f"Added '{skill_id}' to {persona_id}"))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@skill.command("remove")
@click.argument("persona_id")
@click.argument("skill_id")
@click.pass_context
def skill_remove(ctx: click.Context, persona_id: str, skill_id: str) -> None:
    """Remove a skill from a role."""
    build = ctx.obj["build_service"]
    try:
        build.remove_skill_from_persona(persona_id, skill_id)
        click.echo(o.success(f"Removed '{skill_id}' from {persona_id}"))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


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


# ── Adopt + Contribute ──

@fleet.command()
@click.argument("item_type", type=click.Choice(["persona", "team", "skill"]))
@click.argument("item_id")
@click.pass_context
def adopt(ctx: click.Context, item_type: str, item_id: str) -> None:
    """Copy a starter to your local org for customization."""
    build = ctx.obj["build_service"]
    try:
        if item_type == "persona":
            build.adopt_persona(item_id)
        elif item_type == "team":
            build.adopt_team(item_id)
        click.echo(o.success(f"Adopted: {item_id}"))
        click.echo(o.dim("Edit to customize. Your version takes priority over the starter."))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


@fleet.command()
@click.argument("item_type", type=click.Choice(["persona", "team", "skill"]))
@click.argument("item_id")
@click.pass_context
def contribute(ctx: click.Context, item_type: str, item_id: str) -> None:
    """Copy from your local org to the repo for sharing."""
    build = ctx.obj["build_service"]
    try:
        if item_type == "persona":
            build.contribute_persona(item_id)
        elif item_type == "team":
            build.contribute_team(item_id)
        elif item_type == "skill":
            build.contribute_skill(item_id)
        click.echo(o.success(f"Contributed: {item_id}"))
        click.echo(o.dim("Now commit to share with your team."))
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


# ── Backends + Sync ──

@fleet.command()
@click.pass_context
def backends(ctx: click.Context) -> None:
    """List available backends and their status."""
    sync_svc = ctx.obj["sync_service"]
    active = get_active_backend(ctx.obj["config"])
    click.echo()
    click.echo(o.bold("Backends"))
    click.echo()
    for info in sync_svc.list_backends():
        marker = click.style(" <-", fg="green") if info.name == active else ""
        status_str = click.style("[installed]", fg="green") if info.installed else click.style("[not installed]", fg="red")
        click.echo(f"  {o.bold(info.name):<20} {status_str:<25} {o.dim(info.description)}{marker}")
    click.echo()


@fleet.group(invoke_without_command=True, name="backend")
@click.pass_context
def backend_group(ctx: click.Context) -> None:
    """View or switch the active backend."""
    if ctx.invoked_subcommand is None:
        name = get_active_backend(ctx.obj["config"])
        click.echo(f"Active backend: {o.bold(name)}")


@backend_group.command("use")
@click.argument("name")
@click.pass_context
def backend_use(ctx: click.Context, name: str) -> None:
    """Switch the active backend."""
    sync_svc = ctx.obj["sync_service"]
    known = [info.name for info in sync_svc.list_backends()]
    if name not in known:
        click.echo(o.error(f"Unknown backend: {name}. Available: {', '.join(known)}"), err=True)
        raise SystemExit(1)
    set_active_backend(ctx.obj["config"], name)
    click.echo(o.success(f"Switched to: {name}"))


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


# ── Inspect ──

@fleet.command()
@click.argument("role_id")
@click.pass_context
def inspect(ctx: click.Context, role_id: str) -> None:
    """Detailed view of a role."""
    org = ctx.obj["org_service"]
    data = org.inspect_persona(role_id)
    if data is None:
        click.echo(o.error(f"Persona not found: {role_id}"), err=True)
        raise SystemExit(1)

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


# ── Org ──

@fleet.group(invoke_without_command=True)
@click.pass_context
def org(ctx: click.Context) -> None:
    """View your organization."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(status)


@org.command("roles")
@click.pass_context
def org_roles(ctx: click.Context) -> None:
    """List all roles."""
    org_svc = ctx.obj["org_service"]
    click.echo()
    click.echo(o.bold("Roles"))
    for pv in org_svc.list_personas():
        lc = o.level_color(pv.level)
        click.echo(f"  {o.bold(pv.id):<30} {click.style(f'[{pv.level.value}]', fg=lc):<20}{o.source_tag(pv.source)} {o.dim(pv.mission)}")
    click.echo()


@org.command("teams")
@click.pass_context
def org_teams(ctx: click.Context) -> None:
    """List all teams."""
    org_svc = ctx.obj["org_service"]
    click.echo()
    click.echo(o.bold("Teams"))
    for tv in org_svc.list_teams():
        click.echo(f"  {o.bold(tv.id):<30} {o.dim(f'[{tv.governance_profile}]'):<20} {' '.join(tv.persona_ids)}{o.source_tag(tv.source)}")
    click.echo()


@org.command("history")
@click.pass_context
def org_history(ctx: click.Context) -> None:
    """View recent runs."""
    run_store = ctx.obj["run_service"]._runs
    runs = run_store.list_recent(count=10)
    click.echo()
    click.echo(o.bold("Run History"))
    click.echo()
    if not runs:
        click.echo(o.dim("  No runs yet."))
    else:
        for run in runs:
            team_str = run.team_id or "solo"
            click.echo(f"  {o.dim(run.id):<30} {team_str:<22} {run.status.value}")
    click.echo()


@org.command("use")
@click.argument("name")
@click.pass_context
def org_use(ctx: click.Context, name: str) -> None:
    """Switch to a named org (e.g., 'personal', 'work')."""
    from agentorg.config import set_active_org
    org_dir = set_active_org(name)
    click.echo(o.success(f"Switched to org: {name}"))
    click.echo(o.dim(f"Data: {org_dir}"))


@org.command("default")
@click.pass_context
def org_default(ctx: click.Context) -> None:
    """Switch back to the default org."""
    from agentorg.config import clear_active_org
    clear_active_org()
    click.echo(o.success("Switched to default org."))


@org.command("list")
@click.pass_context
def org_list(ctx: click.Context) -> None:
    """List all named orgs."""
    from agentorg.config import get_active_org, list_orgs
    active = get_active_org()
    orgs = list_orgs()
    click.echo()
    click.echo(o.bold("Orgs"))
    click.echo()
    default_marker = " " + click.style("(active)", fg="green") if not active else ""
    click.echo(f"  default{default_marker}")
    for name in orgs:
        marker = " " + click.style("(active)", fg="green") if name == active else ""
        click.echo(f"  {name}{marker}")
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


@project.command("task")
@click.argument("task_name")
@click.pass_context
def project_task(ctx: click.Context, task_name: str) -> None:
    """Scaffold a task spec in the active project."""
    proj_svc = ctx.obj["project_service"]
    try:
        task_file = proj_svc.create_task(task_name)
        click.echo(o.success(f"Created: {task_file}"))
        click.echo(o.dim("Edit the spec, then run:"))
        click.echo(f"  fleet run --team product-delivery {task_file}")
    except ValueError as e:
        click.echo(o.error(str(e)), err=True)
        raise SystemExit(1)


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

    if write_back:
        # Explicit --write-back always writes
        result = reflect_svc.write_back(output, project_root=project_root)
        _report_reflection(result)
    else:
        # Check reflection mode
        mode = get_reflection_mode(config)
        if mode == ReflectionMode.AUTO:
            result = reflect_svc.write_back(output, project_root=project_root)
            _report_reflection(result)
        elif mode == ReflectionMode.REVIEW:
            click.echo()
            click.echo(o.bold("Reflection complete. Review learnings before saving:"))
            click.echo()
            if click.confirm("Write these learnings back?"):
                result = reflect_svc.write_back(output, project_root=project_root)
                _report_reflection(result)
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

