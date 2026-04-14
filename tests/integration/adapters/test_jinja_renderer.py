"""Integration tests for JinjaRenderer."""

from agentorg.adapters.rendering.jinja_renderer import JinjaRenderer


_EMPTY_PROJECT_VARS = {
    "project_context": "",
    "project_commands": "",
    "project_runbooks": "",
    "project_knowledge": "",
    "project_skills": "",
}


def test_render_solo_prompt():
    renderer = JinjaRenderer()
    result = renderer.render("solo_prompt.md.j2", {"task": "Fix the login bug.", **_EMPTY_PROJECT_VARS})
    assert "Fix the login bug" in result
    assert "solo workflow" in result


def test_render_summon_prompt():
    renderer = JinjaRenderer()
    result = renderer.render("summon_prompt.md.j2", {
        "role_title": "Architect",
        "mission": "Design systems.",
        "knowledge": "",
        "task": "Should we use a queue?",
        **_EMPTY_PROJECT_VARS,
    })
    assert "Architect" in result
    assert "Should we use a queue?" in result


def test_render_team_prompt():
    renderer = JinjaRenderer()
    result = renderer.render("team_prompt.md.j2", {
        "governance_profile": "quality_first",
        "gates": {"reviewer_required": True, "tester_required": True},
        "governance_rules": ["strict_handoff_schema"],
        "interaction_budget": 3,
        "org_learnings": "",
        "team_learnings": "",
        "roles": [
            {
                "title": "Architect",
                "content": "## Mission\n\nDesign things.",
                "knowledge": "",
                "skills": "",
            }
        ],
        "task": "Add rate limiting.",
        "team_id": "product-delivery",
        **_EMPTY_PROJECT_VARS,
    })
    assert "quality_first" in result
    assert "Architect" in result
    assert "rate limiting" in result


def test_user_dir_overrides_package_template(tmp_path):
    """User templates take precedence over package templates of the same name."""
    user_dir = tmp_path / "templates"
    user_dir.mkdir()
    (user_dir / "solo_prompt.md.j2").write_text("USER OVERRIDE: {{ task }}\n")

    renderer = JinjaRenderer(user_dir=user_dir)
    result = renderer.render("solo_prompt.md.j2", {"task": "Fix X.", **_EMPTY_PROJECT_VARS})
    assert result.startswith("USER OVERRIDE: Fix X.")


def test_user_dir_falls_back_to_package_when_missing(tmp_path):
    """Non-existent user_dir doesn't break package lookup."""
    renderer = JinjaRenderer(user_dir=tmp_path / "does-not-exist")
    result = renderer.render("solo_prompt.md.j2", {"task": "X", **_EMPTY_PROJECT_VARS})
    assert "solo workflow" in result


def test_user_dir_without_matching_template_falls_back(tmp_path):
    """If user_dir exists but lacks the template, package template is used."""
    user_dir = tmp_path / "templates"
    user_dir.mkdir()
    renderer = JinjaRenderer(user_dir=user_dir)
    result = renderer.render("solo_prompt.md.j2", {"task": "X", **_EMPTY_PROJECT_VARS})
    assert "solo workflow" in result


def test_render_claude_agent():
    renderer = JinjaRenderer()
    result = renderer.render("claude_agent.md.j2", {
        "persona_id": "developer",
        "mission": "Write code.",
        "persona_content": "# Persona: Developer\n\n## Mission\n\nWrite code.",
        "knowledge": "- Always test first",
        "skills": "",
        "handoff_contract": "1. input_digest\n2. decision",
    })
    assert "fleet-developer" in result
    assert "Write code" in result
    assert "Always test first" in result
