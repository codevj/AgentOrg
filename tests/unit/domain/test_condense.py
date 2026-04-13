"""Tests for the condense prompt builder."""

from agentorg.domain.condense import build_condense_prompt


def test_build_condense_prompt_basic():
    """Prompt includes active learnings and new reflections."""
    active = "- Always validate inputs\n- Use async for I/O"
    reflections = ["- Found that retries help", "- Caching reduces latency"]

    prompt = build_condense_prompt(active, reflections)

    assert "Always validate inputs" in prompt
    assert "Use async for I/O" in prompt
    assert "Found that retries help" in prompt
    assert "Caching reduces latency" in prompt
    assert "## Active Learnings" in prompt
    assert "## Changelog" in prompt


def test_build_condense_prompt_empty_reflections():
    """Works with no new reflections."""
    active = "- One learning"
    prompt = build_condense_prompt(active, [])
    assert "One learning" in prompt
    assert "Deduplicating" in prompt


def test_build_condense_prompt_numbered_reflections():
    """Each reflection gets a numbered header."""
    reflections = ["First", "Second", "Third"]
    prompt = build_condense_prompt("existing", reflections)
    assert "### Reflection 1" in prompt
    assert "### Reflection 2" in prompt
    assert "### Reflection 3" in prompt


def test_build_condense_prompt_instructions():
    """Prompt includes all required instruction keywords."""
    prompt = build_condense_prompt("learnings", ["reflection"])
    for keyword in ["Deduplicating", "Merging similar", "Removing contradictions", "Ranking by reinforcement"]:
        assert keyword in prompt
