from __future__ import annotations

import logging
from core.domain import LessonLearned, RuleScope
from storage.repository import lessons_repo
from services.rules_registry import rules_registry

logger = logging.getLogger(__name__)


class LessonsEngine:
    """Moteur de Mémoire des Leçons Apprises & Auto-Amélioration Continue."""

    def record_lesson(
        self,
        topic: str,
        problem_statement: str,
        solution_applied: str,
        prevention_rule: str = "",
        project_id: str | None = None,
        confidence_score: float = 0.95,
    ) -> LessonLearned:
        """Enregistre une nouvelle leçon apprise suite à un incident ou un audit."""
        lesson = LessonLearned(
            scope="project" if project_id else "global",
            project_id=project_id,
            topic=topic,
            problem_statement=problem_statement,
            solution_applied=solution_applied,
            prevention_rule=prevention_rule,
            confidence_score=confidence_score,
            status="approved",
        )
        return lessons_repo.save_lesson(lesson)

    def find_relevant_lessons(self, query: str) -> list[LessonLearned]:
        """Recherche les leçons pertinentes par mot-clé."""
        all_lessons = lessons_repo.list_lessons()
        q = query.lower()
        matched = [
            l for l in all_lessons
            if q in l.topic.lower() or q in l.problem_statement.lower() or q in l.solution_applied.lower()
        ]
        return matched

    def convert_lesson_to_rule(self, lesson_id: str) -> bool:
        """Convertit une règle de prévention issue d'une leçon en règle modulaire active (.md)."""
        all_lessons = lessons_repo.list_lessons()
        lesson = next((l for l in all_lessons if l.id == lesson_id), None)
        if not lesson or not lesson.prevention_rule:
            return False

        rule_name = f"prevention_{lesson.topic.lower().replace(' ', '_')}"
        rules_registry.create_rule(
            name=rule_name,
            category="Auto-Amélioration",
            content=f"# Règle de Prévention : {lesson.topic}\n\n- {lesson.prevention_rule}\n",
            scope=RuleScope.GLOBAL,
        )
        return True

    def get_lessons_prompt_context(self, topic_query: str) -> str:
        """Génère un bloc XML de leçons apprises pour injection dans le contexte agent."""
        relevant = self.find_relevant_lessons(topic_query)
        if not relevant:
            return ""

        lines = ["<lessons_learned>"]
        for l in relevant[:3]:
            lines.append(f'  <lesson topic="{l.topic}">')
            lines.append(f"    <problem>{l.problem_statement}</problem>")
            lines.append(f"    <solution>{l.solution_applied}</solution>")
            if l.prevention_rule:
                lines.append(f"    <prevention>{l.prevention_rule}</prevention>")
            lines.append("  </lesson>")
        lines.append("</lessons_learned>")
        return "\n".join(lines)


lessons_engine = LessonsEngine()
