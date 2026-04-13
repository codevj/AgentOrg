"""Reflect service — run reflection and write learnings back."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import re

from agentorg.domain.condense import build_condense_prompt
from agentorg.domain.knowledge import has_content, strip_placeholders
from agentorg.domain.models import ReflectionResult
from agentorg.domain.reflection import parse_reflection_output
from agentorg.ports.backend import Backend
from agentorg.ports.knowledge_store import KnowledgeStore
from agentorg.ports.repository import PersonaRepository
from agentorg.ports.renderer import TemplateRenderer
from agentorg.ports.run_store import RunStore


class ReflectService:
    def __init__(
        self,
        persona_repo: PersonaRepository,
        knowledge_store: KnowledgeStore,
        run_store: RunStore,
        renderer: TemplateRenderer,
    ) -> None:
        self._personas = persona_repo
        self._knowledge = knowledge_store
        self._runs = run_store
        self._renderer = renderer

    def generate_prompt(
        self,
        *,
        role_id: str | None = None,
        run_content: str | None = None,
        project_root: Path | None = None,
        project_id: str | None = None,
    ) -> str:
        """Generate a reflection prompt from persona definitions and run history."""
        roles = []
        if role_id:
            persona = self._personas.get(role_id)
            if persona:
                learnings = self._knowledge.persona_learnings(role_id)
                roles.append({
                    "id": role_id,
                    "content": persona.raw_content,
                    "knowledge": strip_placeholders(learnings) if has_content(learnings) else "",
                })
        else:
            for pid in self._personas.list_ids():
                persona = self._personas.get(pid)
                if persona is None:
                    continue
                learnings = self._knowledge.persona_learnings(pid)
                roles.append({
                    "id": pid,
                    "content": persona.raw_content,
                    "knowledge": strip_placeholders(learnings) if has_content(learnings) else "",
                })

        # Gather run history
        runs = []
        if run_content:
            runs.append(run_content)
        else:
            for run in self._runs.list_recent(count=10):
                if run.output:
                    runs.append(run.output)

        # Project context for reflection
        project_context = ""
        project_knowledge = ""
        if project_root:
            context_dir = project_root / "context"
            if context_dir.is_dir():
                parts = []
                for f in sorted(context_dir.glob("*.md")):
                    parts.append(f.read_text())
                project_context = "\n\n".join(parts)
            learnings_file = project_root / "knowledge" / "learnings.md"
            if learnings_file.is_file():
                content = learnings_file.read_text()
                if has_content(content):
                    project_knowledge = strip_placeholders(content)

        return self._renderer.render("reflection_prompt.md.j2", {
            "roles": roles,
            "runs": runs,
            "run_count": len(runs),
            "project_id": project_id or "",
            "project_context": project_context,
            "project_knowledge": project_knowledge,
        })

    def write_back(
        self, reflection_output: str, *, project_root: Path | None = None
    ) -> ReflectionResult:
        """Parse reflection output and write learnings to knowledge store."""
        result = parse_reflection_output(reflection_output)
        today = date.today().isoformat()

        for pl in result.persona_learnings:
            self._knowledge.init_persona(pl.persona_id)
            self._knowledge.append_persona_learnings(
                pl.persona_id, f"\n## Reflection: {today}\n\n{pl.content}\n"
            )

        for tl in result.team_learnings:
            self._knowledge.init_team(tl.team_id)
            self._knowledge.append_team_learnings(
                tl.team_id, f"\n## Reflection: {today}\n\n{tl.content}\n"
            )

        for ol in result.org_learnings:
            self._knowledge.init_org()
            self._knowledge.append_org_learnings(f"\n## {today}\n\n{ol.content}\n")

        for la in result.level_assessments:
            self._knowledge.set_persona_level(la.persona_id, la.level)

        for prl in result.project_learnings:
            if project_root and prl.project_id:
                learnings_file = project_root / "knowledge" / "learnings.md"
                if learnings_file.is_file():
                    with open(learnings_file, "a") as f:
                        f.write(f"\n## Reflection: {today}\n\n{prl.content}\n")

        return result

    def maybe_condense(
        self,
        *,
        backend: Backend,
        condense_after: int,
        persona_ids: list[str] | None = None,
    ) -> list[str]:
        """Check each persona and condense if reflection count >= threshold.

        Returns a list of persona IDs that were condensed.
        """
        if condense_after <= 0:
            return []

        ids = persona_ids or self._personas.list_ids()
        condensed_ids: list[str] = []

        for pid in ids:
            count = self._knowledge.persona_reflection_count(pid)
            if count < condense_after:
                continue

            # Get current learnings
            learnings = self._knowledge.persona_learnings(pid)
            if not learnings or not has_content(learnings):
                continue

            # Extract individual reflections from the learnings text
            reflections = re.split(r"(?=^## Reflection:)", learnings, flags=re.MULTILINE)
            new_reflections = [r.strip() for r in reflections if r.strip().startswith("## Reflection:")]

            prompt = build_condense_prompt(learnings, new_reflections)
            try:
                output = backend.prompt(prompt)
            except Exception:
                continue  # condensation failure is non-fatal

            # Parse output: extract Active Learnings and Changelog sections
            condensed_text, changelog_text = _parse_condense_output(output)
            if condensed_text:
                self._knowledge.condense_persona_learnings(pid, condensed_text, changelog_text)
                condensed_ids.append(pid)

        return condensed_ids


def _parse_condense_output(output: str) -> tuple[str, str]:
    """Extract Active Learnings and Changelog sections from LLM output.

    Returns (condensed_text, changelog_text). Either may be empty.
    """
    condensed = ""
    changelog = ""

    # Split on ## headers
    sections = re.split(r"(?=^## )", output, flags=re.MULTILINE)
    for section in sections:
        stripped = section.strip()
        if stripped.lower().startswith("## active learnings"):
            # Everything after the header line
            lines = stripped.split("\n", 1)
            condensed = lines[1].strip() if len(lines) > 1 else ""
        elif stripped.lower().startswith("## changelog"):
            lines = stripped.split("\n", 1)
            changelog = lines[1].strip() if len(lines) > 1 else ""

    return condensed, changelog
