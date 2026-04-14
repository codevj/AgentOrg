"""End-to-end CLI tests using Click's CliRunner."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agentorg.cli.main import fleet


@pytest.fixture
def runner(tmp_path: Path):
    """CliRunner with isolated org setup so tests don't touch real ~/.agent-org/."""
    root = tmp_path / "agent_org_root"
    org_home = root / "orgs" / "testorg"
    org_home.mkdir(parents=True)
    (org_home / "settings.yaml").write_text(
        f"default_backend: claude\ndefault_team: product-delivery\nreflection: auto\nscratch_dir: {org_home / 'scratch'}\n"
    )
    (root / ".active-org").write_text("testorg")
    env = {
        "AGENT_ORG_HOME": str(org_home),
        "AGENT_ORG_ROOT": str(root),
    }
    r = CliRunner(env=env)
    return r


class TestStatus:
    def test_default_shows_status(self, runner: CliRunner):
        result = runner.invoke(fleet)
        assert result.exit_code == 0
        assert "AgentOrg" in result.output
        assert "Roles:" in result.output
        assert "Teams:" in result.output

    def test_status_lists_starters(self, runner: CliRunner):
        result = runner.invoke(fleet, ["status"])
        assert result.exit_code == 0
        assert "architect" in result.output
        assert "product-delivery" in result.output


class TestBackends:
    def test_list_backends(self, runner: CliRunner):
        result = runner.invoke(fleet, ["backends"])
        assert result.exit_code == 0
        assert "claude" in result.output
        assert "copilot" in result.output
        assert "cursor" in result.output

    def test_backends_shows_active_marker(self, runner: CliRunner):
        result = runner.invoke(fleet, ["backends"])
        assert result.exit_code == 0
        # Default is claude, should have the active marker on that line
        for line in result.output.splitlines():
            if "claude" in line:
                assert "<-" in line
                break
        else:
            pytest.fail("claude line not found in backends output")


class TestBackendSwitch:
    def test_backend_shows_active(self, runner: CliRunner):
        result = runner.invoke(fleet, ["backend"])
        assert result.exit_code == 0
        assert "Active backend: " in result.output
        assert "claude" in result.output

    def test_backend_use_valid(self, runner: CliRunner):
        result = runner.invoke(fleet, ["backend", "use", "cursor"])
        assert result.exit_code == 0
        assert "Switched to: cursor" in result.output
        # Verify it persisted
        result = runner.invoke(fleet, ["backend"])
        assert "cursor" in result.output

    def test_backend_use_invalid(self, runner: CliRunner):
        result = runner.invoke(fleet, ["backend", "use", "nonexistent"])
        assert result.exit_code != 0
        assert "Unknown backend: nonexistent" in result.output


class TestSync:
    def test_sync_active_backend(self, runner: CliRunner, tmp_path: Path):
        # Active backend defaults to claude; sync writes to ~/.claude/agents/
        result = runner.invoke(fleet, ["sync", "product-delivery"])
        assert result.exit_code == 0
        assert "Synced" in result.output
        # Check agent files were created in user-level dir with org prefix
        agent_dir = Path.home() / ".claude" / "agents"
        assert (agent_dir / "fleet-testorg-architect.md").is_file()
        assert (agent_dir / "fleet-testorg-product-delivery-lead.md").is_file()


class TestHire:
    def test_hire_creates_persona(self, runner: CliRunner, tmp_path: Path):
        org_home = tmp_path / "agent_org_root" / "orgs" / "testorg"
        result = runner.invoke(fleet, ["hire", "--non-interactive", "sales-rep"])
        assert result.exit_code == 0
        assert "Hired: sales-rep" in result.output
        persona_file = org_home / "personas" / "sales-rep" / "persona.md"
        assert persona_file.is_file()

    def test_hire_duplicate_fails(self, runner: CliRunner):
        runner.invoke(fleet, ["hire", "--non-interactive", "dup-role"])
        result = runner.invoke(fleet, ["hire", "--non-interactive", "dup-role"])
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_hired_persona_shows_in_status(self, runner: CliRunner):
        runner.invoke(fleet, ["hire", "--non-interactive", "custom-role"])
        result = runner.invoke(fleet, ["status"])
        assert "custom-role" in result.output


