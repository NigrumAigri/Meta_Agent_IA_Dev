#!/usr/bin/env python3
"""
Meta Developer Agent v5.0.0 — Script de Démarrage Rapide avec Auto-détection du .venv
"""
import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent
ROOT_DIR = PARENT_DIR.parent

# Auto-détection de l'interpréteur Python du .venv
potential_venvs = [
    BASE_DIR / ".venv",
    PARENT_DIR / ".venv",
    ROOT_DIR / ".venv",
]

venv_python = None
for venv_dir in potential_venvs:
    win_py = venv_dir / "Scripts" / "python.exe"
    nix_py = venv_dir / "bin" / "python"
    if win_py.exists():
        venv_python = win_py
        break
    elif nix_py.exists():
        venv_python = nix_py
        break

if venv_python and Path(sys.executable).resolve() != venv_python.resolve():
    try:
        result = subprocess.run([str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:])
        sys.exit(result.returncode)
    except Exception:
        pass

# Ajout du dossier v5 au sys.path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    import uvicorn
    from core.config import settings
except ImportError as e:
    print("=" * 70)
    print(f"Erreur d'environnement Python : {e}")
    print("Pour lancer avec l'environnement virtuel contenant FastAPI et Uvicorn :")
    print("   .\\.venv\\Scripts\\python.exe Meta_Agent_Dev_V5\\run.py")
    print("=" * 70)
    sys.exit(1)


def main():
    port = int(os.getenv("META_SERVER_PORT", "8000"))
    print("=" * 70)
    print("META DEVELOPER AGENT v5.0.0 — Enterprise Edition")
    print(f"Serveur disponible sur : http://127.0.0.1:{port}")
    print(f"Base de données SQLite  : {settings.db_path} (Mode WAL)")
    print(f"OpenRouter Connecté     : {'OUI' if settings.llm_api_key else 'NON'}")
    print(f"Artificial Analysis     : {'API v2 Live' if settings.artificial_analysis_api_key else 'Dataset Embarqué'}")
    print("=" * 70)

    uvicorn.run(
        "api.app:app",
        host="127.0.0.1",
        port=port,
        reload=True,
    )


if __name__ == "__main__":
    main()
