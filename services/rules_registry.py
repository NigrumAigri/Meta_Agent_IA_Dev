from __future__ import annotations

import logging

from core.config import settings
from core.domain import RuleDefinition, RuleScope
from storage.repository import rules_repo

logger = logging.getLogger(__name__)


class RulesRegistry:
    """Gestionnaire de Règles Modulaires à 2 niveaux (Global vs Local)."""

    def __init__(self) -> None:
        self.sync_filesystem_to_db()

    def sync_filesystem_to_db(self) -> list[RuleDefinition]:
        """Scanne les répertoires physiques et met à jour l'index SQLite."""
        synced: list[RuleDefinition] = []

        global_dir = settings.rules_dir
        if global_dir.exists():
            disk_rule_names: set[str] = set()
            for rule_file in global_dir.glob("*.md"):
                content = rule_file.read_text(encoding="utf-8")
                rule_name = rule_file.stem
                disk_rule_names.add(rule_name)
                rule = RuleDefinition(
                    name=rule_name,
                    category="Sécurité & Standards",
                    scope=RuleScope.GLOBAL,
                    project_id=None,
                    file_path=str(rule_file),
                    content=content,
                    is_active=True,
                )
                rules_repo.save_rule(rule)
                synced.append(rule)

            # Purge des règles orphelines supprimées du disque
            for db_rule in rules_repo.list_rules(scope=RuleScope.GLOBAL, active_only=False):
                if db_rule.name not in disk_rule_names:
                    rules_repo.delete_rule(db_rule.id)

        return synced

    def get_active_rules_xml(self, project_id: str | None = None) -> str:
        """Génère le bloc <rules> injecté systématiquement dans chaque appel LLM."""
        rules = rules_repo.list_rules(project_id=project_id, active_only=True)
        if not rules:
            return "<rules>\nAucune règle spécifique configurée.\n</rules>"

        lines = ["<rules>"]
        for r in rules:
            lines.append(f'  <rule name="{r.name}" category="{r.category}" scope="{r.scope.value}">')
            lines.append(f"    {r.content.strip()}")
            lines.append("  </rule>")
        lines.append("</rules>")
        return "\n".join(lines)

    def create_rule(
        self,
        name: str,
        category: str,
        content: str,
        scope: RuleScope = RuleScope.GLOBAL,
        project_id: str | None = None,
    ) -> RuleDefinition:
        """Crée une nouvelle règle physique (.md) et l'indexe dans SQLite."""
        target_dir = settings.rules_dir if scope == RuleScope.GLOBAL else settings.output_dir / (project_id or "temp") / "rules"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{name}.md"
        file_path.write_text(content.strip() + "\n", encoding="utf-8")

        rule = RuleDefinition(
            name=name,
            category=category,
            scope=scope,
            project_id=project_id,
            file_path=str(file_path),
            content=content.strip(),
            is_active=True,
        )
        return rules_repo.save_rule(rule)


rules_registry = RulesRegistry()