class TestTeam:
    def test_create_team(self, runner: CliRunner, tmp_path: Path):
        org_home = tmp_path / "agent_org_root" / "orgs" / "testorg"
        result = runner.invoke(fleet, ["team", "my-team"])
        assert result.exit_code == 0
        assert "Team created: my-team" in result.output
        team_file = org_home / "teams" / "my-team.yaml"
        assert team_file.is_file()


class TestInspect:
    def test_inspect_starter(self, runner: CliRunner):
        result = runner.invoke(fleet, ["inspect", "architect"])
        assert result.exit_code == 0
        assert "architect" in result.output
        assert "risk-assessment" in result.output
        assert "product-delivery" in result.output

    def test_inspect_nonexistent(self, runner: CliRunner):
        result = runner.invoke(fleet, ["inspect", "nonexistent"])
        assert result.exit_code != 0


class TestOrg:
    def test_org_roles(self, runner: CliRunner):
        result = runner.invoke(fleet, ["org", "roles"])
        assert result.exit_code == 0
        assert "architect" in result.output
        assert "developer" in result.output

    def test_org_teams(self, runner: CliRunner):
        result = runner.invoke(fleet, ["org", "teams"])
        assert result.exit_code == 0
        assert "product-delivery" in result.output


class TestAdopt:
    def test_adopt_persona(self, runner: CliRunner, tmp_path: Path):
        org_home = tmp_path / "agent_org_root" / "orgs" / "testorg"
        result = runner.invoke(fleet, ["adopt", "persona", "architect"])
        assert result.exit_code == 0
        assert "Adopted: architect" in result.output
        assert (org_home / "personas" / "architect" / "persona.md").is_file()

    def test_adopt_already_user_fails(self, runner: CliRunner):
        runner.invoke(fleet, ["adopt", "persona", "architect"])
        result = runner.invoke(fleet, ["adopt", "persona", "architect"])
        assert result.exit_code != 0
        assert "Already in your org" in result.output


class TestRun:
    def test_run_prompt_generates_prompt(self, runner: CliRunner):
        result = runner.invoke(fleet, ["run", "--prompt", "Add rate limiting"])
        assert result.exit_code == 0
        assert "team workflow" in result.output
        assert "rate limiting" in result.output

    def test_run_prompt_solo(self, runner: CliRunner):
        result = runner.invoke(fleet, ["run", "--prompt", "--solo", "Fix a bug"])
        assert result.exit_code == 0
        assert "solo workflow" in result.output

    def test_run_prompt_specific_team(self, runner: CliRunner):
        result = runner.invoke(fleet, ["run", "--prompt", "--team", "strategy-analysis", "Analyze market"])
        assert result.exit_code == 0
        assert "Analyze market" in result.output

    def test_run_prompt_reads_task_from_file(self, runner: CliRunner, tmp_path: Path):
        task_file = tmp_path / "task.md"
        task_file.write_text("Implement a caching layer for the API gateway")
        result = runner.invoke(fleet, ["run", "--prompt", str(task_file)])
        assert result.exit_code == 0
        assert "caching layer" in result.output


class TestSummon:
    def test_summon_prompt(self, runner: CliRunner):
        result = runner.invoke(fleet, ["summon", "--prompt", "architect", "Should we use a queue?"])
        assert result.exit_code == 0
        assert "Architect" in result.output
        assert "queue" in result.output

    def test_summon_nonexistent_role(self, runner: CliRunner):
        result = runner.invoke(fleet, ["summon", "nonexistent-role", "Do something"])
        assert result.exit_code != 0
        assert "not found" in result.output


class TestLearnings:
    def test_learnings_empty(self, runner: CliRunner):
        result = runner.invoke(fleet, ["learnings"])
        assert result.exit_code == 0
        assert "Learnings" in result.output


class TestReflect:
    def test_reflect_generates_prompt(self, runner: CliRunner):
        result = runner.invoke(fleet, ["reflect", "--prompt"])
        assert result.exit_code == 0
        assert "reflection cycle" in result.output
        assert "LEARNING" in result.output
