"""E2E tests for the full exec -> reflect -> knowledge write-back loop.

We mock the SubprocessExecutor.run method to simulate LLM responses,
letting us test the complete cycle without real LLM calls. The mock
returns different responses for the exec call vs the reflection call
using side_effect.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agentorg.cli.main import fleet
from agentorg.domain.models import Level
from agentorg.ports.executor import CommandResult

# ── Fixture paths ──

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "mock_responses"
EXEC_RESPONSE_FILE = FIXTURES_DIR / "exec_response.md"
REFLECTION_RESPONSE_FILE = FIXTURES_DIR / "reflection_response.md"


def _load_fixture(path: Path) -> str:
    return path.read_text()


def _mock_command_result(stdout: str) -> CommandResult:
    return CommandResult(stdout=stdout, stderr="", returncode=0)


def _failed_command_result(stderr: str = "error") -> CommandResult:
    return CommandResult(stdout="", stderr=stderr, returncode=1)


@pytest.fixture
def exec_response() -> str:
    return _load_fixture(EXEC_RESPONSE_FILE)


@pytest.fixture
def reflection_response() -> str:
    return _load_fixture(REFLECTION_RESPONSE_FILE)


@pytest.fixture
def org_home(tmp_path: Path) -> Path:
    """Isolated org_home directory for a test run."""
    home = tmp_path / "org_home"
    home.mkdir()
    # Create a minimal settings file so init check passes
    (home / "settings.yaml").write_text(
        "default_backend: claude\ndefault_team: product-delivery\nreflection: auto\n"
    )
    return home


@pytest.fixture
def runner(org_home: Path) -> CliRunner:
    """CliRunner with isolated AGENT_ORG_HOME."""
    return CliRunner(env={"AGENT_ORG_HOME": str(org_home)})


@pytest.fixture
def mock_executor(exec_response: str, reflection_response: str):
    """Patch SubprocessExecutor for exec (interactive) + reflection (run).

    execute() calls run_interactive (returns 0).
    reflect calls run (returns reflection response).
    """
    reflect_result = _mock_command_result(reflection_response)

    with patch("agentorg.adapters.executor.SubprocessExecutor.run_interactive", return_value=0), \
         patch("agentorg.adapters.executor.SubprocessExecutor.run", side_effect=[reflect_result]) as mock_run, \
         patch("agentorg.adapters.executor.SubprocessExecutor.is_installed", return_value=True):
        yield mock_run


@pytest.fixture
def mock_executor_exec_only(exec_response: str):
    """Patch for exec only (interactive), no reflection."""
    with patch("agentorg.adapters.executor.SubprocessExecutor.run_interactive", return_value=0), \
         patch("agentorg.adapters.executor.SubprocessExecutor.run") as mock_run, \
         patch("agentorg.adapters.executor.SubprocessExecutor.is_installed", return_value=True):
        yield mock_run


# ═══════════════════════════════════════════════════════════════════
# TestExecReflectLoop — full exec -> reflect -> knowledge cycle
# ═══════════════════════════════════════════════════════════════════


class TestExecReflectLoop:
    """Test the complete execution + reflection + knowledge write-back loop."""

    def test_exec_writes_run_log(self, runner: CliRunner, org_home: Path, mock_executor):
        """fleet run should save a run log to the runs directory."""
        with runner.isolated_filesystem():
            result = runner.invoke(fleet, [
                "run","--team", "product-delivery",
                "Implement user authentication",
            ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        runs_dir = org_home / "runs"
        assert runs_dir.is_dir(), "Runs directory not created"

        run_files = list(runs_dir.glob("*.md"))
        assert len(run_files) >= 1, "No run log file created"

        run_content = run_files[0].read_text()
        assert "product-delivery" in run_content
        assert "Implement user authentication" in run_content

    def test_exec_triggers_reflection(self, runner: CliRunner, mock_executor):
        """Exec should call the executor twice: once for exec, once for reflection."""
        with runner.isolated_filesystem():
            result = runner.invoke(fleet, [
                "run","--team", "product-delivery",
                "Build a feature",
            ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Exec is interactive (run_interactive), reflect goes through run
        assert mock_executor.call_count == 1, (
            f"Expected 1 run call (reflect only), got {mock_executor.call_count}"
        )

    def test_reflection_writes_persona_learnings(
        self, runner: CliRunner, org_home: Path, mock_executor
    ):
        """After reflection, persona learning files should be created."""
        with runner.isolated_filesystem():
            runner.invoke(fleet, [
                "run","--team", "product-delivery",
                "Implement OAuth2",
            ])

        knowledge_dir = org_home / "knowledge" / "personas"

        # The reflection response contains learnings for architect, developer, tester, code-reviewer
        for persona_id in ["architect", "developer", "tester", "code-reviewer"]:
            learnings_file = knowledge_dir / persona_id / "learnings.md"
            assert learnings_file.is_file(), f"No learnings file for {persona_id}"

            content = learnings_file.read_text()
            assert "Reflection:" in content, f"No reflection header in {persona_id} learnings"

        # Verify specific content from the mock reflection response
        architect_content = (knowledge_dir / "architect" / "learnings.md").read_text()
        assert "rollback plan" in architect_content

        developer_content = (knowledge_dir / "developer" / "learnings.md").read_text()
        assert "Validate inputs" in developer_content

    def test_reflection_writes_team_learnings(
        self, runner: CliRunner, org_home: Path, mock_executor
    ):
        """Team learnings from reflection should be written to the knowledge store."""
        with runner.isolated_filesystem():
            runner.invoke(fleet, [
                "run","--team", "product-delivery",
                "Build a feature",
            ])

        team_learnings_file = org_home / "knowledge" / "teams" / "product-delivery" / "learnings.md"
        assert team_learnings_file.is_file(), "Team learnings file not created"

        content = team_learnings_file.read_text()
        assert "Architect-developer handoff" in content
        assert "concurrency hints" in content

    def test_reflection_writes_org_learnings(
        self, runner: CliRunner, org_home: Path, mock_executor
    ):
        """Org-wide learnings from reflection should be written to the knowledge store."""
        with runner.isolated_filesystem():
            runner.invoke(fleet, [
                "run","--team", "product-delivery",
                "Build a feature",
            ])

        org_file = org_home / "knowledge" / "org-learnings.md"
        assert org_file.is_file(), "Org learnings file not created"

        content = org_file.read_text()
        assert "Vague tasks" in content
        assert "File boundary specifications" in content

    def test_reflection_updates_levels(
        self, runner: CliRunner, org_home: Path, mock_executor
    ):
        """Level assessments from reflection should update persona .level files."""
        with runner.isolated_filesystem():
            runner.invoke(fleet, [
                "run","--team", "product-delivery",
                "Build a feature",
            ])

        knowledge_dir = org_home / "knowledge" / "personas"

        for persona_id in ["architect", "developer", "tester", "code-reviewer"]:
            level_file = knowledge_dir / persona_id / ".level"
            assert level_file.is_file(), f"No level file for {persona_id}"
            assert level_file.read_text().strip() == "practiced", (
                f"Expected 'practiced' for {persona_id}, got '{level_file.read_text().strip()}'"
            )

    def test_knowledge_included_in_next_run(
        self, runner: CliRunner, org_home: Path, exec_response: str, reflection_response: str
    ):
        """After learnings are written, the next run's prompt should include them."""
        # First run: exec + reflect (writes knowledge)
        exec_result = _mock_command_result(exec_response)
        reflect_result = _mock_command_result(reflection_response)

        with patch("agentorg.adapters.executor.SubprocessExecutor.run_interactive", return_value=0), \
             patch("agentorg.adapters.executor.SubprocessExecutor.run", side_effect=[reflect_result]), \
             patch("agentorg.adapters.executor.SubprocessExecutor.is_installed", return_value=True):
            with runner.isolated_filesystem():
                runner.invoke(fleet, [
                    "run","--team", "product-delivery",
                    "First task",
                ])

        # Second run: prompt-only mode to inspect the generated prompt
        result = runner.invoke(fleet, [
            "run", "--prompt", "--team", "product-delivery",
            "Second task",
        ])

        assert result.exit_code == 0
        # The prompt should now include the learnings written by the first run's reflection
        assert "rollback plan" in result.output, (
            "Expected architect learnings in the next run's prompt"
        )
        assert "Validate inputs" in result.output, (
            "Expected developer learnings in the next run's prompt"
        )


