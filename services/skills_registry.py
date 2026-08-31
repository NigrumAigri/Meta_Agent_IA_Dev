from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.config import settings
from core.domain import SkillDefinition, SkillScope
from storage.repository import skills_repo

logger = logging.getLogger(__name__)


def parse_skill_md(file_path: Path) -> dict[str, Any]:
    """Parse le frontmatter YAML et le corps d'un fichier SKILL.md."""
    if not file_path.exists():
        return {}

    content = file_path.read_text(encoding="utf-8")
    metadata: dict[str, Any] = {
        "name": file_path.parent.name,
        "description": "Compétence technique spécialisée",
        "version": "1.0.0",
        "tags": [],
        "body": content,
    }

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_header = parts[1]
            metadata["body"] = parts[2].strip()
            for line in yaml_header.splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key == "name":
                    metadata["name"] = value
                elif key == "description":
                    metadata["description"] = value
                elif key == "version":
                    metadata["version"] = value
                elif key == "tags":
                    if value.startswith("[") and value.endswith("]"):
                        metadata["tags"] = [t.strip().strip("'\"") for t in value[1:-1].split(",") if t.strip()]

    return metadata


class SkillsRegistry:
    """Gestionnaire de Playbooks à 2 niveaux (Global vs Local) et Injection Just-In-Time."""

    def __init__(self) -> None:
        self.sync_filesystem_to_db()

    def sync_filesystem_to_db(self) -> list[SkillDefinition]:
        """Scanne les répertoires physiques et met à jour l'index SQLite."""
        synced: list[SkillDefinition] = []

        # 1. Scanner les Skills Globaux (skills/)
        global_dir = settings.skills_dir
        if global_dir.exists():
            disk_skill_names: set[str] = set()
            for skill_folder in global_dir.iterdir():
                if skill_folder.is_dir():
                    skill_file = skill_folder / "SKILL.md"
                    if skill_file.exists():
                        meta = parse_skill_md(skill_file)
                        s_name = meta.get("name", skill_folder.name)
                        disk_skill_names.add(s_name)
                        skill = SkillDefinition(
                            name=s_name,
                            description=meta.get("description", ""),
                            version=meta.get("version", "1.0.0"),
                            scope=SkillScope.GLOBAL,
                            project_id=None,
                            file_path=str(skill_file),
                            tags=meta.get("tags", []),
                            is_active=True,
                        )
                        skills_repo.save_skill(skill)
                        synced.append(skill)

            # Purge des skills orphelins supprimés du disque
            for db_skill in skills_repo.list_skills(scope=SkillScope.GLOBAL):
                if db_skill.name not in disk_skill_names:
                    skills_repo.delete_skill(db_skill.id)

            # Synchronisation de l'index FTS5 via rebuild natif
            try:
                from storage.sqlite_db import db
                db.execute("INSERT INTO skills_fts(skills_fts) VALUES('rebuild');")
            except Exception as e:
                logger.warning("Erreur synchronisation FTS5 skills: %s", e)

        return synced

    def get_available_skills_xml(self, project_id: str | None = None) -> str:
        """Génère le bloc <available_skills> léger (~50 tokens) pour le prompt système au repos."""
        skills = skills_repo.list_skills(project_id=project_id)
        if not skills:
            return "<available_skills>\nAucune compétence spécialisée au repos.\n</available_skills>"

        lines = ["<available_skills>"]
        for s in skills:
            if s.is_active:
                lines.append(f'  <skill name="{s.name}" scope="{s.scope.value}">')
                lines.append(f"    <description>{s.description}</description>")
                lines.append("  </skill>")
        lines.append("</available_skills>")
        return "\n".join(lines)

    def load_skill_body(self, skill_name: str, project_id: str | None = None) -> str | None:
        """Charge le contenu complet du Playbook à l'activation de la compétence."""
        skills = skills_repo.list_skills(project_id=project_id)
        skill = next((s for s in skills if s.name == skill_name and s.is_active), None)
        if not skill:
            return None

        path = Path(skill.file_path)
        if path.exists():
            # Incrémenter le compteur d'invocations
            skill.invocations_count += 1
            skills_repo.save_skill(skill)
            meta = parse_skill_md(path)
            return meta.get("body", path.read_text(encoding="utf-8"))
        return None

    def get_skill_details(self, skill_name: str, project_id: str | None = None) -> dict[str, Any] | None:
        """Récupère les détails complets d'un skill, son playbook et la liste de ses fichiers de support."""
        skills = skills_repo.list_skills(project_id=project_id)
        skill = next((s for s in skills if s.name == skill_name), None)
        if not skill:
            return None

        path = Path(skill.file_path)
        body = ""
        resources: list[str] = []
        if path.exists():
            meta = parse_skill_md(path)
            body = meta.get("body", path.read_text(encoding="utf-8"))
            skill_folder = path.parent
            for sub_f in skill_folder.rglob("*"):
                if sub_f.is_file() and sub_f.name != "SKILL.md":
                    resources.append(str(sub_f.relative_to(skill_folder)).replace("\\", "/"))

        d = skill.model_dump(mode="json")
        d["instructions_md"] = body
        d["available_resources"] = resources
        return d

    def create_skill(
        self,
        name: str,
        description: str,
        instructions_md: str,
        scope: SkillScope = SkillScope.GLOBAL,
        project_id: str | None = None,
        tags: list[str] | None = None,
    ) -> SkillDefinition:
        """Crée un nouveau Playbook physique et l'indexe dans SQLite."""
        target_dir = settings.skills_dir / name if scope == SkillScope.GLOBAL else settings.output_dir / (project_id or "temp") / ".skills" / name
        target_dir.mkdir(parents=True, exist_ok=True)
        skill_file = target_dir / "SKILL.md"

        yaml_tags = f"[{', '.join(tags or [])}]"
        content = f"""---
name: {name}
description: {description}
version: 1.0.0
tags: {yaml_tags}
---

{instructions_md.strip()}
"""
        skill_file.write_text(content, encoding="utf-8")

        skill = SkillDefinition(
            name=name,
            description=description,
            version="1.0.0",
            scope=scope,
            project_id=project_id,
            file_path=str(skill_file),
            tags=tags or [],
            is_active=True,
        )
        return skills_repo.save_skill(skill)


skills_registry = SkillsRegistry()
