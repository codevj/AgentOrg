"""Tests for knowledge content helpers."""

from agentorg.domain.knowledge import has_content, strip_placeholders


def test_has_content_with_bullets():
    assert has_content("- Something learned") is True


def test_has_content_with_numbered():
    assert has_content("1. First thing") is True


def test_has_content_empty():
    assert has_content("") is False
    assert has_content(None) is False


def test_has_content_only_placeholders():
    text = "# Learnings\n\n_No runs yet._\n\n_Patterns will be captured._\n"
    assert has_content(text) is False


def test_strip_placeholders():
    text = """\
# Learnings: developer

Accumulated knowledge from past runs.

## Run History

_No runs yet. Learnings will appear here after the first team execution._

## Reflection: 2026-04-13

- Always validate inputs before handoff
- Check for edge cases in empty arrays
"""
    result = strip_placeholders(text)
    assert "- Always validate" in result
    assert "- Check for edge" in result
    assert "_No runs yet" not in result
    assert "# Learnings" not in result
    assert "Accumulated knowledge" not in result


def test_strip_placeholders_empty():
    assert strip_placeholders("") == ""
