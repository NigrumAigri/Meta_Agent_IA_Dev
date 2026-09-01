from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

V5_ROOT_DIR = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    """Charge ou recharge les variables du fichier .env sans dépendance externe."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ[key] = value


# Chargement initial depuis .env local ou racine
load_env_file(V5_ROOT_DIR / ".env")


@dataclass
class Settings:
    v5_root: Path
    data_dir: Path
    db_path: Path
    output_dir: Path
    skills_dir: Path
    rules_dir: Path
    hooks_dir: Path
    commands_dir: Path
    llm_provider: str
    llm_base_url: str
    llm_api_key: str | None
    artificial_analysis_api_key: str | None
    llm_discovery_model: str
    llm_coder_model: str
    server_port: int
    ast_validation_enabled: bool = True
    hitl_validation_enabled: bool = True
    circuit_breaker_enabled: bool = True
    prompt_caching_enabled: bool = True

    @classmethod
    def from_environment(cls) -> "Settings":
        v5_root = V5_ROOT_DIR
        data_env = os.getenv("META_DATA_DIR")
        data_dir = Path(data_env) if data_env and Path(data_env).is_absolute() else v5_root / (data_env or "data")
        db_path = data_dir / "meta_agent.db"

        output_env = os.getenv("META_OUTPUT_DIR")
        output_dir = Path(output_env) if output_env and Path(output_env).is_absolute() else v5_root / (output_env or "output_projects")

        skills_dir = v5_root / "skills"
        rules_dir = v5_root / "rules"
        hooks_dir = v5_root / "hooks"
        commands_dir = v5_root / "commands"

        # Création automatique des répertoires de persistance
        data_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.mkdir(parents=True, exist_ok=True)
        rules_dir.mkdir(parents=True, exist_ok=True)
        hooks_dir.mkdir(parents=True, exist_ok=True)
        commands_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            v5_root=v5_root,
            data_dir=data_dir,
            db_path=db_path,
            output_dir=output_dir,
            skills_dir=skills_dir,
            rules_dir=rules_dir,
            hooks_dir=hooks_dir,
            commands_dir=commands_dir,
            llm_provider=os.getenv("META_LLM_PROVIDER", "openrouter").lower(),
            llm_base_url=os.getenv("META_LLM_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
            llm_api_key=os.getenv("META_LLM_API_KEY") or None,
            artificial_analysis_api_key=os.getenv("META_ARTIFICIAL_ANALYSIS_API_KEY") or None,
            llm_discovery_model=os.getenv("META_LLM_DISCOVERY_MODEL", "moonshotai/kimi-k3"),
            llm_coder_model=os.getenv("META_LLM_CODER_MODEL", "qwen/qwen-2.5-coder-32b-instruct"),
            server_port=int(os.getenv("META_SERVER_PORT", "8000")),
            ast_validation_enabled=os.getenv("META_AST_VALIDATION_ENABLED", "true").lower() in ("true", "1", "yes"),
            hitl_validation_enabled=os.getenv("META_HITL_VALIDATION_ENABLED", "true").lower() in ("true", "1", "yes"),
            circuit_breaker_enabled=os.getenv("META_CIRCUIT_BREAKER_ENABLED", "true").lower() in ("true", "1", "yes"),
            prompt_caching_enabled=os.getenv("META_PROMPT_CACHING_ENABLED", "true").lower() in ("true", "1", "yes"),
        )

    @property
    def is_openrouter_connected(self) -> bool:
        return bool(self.get_llm_api_key())

    @property
    def is_artificial_analysis_live(self) -> bool:
        return bool(self.get_aa_api_key())

    def get_llm_api_key(self) -> str | None:
        """Retourne la clé API OpenRouter avec résolution dynamique JIT depuis SQLite."""
        if self.llm_api_key and self.llm_api_key.strip():
            return self.llm_api_key.strip()
        try:
            import sqlite3
            if self.db_path.exists():
                conn = sqlite3.connect(str(self.db_path), timeout=3.0)
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_settings';")
                if cursor.fetchone():
                    row = conn.execute("SELECT value FROM system_settings WHERE key='llm_api_key' LIMIT 1;").fetchone()
                    if row and row["value"]:
                        val = row["value"].strip()
                        self.llm_api_key = val
                        conn.close()
                        return val
                conn.close()
        except Exception:
            pass
        return os.getenv("META_LLM_API_KEY") or None

    def get_aa_api_key(self) -> str | None:
        """Retourne la clé API Artificial Analysis avec résolution dynamique JIT depuis SQLite."""
        if self.artificial_analysis_api_key and self.artificial_analysis_api_key.strip():
            return self.artificial_analysis_api_key.strip()
        try:
            import sqlite3
            if self.db_path.exists():
                conn = sqlite3.connect(str(self.db_path), timeout=3.0)
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_settings';")
                if cursor.fetchone():
                    row = conn.execute("SELECT value FROM system_settings WHERE key='artificial_analysis_api_key' LIMIT 1;").fetchone()
                    if row and row["value"]:
                        val = row["value"].strip()
                        self.artificial_analysis_api_key = val
                        conn.close()
                        return val
                conn.close()
        except Exception:
            pass
        return os.getenv("META_ARTIFICIAL_ANALYSIS_API_KEY") or os.getenv("ARTIFICIAL_ANALYSIS_API_KEY") or None


# Instance de démarrage initial
settings: Settings = Settings.from_environment()


def reload_settings() -> Settings:
    """Force le rechargement du fichier .env et des paramètres dynamiques SQLite."""
    global settings
    current_db_path = getattr(settings, "db_path", None)
    current_output_dir = getattr(settings, "output_dir", None)
    current_data_dir = getattr(settings, "data_dir", None)
    load_env_file(V5_ROOT_DIR / ".env")
    new_s = Settings.from_environment()
    if current_db_path:
        new_s.db_path = current_db_path
    if current_output_dir:
        new_s.output_dir = current_output_dir
    if current_data_dir:
        new_s.data_dir = current_data_dir

    # Charger les surcharges dynamiques depuis SQLite si la base existe
    try:
        import sqlite3
        if new_s.db_path.exists():
            conn = sqlite3.connect(str(new_s.db_path), timeout=5.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_settings';")
            if cursor.fetchone():
                rows = conn.execute("SELECT key, value FROM system_settings;").fetchall()
                for row in rows:
                    k, v = row["key"], row["value"]
                    if k == "llm_api_key":
                        new_s.llm_api_key = v or None
                    elif k == "artificial_analysis_api_key":
                        new_s.artificial_analysis_api_key = v or None
                    elif k == "llm_provider":
                        new_s.llm_provider = v
                    elif k == "llm_base_url":
                        new_s.llm_base_url = v
                    elif k == "llm_discovery_model":
                        new_s.llm_discovery_model = v
                    elif k == "llm_coder_model":
                        new_s.llm_coder_model = v
                    elif k == "ast_validation_enabled":
                        new_s.ast_validation_enabled = v.lower() in ("true", "1", "yes")
                    elif k == "hitl_validation_enabled":
                        new_s.hitl_validation_enabled = v.lower() in ("true", "1", "yes")
                    elif k == "circuit_breaker_enabled":
                        new_s.circuit_breaker_enabled = v.lower() in ("true", "1", "yes")
                    elif k == "prompt_caching_enabled":
                        new_s.prompt_caching_enabled = v.lower() in ("true", "1", "yes")
            conn.close()
    except Exception:
        pass

    for field_name, value in new_s.__dict__.items():
        setattr(settings, field_name, value)
    return settings


def update_env_variable(key: str, value: str | None) -> None:
    """Met à jour une variable dans le fichier .env et recharge la configuration."""
    env_file = V5_ROOT_DIR / ".env"
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    new_lines = []
    found = False

    for line in lines:
        if line.startswith(f"{key}="):
            if value is not None:
                new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)

    if not found and value is not None:
        new_lines.append(f"{key}={value}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    if value is not None:
        os.environ[key] = value
    elif key in os.environ:
        del os.environ[key]

    reload_settings()


# Initialisation active complète au chargement du module
reload_settings()