# ═══════════════════════════════════════════════════════════════════
# TestBudgetEnforcement — budget limits on exec and reflection
# ═══════════════════════════════════════════════════════════════════


class TestBudgetEnforcement:
    """Test that budget constraints are enforced correctly."""

    def test_budget_skip_reflection_when_exceeded(
        self, runner: CliRunner, org_home: Path, exec_response: str
    ):
        """A team with max_calls=1 should execute but skip reflection.

        With max_calls=1, the exec call consumes the entire budget.
        Reflection should be skipped because budget.check(REFLECT) returns False
        when calls_used >= calls_max.
        """
        exec_result = _mock_command_result(exec_response)

        # We provide only one response; if reflection were attempted it would
        # raise StopIteration from the exhausted side_effect iterator (which
        # gets swallowed by the try/except in RunService.execute, but the
        # mock call_count tells us what happened).
        mock_run = MagicMock(side_effect=[exec_result])

        # Patch the team loader to return a team with max_calls=1
        from agentorg.domain.models import Budget, Gates, Team

        tight_budget_team = Team(
            id="tight-budget",
            persona_ids=["architect", "developer"],
            governance_profile="quality_first",
            gates=Gates(reviewer_required=False, tester_required=False),
            budget=Budget(max_calls=1, reflection=True, interactions=0),
        )

        with patch("agentorg.adapters.executor.SubprocessExecutor.run_interactive", return_value=0), \
             patch("agentorg.adapters.executor.SubprocessExecutor.run", mock_run), \
             patch("agentorg.adapters.executor.SubprocessExecutor.is_installed", return_value=True), \
             patch("agentorg.adapters.filesystem.team_repo.FileTeamRepository.get", return_value=tight_budget_team):
            with runner.isolated_filesystem():
                result = runner.invoke(fleet, [
                    "run","--team", "tight-budget",
                    "Do something",
                ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Exec is interactive (run_interactive). Reflection skipped (budget exceeded).
        assert mock_run.call_count == 0, (
            f"Expected 0 run calls (no reflection), got {mock_run.call_count}"
        )

    def test_budget_blocks_exec_when_zero(self, runner: CliRunner, org_home: Path):
        """A team with max_calls=0 should fail to execute."""
        from agentorg.domain.models import Budget, Gates, Team

        zero_budget_team = Team(
            id="zero-budget",
            persona_ids=["architect"],
            governance_profile="quality_first",
            gates=Gates(reviewer_required=False, tester_required=False),
            budget=Budget(max_calls=0, reflection=False, interactions=0),
        )

        with patch("agentorg.adapters.executor.SubprocessExecutor.is_installed", return_value=True), \
             patch("agentorg.adapters.filesystem.team_repo.FileTeamRepository.get", return_value=zero_budget_team):
            with runner.isolated_filesystem():
                result = runner.invoke(fleet, [
                    "run","--team", "zero-budget",
                    "Do something",
                ])

        # Should fail with budget exceeded error
        assert result.exit_code != 0, "Expected non-zero exit code for zero budget"


# ═══════════════════════════════════════════════════════════════════
# TestMockFixtures — verify the fixture files are well-formed
# ═══════════════════════════════════════════════════════════════════


class TestMockFixtures:
    """Verify that mock response fixture files are loadable and well-formed."""

    def test_mock_responses_are_loadable(self):
        """Both fixture files should exist and be non-empty."""
        assert EXEC_RESPONSE_FILE.is_file(), f"Missing fixture: {EXEC_RESPONSE_FILE}"
        assert REFLECTION_RESPONSE_FILE.is_file(), f"Missing fixture: {REFLECTION_RESPONSE_FILE}"

        exec_content = _load_fixture(EXEC_RESPONSE_FILE)
        assert len(exec_content) > 100, "Exec response fixture too short"

        reflection_content = _load_fixture(REFLECTION_RESPONSE_FILE)
        assert len(reflection_content) > 100, "Reflection response fixture too short"

    def test_exec_fixture_has_handoffs(self):
        """The exec fixture should contain handoff structures."""
        content = _load_fixture(EXEC_RESPONSE_FILE)
        assert "Handoff" in content, "Exec fixture missing handoff sections"
        assert "Architect" in content
        assert "Developer" in content
        assert "Tester" in content

    def test_reflection_fixture_has_learning_blocks(self):
        """The reflection fixture should contain parseable ===LEARNING=== blocks."""
        content = _load_fixture(REFLECTION_RESPONSE_FILE)

        assert "===LEARNING:architect===" in content
        assert "===LEARNING:developer===" in content
        assert "===TEAM_LEARNING:product-delivery===" in content
        assert "===ORG_LEARNING===" in content
        assert "===END===" in content
        assert "===LEVEL:architect=practiced===" in content

    def test_reflection_fixture_is_parseable(self):
        """The reflection fixture should parse correctly via the domain parser."""
        from agentorg.domain.reflection import parse_reflection_output

        content = _load_fixture(REFLECTION_RESPONSE_FILE)
        result = parse_reflection_output(content)

        assert len(result.persona_learnings) == 4, (
            f"Expected 4 persona learning blocks, got {len(result.persona_learnings)}"
        )
        assert len(result.team_learnings) == 1, (
            f"Expected 1 team learning block, got {len(result.team_learnings)}"
        )
        assert len(result.org_learnings) == 1, (
            f"Expected 1 org learning block, got {len(result.org_learnings)}"
        )
        assert len(result.level_assessments) == 4, (
            f"Expected 4 level assessments, got {len(result.level_assessments)}"
        )

        # Check specific parsed values
        architect_learning = next(
            pl for pl in result.persona_learnings if pl.persona_id == "architect"
        )
        assert "rollback plan" in architect_learning.content

        team_learning = result.team_learnings[0]
        assert team_learning.team_id == "product-delivery"

        architect_level = next(
            la for la in result.level_assessments if la.persona_id == "architect"
        )
        assert architect_level.level == Level.PRACTICED
