from __future__ import annotations

import io
import zipfile
import pytest
from core.domain import Project
from storage.repository import project_repo
from services.project_exporter import project_exporter


def test_project_exporter_scaffold_and_zip_creation():
    """Vérifie l'écriture des fichiers du sous-projet et la création de l'archive ZIP valide."""
    project = Project(name="Analytics Dashboard Pro")
    project_repo.save(project)

    # 1. Scaffolding
    written = project_exporter.scaffold_project_files(project)
    assert len(written) >= 4
    assert project.target_path != ""

    # 2. Création ZIP
    zip_bytes = project_exporter.create_zip_archive(project)
    assert len(zip_bytes) > 0

    # 3. Vérification intégrité du ZIP
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
        file_list = z.namelist()
        assert "src/main.py" in file_list or "src\\main.py" in file_list
        assert "README.md" in file_list
        assert "requirements.txt" in file_list
