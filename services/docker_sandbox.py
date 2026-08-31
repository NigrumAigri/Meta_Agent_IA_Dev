from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DockerSandboxManager:
    """Gestionnaire de Sandbox Docker Éphémère (Norme Module 11 de la Knowledge Base).
    
    Garantit l'exécution de code et tests dans un conteneur hermétique :
    - Mode lecture seule (-v :ro)
    - Réseau désactivé (--network none)
    - Limite mémoire (512 MB) et CPU (1.0)
    - Destruction automatique immédiate (--rm)
    - Allumage automatique de Docker Desktop sous Windows si éteint.
    """

    def __init__(self, docker_image: str = "python:3.11-slim") -> None:
        self.docker_image = docker_image
        self._docker_bin = shutil.which("docker")

    def is_docker_installed(self) -> bool:
        """Vérifie si l'exécutable docker est présent dans le PATH."""
        return self._docker_bin is not None

    def is_docker_daemon_running(self) -> bool:
        """Vérifie en temps réel (1.5s max) si le daemon Docker répond."""
        if not self.is_docker_installed():
            return False
        try:
            res = subprocess.run(
                [self._docker_bin, "info"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            return res.returncode == 0
        except Exception:
            return False

    def auto_start_docker_desktop(self, wait_timeout: float = 25.0) -> bool:
        """Démarre Docker Desktop sous Windows en arrière-plan et attend activement qu'il soit prêt."""
        if self.is_docker_daemon_running():
            return True

        if platform.system().lower() == "windows":
            docker_desktop_paths = [
                r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
                os.path.expandvars(r"%ProgramFiles%\Docker\Docker\Docker Desktop.exe"),
            ]
            started = False
            for p in docker_desktop_paths:
                if Path(p).exists():
                    try:
                        logger.info("Démarrage automatique de Docker Desktop via %s...", p)
                        subprocess.Popen([p], close_fds=True)
                        started = True
                        break
                    except Exception as e:
                        logger.warning("Échec démarrage direct Docker Desktop: %s", e)

            if not started:
                try:
                    subprocess.Popen(["powershell", "-Command", "Start-Process 'Docker Desktop'"], close_fds=True)
                    started = True
                except Exception as e:
                    logger.warning("Échec démarrage Powershell Docker Desktop: %s", e)

            if started:
                # Boucle d'attente active
                start_time = time.time()
                while time.time() - start_time < wait_timeout:
                    time.sleep(2.0)
                    if self.is_docker_daemon_running():
                        logger.info("Docker Desktop est désormais actif et prêt.")
                        return True

        return self.is_docker_daemon_running()

    def run_tests_in_sandbox(
        self,
        target_dir: str | Path,
        pytest_args: list[str] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Exécute les tests Pytest dans un conteneur éphémère Docker hermétique."""
        abs_path = Path(target_dir).resolve()
        if not abs_path.exists():
            return {
                "status": "error",
                "message": f"Dossier de tests introuvable sur disque : {abs_path}",
                "sandbox_type": "none",
            }

        # 1. Vérification / Allumage de Docker
        if not self.is_docker_daemon_running():
            logger.info("Docker daemon non détecté. Tentative d'allumage automatique...")
            is_ready = self.auto_start_docker_desktop(wait_timeout=20.0)
            if not is_ready:
                return {
                    "status": "error",
                    "message": "Docker Desktop est éteint ou inaccessible. Impossible d'exécuter la sandbox sécurisée.",
                    "sandbox_type": "docker_offline",
                }

        # 2. Préparation des arguments Docker
        # Conversion du chemin Windows en format compatible pour montage volume
        posix_mount = str(abs_path).replace("\\", "/")
        args = pytest_args or ["-v"]

        cmd = [
            self._docker_bin or "docker",
            "run",
            "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1.0",
            "-v", f"{posix_mount}:/workspace:ro",
            "-w", "/workspace",
            self.docker_image,
            "pytest",
        ] + args

        start_exec = time.time()
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed_ms = round((time.time() - start_exec) * 1000, 2)
            is_success = res.returncode == 0

            return {
                "status": "success" if is_success else "failure",
                "returncode": res.returncode,
                "stdout": res.stdout[:8000],
                "stderr": res.stderr[:3000],
                "execution_time_ms": elapsed_ms,
                "sandbox_type": "docker_ephemeral_container",
                "security": "READ_ONLY_NO_NETWORK_512MB",
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "message": f"Délai d'exécution Sandbox dépassé ({timeout}s). Arrêt forcé du conteneur.",
                "sandbox_type": "docker_timeout",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Erreur lors de l'exécution Docker Sandbox : {str(e)}",
                "sandbox_type": "docker_error",
            }


docker_sandbox = DockerSandboxManager()
