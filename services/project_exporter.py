from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

from core.config import settings
from core.domain import Project
from storage.repository import project_repo
from services.blackboard import blackboard
from services.mcp_hub import mcp_hub

logger = logging.getLogger(__name__)


class ProjectExporter:
    """Gestionnaire de persistance des sous-projets et Export Archive ZIP."""

    def get_project_target_dir(self, project: Project) -> Path:
        """Retourne le chemin absolu du dossier sous-projet (personnalisé ou dans output_projects/)."""
        if project.target_path and project.target_path.strip():
            target_dir = Path(project.target_path.strip()).resolve()
        else:
            safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project.name.lower())
            target_dir = settings.output_dir / safe_name
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def scaffold_project_files(self, project: Project, files: dict[str, str] | None = None) -> list[str]:
        """Écrit tous les fichiers du sous-projet de manière atomique sur le disque."""
        target_dir = self.get_project_target_dir(project)
        project_files = files or blackboard.get_or_create_state(str(project.id)).generated_files
        written_files: list[str] = []

        # Si aucun fichier n'a été généré, créer le scaffold minimal
        if not project_files:
            project_files = {
                "src/__init__.py": '"""Package principal."""\n',
                "src/main.py": '"""Point d\'entrée FastAPI."""\nfrom fastapi import FastAPI\n\napp = FastAPI(title="' + project.name + '")\n\n@app.get("/")\ndef read_root():\n    return {"status": "online", "project": "' + project.name + '"}\n',
                "tests/__init__.py": "",
                "tests/test_main.py": 'from fastapi.testclient import TestClient\nfrom src.main import app\n\nclient = TestClient(app)\n\ndef test_root():\n    res = client.get("/")\n    assert res.status_code == 200\n',
                "requirements.txt": "fastapi>=0.115.0\nuvicorn[standard]>=0.32.0\npydantic>=2.10.0\npytest>=8.0.0\nhttpx>=0.28.0\n",
                "README.md": f"# {project.name}\n\nApplication générée par **Meta Developer Agent v5.0.0 Enterprise**.\n\n## Lancement\n```bash\nuvicorn src.main:app --reload\n```\n",
            }

        for rel_path, content in project_files.items():
            dest_file = target_dir / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            res = mcp_hub.execute_tool("file_writer_atomic", {"file_path": str(dest_file), "content": content})
            if res.get("status") == "success":
                written_files.append(str(dest_file))

        project.target_path = str(target_dir)
        project.generated_files = list(project_files.keys())
        project_repo.save(project)

        return written_files

    def create_zip_archive(self, project: Project) -> bytes:
        """Génère l'archive ZIP en mémoire prête pour le téléchargement."""
        target_dir = self.get_project_target_dir(project)
        # S'assurer que les fichiers sont bien écrits sur disque
        self.scaffold_project_files(project)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in target_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.endswith(".tmp"):
                    archive_name = file_path.relative_to(target_dir)
                    zip_file.write(file_path, arcname=str(archive_name))

        zip_buffer.seek(0)
        return zip_buffer.getvalue()


project_exporter = ProjectExporter()
