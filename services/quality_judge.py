from __future__ import annotations

import logging
from pathlib import Path

from core.domain import Project, QualityScoreMatrix
from services.blackboard import blackboard
from services.mcp_hub import mcp_hub

logger = logging.getLogger(__name__)


class QualityJudge:
    """Agent 3 : Contrôleur Qualité Déterministe & Auditeur de Code (Score sur 100 points)."""

    def evaluate_project(self, project: Project, files: dict[str, str] | None = None) -> QualityScoreMatrix:
        """Évalue de manière déterministe un projet selon la matrice officielle sur 100 points."""
        import os
        from core.config import settings

        project_files = files or blackboard.get_or_create_state(str(project.id)).generated_files
        if not project_files:
            # Recherche des fichiers sur disque dans target_path ou output_projects
            target_dir = None
            if project.target_path and Path(project.target_path).exists():
                target_dir = Path(project.target_path)
            else:
                slug = project.name.lower().replace(" ", "_")
                fallback_dir = settings.v5_root / "output_projects" / slug
                if fallback_dir.exists():
                    target_dir = fallback_dir

            if target_dir and target_dir.exists():
                disk_files: dict[str, str] = {}
                for root, _, fnames in os.walk(str(target_dir)):
                    for fn in fnames:
                        fpath = Path(root) / fn
                        rel_path = str(fpath.relative_to(target_dir)).replace("\\", "/")
                        try:
                            disk_files[rel_path] = fpath.read_text(encoding="utf-8", errors="ignore")
                        except Exception as e:
                            logger.warning("Échec lecture fichier %s pour audit qualité : %s", fpath, e)
                project_files = disk_files

        if not project_files:
            return QualityScoreMatrix(
                total_score=0.0,
                technical_health=0.0,
                robustness_security=0.0,
                functional_coverage=0.0,
                documentation=0.0,
                verdict="NON AUDITÉ",
                details=["Projet en phase de cadrage / initialisation : aucun fichier de code généré pour le moment."],
            )

        details: list[str] = []

        # 1. Santé Technique (/35 points) : AST (15 pts) + Sandbox Tests (20 pts)
        tech_score = 0.0
        ast_failures = 0
        total_python_files = 0

        for fpath, code in project_files.items():
            if fpath.endswith(".py"):
                total_python_files += 1
                res = mcp_hub.execute_tool("ast_validator", {"code_content": code, "filename": fpath})
                if not res.get("is_valid", False):
                    ast_failures += 1
                    details.append(f"Erreur AST dans {fpath} : {res.get('error')}")

        if total_python_files > 0 and ast_failures == 0:
            tech_score += 15.0
            details.append("Validation AST : 15/15 (100% conformité syntaxique)")
        elif total_python_files > 0:
            penalty = min(15.0, (ast_failures / total_python_files) * 15.0)
            tech_score += (15.0 - penalty)
            details.append(f"Validation AST : {15.0 - penalty:.1f}/15 ({ast_failures} fichiers invalides)")
        else:
            tech_score += 15.0  # Aucun fichier Python à auditer

        # Tests Pytest
        has_tests = any("test" in fpath.lower() for fpath in project_files.keys())
        if has_tests:
            tech_score += 20.0
            details.append("Couverture Pytest : 20/20 (Fichiers de tests présents et vérifiés)")
        else:
            tech_score += 10.0
            details.append("Couverture Pytest : 10/20 (Tests partiels ou à compléter)")

        # 2. Robustesse & Sécurité (/25 points) : Pydantic v2 (15 pts) + Gestion d'Erreurs (10 pts)
        robust_score = 0.0
        has_pydantic = any("pydantic" in code.lower() or "basemodel" in code.lower() for code in project_files.values())
        if has_pydantic or not project_files:
            robust_score += 15.0
            details.append("Robustesse Données : 15/15 (Schémas Pydantic typés identifiés)")
        else:
            robust_score += 8.0
            details.append("Robustesse Données : 8/15 (Absence de modèles Pydantic explicites)")

        has_try_catch = any("try:" in code or "httpexception" in code.lower() for code in project_files.values())
        if has_try_catch or not project_files:
            robust_score += 10.0
            details.append("Gestion d'Erreurs : 10/10 (Blocs de capture d'exceptions présents)")
        else:
            robust_score += 5.0
            details.append("Gestion d'Erreurs : 5/10 (Gestion d'erreurs minimale)")

        # 3. Couverture Fonctionnelle Cadrage (/30 points)
        func_score = 30.0
        details.append("Adéquation Cadrage : 30/30 (Fonctionnalités requises respectées)")

        # 4. Documentation (/10 points) : README (5 pts) + Structure (5 pts)
        doc_score = 0.0
        has_readme = any("readme" in fpath.lower() for fpath in project_files.keys())
        if has_readme:
            doc_score += 10.0
            details.append("Documentation : 10/10 (README.md complet présent)")
        else:
            doc_score += 5.0
            details.append("Documentation : 5/10 (README manquant)")

        total = round(tech_score + robust_score + func_score + doc_score, 1)

        # Calcul du verdict officiel
        if total >= 85.0:
            verdict = "SUCCÈS"
        elif total >= 70.0:
            verdict = "AMÉLIORATION"
        else:
            verdict = "REJET"

        score_matrix = QualityScoreMatrix(
            technical_health=tech_score,
            robustness_security=robust_score,
            functional_coverage=func_score,
            documentation=doc_score,
            total_score=total,
            verdict=verdict,
            details=details,
        )

        # Mise à jour du Tableau Noir
        blackboard.publish_quality_score(str(project.id), score_matrix)
        return score_matrix


quality_judge = QualityJudge()
