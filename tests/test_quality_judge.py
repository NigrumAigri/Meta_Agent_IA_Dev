from __future__ import annotations

import pytest
from core.domain import Project
from storage.repository import project_repo
from services.quality_judge import quality_judge


def test_quality_judge_perfect_score_evaluation():
    """Vérifie l'attribution d'un score de 100/100 et verdict SUCCÈS sur un projet parfait."""
    project = Project(name="CRM Perfect Enterprise")
    project_repo.save(project)

    files = {
        "src/main.py": "from fastapi import FastAPI\nfrom pydantic import BaseModel, ConfigDict\n\napp = FastAPI()\n\nclass Item(BaseModel):\n    model_config = ConfigDict(extra='forbid')\n    name: str\n\ntry:\n    pass\nexcept Exception:\n    pass\n",
        "tests/test_main.py": "def test_example():\n    assert True\n",
        "README.md": "# CRM Perfect\n\nDocumentation complète du projet.\n",
    }

    score_matrix = quality_judge.evaluate_project(project, files=files)

    assert score_matrix.total_score >= 85.0
    assert score_matrix.verdict == "SUCCÈS"
    assert score_matrix.technical_health >= 30.0
    assert score_matrix.robustness_security >= 20.0
    assert score_matrix.documentation == 10.0


def test_quality_judge_penalties_on_bad_code():
    """Vérifie les pénalités sur code avec syntaxe invalide ou composants manquants."""
    project = Project(name="Bad Code Project")
    project_repo.save(project)

    files = {
        "src/bad_syntax.py": "def invalid_func(:\n",
    }

    score_matrix = quality_judge.evaluate_project(project, files=files)
    assert score_matrix.total_score < 70.0
    assert score_matrix.verdict == "REJET"
    assert any("Erreur AST" in d for d in score_matrix.details)
