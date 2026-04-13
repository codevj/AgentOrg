"""Knowledge condensation — build prompts to deduplicate and merge learnings."""

from __future__ import annotations


def build_condense_prompt(active_learnings: str, new_reflections: list[str]) -> str:
    """Build a prompt that asks the LLM to condense learnings.

    Args:
        active_learnings: The current accumulated learnings text.
        new_reflections: New reflection entries since the last condensation.

    Returns:
        A prompt string for the LLM.
    """
    reflections_block = "\n\n".join(
        f"### Reflection {i + 1}\n{r}" for i, r in enumerate(new_reflections)
    )

    return f"""\
You are a knowledge curator for an AI agent organization. Your job is to condense
accumulated learnings into a concise, high-signal set of active knowledge.

## Current Active Learnings

{active_learnings}

## New Reflections Since Last Condensation

{reflections_block}

## Instructions

Produce a condensed set of active learnings by:
1. **Deduplicating** — merge entries that say the same thing in different words.
2. **Merging similar** — combine related observations into single, richer entries.
3. **Removing contradictions** — when two entries contradict, keep the more recent or more reinforced one.
4. **Ranking by reinforcement** — put the most frequently reinforced learnings first.

Output exactly two sections:

## Active Learnings

A bullet-point list of the condensed, deduplicated learnings. Each bullet should be
self-contained and actionable. Most important/reinforced first.

## Changelog

A brief bullet-point list of what changed during this condensation (e.g., "merged X and Y",
"removed outdated Z", "promoted A to top").
"""
