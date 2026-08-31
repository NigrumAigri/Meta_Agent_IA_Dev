from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Sequence

from core.config import settings

_LOCAL_STORAGE = threading.local()
_DB_LOCK = threading.RLock()


class SqliteDatabase:
    """Gestionnaire de base de données SQLite transactionnelle en mode WAL."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Retourne une connexion SQLite isolée par thread configurée en mode WAL."""
        if not hasattr(_LOCAL_STORAGE, "connection") or _LOCAL_STORAGE.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=10.0,
                check_same_thread=False,
                isolation_level=None,  # Autocommit par défaut, géré par transactions explicites
            )
            conn.row_factory = sqlite3.Row
            # Directives de performance et d'intégrité ACID
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA foreign_keys = ON;")
            _LOCAL_STORAGE.connection = conn
        return _LOCAL_STORAGE.connection

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Gestionnaire de transaction atomique ACID."""
        conn = self.get_connection()
        with _DB_LOCK:
            conn.execute("BEGIN IMMEDIATE;")
            try:
                yield conn
                conn.execute("COMMIT;")
            except Exception:
                conn.execute("ROLLBACK;")
                raise

    def execute(self, query: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Exécute une requête SQL avec paramètres de façon sécurisée."""
        with _DB_LOCK:
            conn = self.get_connection()
            return conn.execute(query, params)

    def executemany(self, query: str, seq_of_params: Sequence[Sequence[Any]]) -> sqlite3.Cursor:
        with _DB_LOCK:
            conn = self.get_connection()
            return conn.executemany(query, seq_of_params)

    def fetch_one(self, query: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        with _DB_LOCK:
            cursor = self.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with _DB_LOCK:
            cursor = self.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def init_schema(self) -> None:
        """Initialise le schéma relationnel complet des 16 tables v5."""
        schema_sql = """
        -- 1. Table des Projets
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            target_path TEXT NOT NULL DEFAULT '',
            selected_finops_profile TEXT NOT NULL DEFAULT 'sweet_spot',
            budget_limit_usd REAL NOT NULL DEFAULT 10.0,
            active_thread_id TEXT,
            documents_json TEXT NOT NULL DEFAULT '[]',
            generated_files_json TEXT NOT NULL DEFAULT '[]',
            is_archived INTEGER NOT NULL DEFAULT 0,
            deleted_at TEXT DEFAULT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 2. Table des Threads (Discussions multiples par projet)
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT 'Discussion',
            is_pinned INTEGER NOT NULL DEFAULT 0,
            is_archived INTEGER NOT NULL DEFAULT 0,
            is_unread INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- 3. Table des Messages du Studio Projet (Étanche)
        CREATE TABLE IF NOT EXISTS project_messages (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            author_name TEXT,
            agent_id TEXT,
            attachments_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- 4. Table des Messages du Copilote Système (Étanche)
        CREATE TABLE IF NOT EXISTS system_copilot_messages (
            id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            author_name TEXT,
            attachments_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );

        -- 5. Table des Agents (Topologie Canvas & Hyperparamètres)
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            project_id TEXT DEFAULT NULL,
            role_description TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            goal TEXT NOT NULL DEFAULT '',
            backstory TEXT NOT NULL DEFAULT '',
            agent_type TEXT NOT NULL DEFAULT 'custom',
            parent_id TEXT,
            model TEXT NOT NULL,
            temperature REAL NOT NULL DEFAULT 0.2,
            max_tokens INTEGER NOT NULL DEFAULT 4096,
            timeout_seconds REAL NOT NULL DEFAULT 60.0,
            reasoning_effort TEXT NOT NULL DEFAULT 'medium',
            max_iter INTEGER NOT NULL DEFAULT 5,
            budget_limit_usd REAL NOT NULL DEFAULT 5.0,
            system_prompt TEXT NOT NULL DEFAULT '',
            allow_delegation INTEGER NOT NULL DEFAULT 1,
            tools_json TEXT NOT NULL DEFAULT '[]',
            skills_json TEXT NOT NULL DEFAULT '[]',
            rules_json TEXT NOT NULL DEFAULT '[]',
            is_active INTEGER NOT NULL DEFAULT 1,
            is_core_meta_agent INTEGER NOT NULL DEFAULT 0,
            canvas_x REAL NOT NULL DEFAULT 0.0,
            canvas_y REAL NOT NULL DEFAULT 0.0,
            icon TEXT NOT NULL DEFAULT 'layers',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 6. Grand Livre FinOps (Inférences & Tokens réels)
        CREATE TABLE IF NOT EXISTS finops_ledger (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            session_id TEXT NOT NULL DEFAULT 'global',
            project_id TEXT,
            project_name TEXT NOT NULL DEFAULT 'Global',
            agent_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            model TEXT NOT NULL,
            task_name TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            reasoning_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0.0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            ttft_ms INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'success'
        );


        -- 8. Serveurs MCP Externes (stdio / SSE)
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            transport TEXT NOT NULL DEFAULT 'stdio',
            command_or_url TEXT NOT NULL,
            args_json TEXT NOT NULL DEFAULT '[]',
            env_json TEXT NOT NULL DEFAULT '{}',
            project_id TEXT DEFAULT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'configured',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 9. Catalogue des Outils MCP
        CREATE TABLE IF NOT EXISTS mcp_tools (
            id TEXT PRIMARY KEY,
            server_id TEXT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Système',
            parameters_schema_json TEXT NOT NULL DEFAULT '{}',
            project_id TEXT DEFAULT NULL,
            mcp_primitive TEXT NOT NULL DEFAULT 'tool',
            is_idempotent INTEGER NOT NULL DEFAULT 0,
            is_critical INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            is_core INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE
        );

        -- Index Virtuel Full-Text Search FTS5 pour le Tool RAG
        CREATE VIRTUAL TABLE IF NOT EXISTS mcp_tools_fts USING fts5(
            id UNINDEXED,
            name,
            description,
            category,
            content='mcp_tools',
            content_rowid='rowid'
        );

        -- 10. Index des Compétences (Skills à 2 Niveaux)
        CREATE TABLE IF NOT EXISTS skills_index (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '1.0.0',
            scope TEXT NOT NULL DEFAULT 'global',
            project_id TEXT,
            file_path TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            invocations_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- Index Virtuel Full-Text Search FTS5 pour le Skill RAG
        CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
            name,
            description,
            tags_json,
            content='skills_index',
            content_rowid='rowid'
        );

        -- 11. Index des Règles Modulaires (Rules à 2 Niveaux)
        CREATE TABLE IF NOT EXISTS rules_index (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Sécurité',
            scope TEXT NOT NULL DEFAULT 'global',
            project_id TEXT,
            file_path TEXT NOT NULL,
            content TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_rules_unique_name ON rules_index (name, scope, COALESCE(project_id, 'global'));

        -- 12. Index des Écouteurs de Cycle de Vie (Hooks)
        CREATE TABLE IF NOT EXISTS hooks_index (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL,
            action_type TEXT NOT NULL DEFAULT 'validator',
            target TEXT NOT NULL DEFAULT '',
            config_json TEXT NOT NULL DEFAULT '{}',
            scope TEXT NOT NULL DEFAULT 'global',
            project_id TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 12.bis. Journal d'Audit des Sentinelles (Hooks Audit Trail)
        CREATE TABLE IF NOT EXISTS hooks_audit_log (
            id TEXT PRIMARY KEY,
            hook_id TEXT NOT NULL,
            hook_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms REAL NOT NULL DEFAULT 0.0,
            payload_summary TEXT NOT NULL DEFAULT '',
            result_summary TEXT NOT NULL DEFAULT '',
            error TEXT,
            project_id TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_hooks_audit_created ON hooks_audit_log(created_at DESC);

        -- 13. Index des Slash Commands (Commands)
        CREATE TABLE IF NOT EXISTS commands_index (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            usage TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'Système',
            handler_type TEXT NOT NULL DEFAULT 'native',
            target TEXT NOT NULL DEFAULT '',
            scope TEXT NOT NULL DEFAULT 'global',
            project_id TEXT DEFAULT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 14. Leçons Apprises & Mémoire d'Erreurs
        CREATE TABLE IF NOT EXISTS lessons_learned (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL DEFAULT 'global',
            project_id TEXT,
            topic TEXT NOT NULL,
            problem_statement TEXT NOT NULL,
            solution_applied TEXT NOT NULL,
            prevention_rule TEXT NOT NULL DEFAULT '',
            confidence_score REAL NOT NULL DEFAULT 0.95,
            status TEXT NOT NULL DEFAULT 'approved',
            created_at TEXT NOT NULL
        );

        -- 15. Checkpoints & Snapshots Time Travel
        CREATE TABLE IF NOT EXISTS checkpoints (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            thread_id TEXT,
            step_name TEXT NOT NULL,
            state_json TEXT NOT NULL DEFAULT '{}',
            files_snapshot_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- 16. File d'Attente de Validation Humaine (HITL)
        CREATE TABLE IF NOT EXISTS hitl_requests (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            agent_id TEXT,
            request_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            rejection_reason TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT
        );

        -- 17. Cache Complet des Modèles OpenRouter (400+ modèles)
        CREATE TABLE IF NOT EXISTS openrouter_models_cache (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            context_length INTEGER NOT NULL DEFAULT 128000,
            price_in_usd REAL NOT NULL DEFAULT 0.0,
            price_out_usd REAL NOT NULL DEFAULT 0.0,
            price_cache_usd REAL NOT NULL DEFAULT 0.0,
            reasoning INTEGER NOT NULL DEFAULT 0,
            reasoning_json TEXT NOT NULL DEFAULT '{}',
            reasoning_type TEXT NOT NULL DEFAULT 'none',
            reasoning_options_json TEXT NOT NULL DEFAULT '[]',
            supported_parameters_json TEXT NOT NULL DEFAULT '[]',
            architecture_json TEXT NOT NULL DEFAULT '{}',
            top_provider_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        );

        -- 18. Liaisons Dynamiques Multi-Agents (Canvas 2D DAG Wires)
        CREATE TABLE IF NOT EXISTS agent_links (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            source_agent_id TEXT NOT NULL,
            target_agent_id TEXT NOT NULL,
            link_type TEXT NOT NULL DEFAULT 'data_flow',
            label TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_agent_id) REFERENCES agents(id) ON DELETE CASCADE,
            FOREIGN KEY (target_agent_id) REFERENCES agents(id) ON DELETE CASCADE
        );

        -- 19. Propositions d'Actions Proactives (Action Proposals)
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            proposal_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            benefit TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            resolved_at TEXT
        );

        -- 20. Paramètres et Clés Dynamiques Système (Persistés en base de données SQLite)
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 21. Cache Dynamique des Benchmarks Certifiés Artificial Analysis (v2 - Pur JSON)
        CREATE TABLE IF NOT EXISTS aa_benchmarks_cache (
            id TEXT PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            creator_name TEXT NOT NULL,
            creator_slug TEXT NOT NULL DEFAULT '',
            release_date TEXT DEFAULT '',
            price_in_usd REAL NOT NULL DEFAULT 0.0,
            price_out_usd REAL NOT NULL DEFAULT 0.0,
            price_cache_usd REAL NOT NULL DEFAULT 0.0,
            price_blended_usd REAL NOT NULL DEFAULT 0.0,
            evaluations_json TEXT NOT NULL DEFAULT '{}',
            raw_payload_json TEXT NOT NULL DEFAULT '{}',
            last_synced_at TEXT NOT NULL
        );

        -- Index d'optimisation
        CREATE INDEX IF NOT EXISTS idx_threads_project ON threads(project_id);
        CREATE INDEX IF NOT EXISTS idx_project_messages_thread ON project_messages(thread_id);
        CREATE INDEX IF NOT EXISTS idx_finops_timestamp ON finops_ledger(timestamp);
        CREATE INDEX IF NOT EXISTS idx_checkpoints_project ON checkpoints(project_id);
        CREATE INDEX IF NOT EXISTS idx_hitl_status ON hitl_requests(status);
        CREATE INDEX IF NOT EXISTS idx_models_reasoning ON openrouter_models_cache(reasoning);
        CREATE INDEX IF NOT EXISTS idx_aa_slug ON aa_benchmarks_cache(slug);
        CREATE INDEX IF NOT EXISTS idx_agent_links_source ON agent_links(source_agent_id);
        CREATE INDEX IF NOT EXISTS idx_agent_links_target ON agent_links(target_agent_id);
        CREATE INDEX IF NOT EXISTS idx_proposals_project ON proposals(project_id);
        CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_lessons_unique_topic ON lessons_learned (topic, COALESCE(project_id, 'global'));
        """
        with _DB_LOCK:
            conn = self.get_connection()
            conn.executescript(schema_sql)
            
            # Migration sûre des colonnes si la BDD existe déjà
            existing_cols_agents = {r[1] for r in conn.execute("PRAGMA table_info(agents);").fetchall()}
            for col, ddl in [
                ("project_id", "ALTER TABLE agents ADD COLUMN project_id TEXT DEFAULT NULL;"),
                ("role", "ALTER TABLE agents ADD COLUMN role TEXT NOT NULL DEFAULT '';"),
                ("goal", "ALTER TABLE agents ADD COLUMN goal TEXT NOT NULL DEFAULT '';"),
                ("backstory", "ALTER TABLE agents ADD COLUMN backstory TEXT NOT NULL DEFAULT '';"),
                ("budget_limit_usd", "ALTER TABLE agents ADD COLUMN budget_limit_usd REAL NOT NULL DEFAULT 5.0;"),
                ("system_prompt", "ALTER TABLE agents ADD COLUMN system_prompt TEXT NOT NULL DEFAULT '';"),
            ]:
                if col not in existing_cols_agents:
                    try:
                        conn.execute(ddl)
                    except Exception:
                        pass

            existing_cols_models = {r[1] for r in conn.execute("PRAGMA table_info(openrouter_models_cache);").fetchall()}
            for col, ddl in [
                ("reasoning_json", "ALTER TABLE openrouter_models_cache ADD COLUMN reasoning_json TEXT NOT NULL DEFAULT '{}';"),
                ("reasoning_type", "ALTER TABLE openrouter_models_cache ADD COLUMN reasoning_type TEXT NOT NULL DEFAULT 'none';"),
                ("reasoning_options_json", "ALTER TABLE openrouter_models_cache ADD COLUMN reasoning_options_json TEXT NOT NULL DEFAULT '[]';"),
            ]:
                if col not in existing_cols_models:
                    try:
                        conn.execute(ddl)
                    except Exception:
                        pass

            existing_cols_threads = {r[1] for r in conn.execute("PRAGMA table_info(threads);").fetchall()}
            for col, ddl in [
                ("is_pinned", "ALTER TABLE threads ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0;"),
                ("is_archived", "ALTER TABLE threads ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;"),
                ("is_unread", "ALTER TABLE threads ADD COLUMN is_unread INTEGER NOT NULL DEFAULT 0;"),
            ]:
                if col not in existing_cols_threads:
                    try:
                        conn.execute(ddl)
                    except Exception:
                        pass

            existing_cols_projects = {r[1] for r in conn.execute("PRAGMA table_info(projects);").fetchall()}
            for col, ddl in [
                ("is_archived", "ALTER TABLE projects ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;"),
                ("deleted_at", "ALTER TABLE projects ADD COLUMN deleted_at TEXT DEFAULT NULL;"),
                ("documents_json", "ALTER TABLE projects ADD COLUMN documents_json TEXT NOT NULL DEFAULT '[]';"),
                ("generated_files_json", "ALTER TABLE projects ADD COLUMN generated_files_json TEXT NOT NULL DEFAULT '[]';"),
            ]:
                if col not in existing_cols_projects:
                    try:
                        conn.execute(ddl)
                    except Exception as e:
                        logger.warning("Erreur migration colonne projects %s: %s", col, e)

            existing_cols_mcp_tools = {r[1] for r in conn.execute("PRAGMA table_info(mcp_tools);").fetchall()}
            for col, ddl in [
                ("project_id", "ALTER TABLE mcp_tools ADD COLUMN project_id TEXT DEFAULT NULL;"),
                ("mcp_primitive", "ALTER TABLE mcp_tools ADD COLUMN mcp_primitive TEXT NOT NULL DEFAULT 'tool';"),
                ("is_idempotent", "ALTER TABLE mcp_tools ADD COLUMN is_idempotent INTEGER NOT NULL DEFAULT 0;"),
                ("is_critical", "ALTER TABLE mcp_tools ADD COLUMN is_critical INTEGER NOT NULL DEFAULT 0;"),
            ]:
                if col not in existing_cols_mcp_tools:
                    try:
                        conn.execute(ddl)
                    except Exception:
                        pass

            existing_cols_mcp_servers = {r[1] for r in conn.execute("PRAGMA table_info(mcp_servers);").fetchall()}
            if "project_id" not in existing_cols_mcp_servers:
                try:
                    conn.execute("ALTER TABLE mcp_servers ADD COLUMN project_id TEXT DEFAULT NULL;")
                except Exception:
                    pass

            # Migration des colonnes hooks_index
            existing_cols_hooks = {r[1] for r in conn.execute("PRAGMA table_info(hooks_index);").fetchall()}
            for col, ddl in [
                ("description", "ALTER TABLE hooks_index ADD COLUMN description TEXT NOT NULL DEFAULT '';"),
                ("scope", "ALTER TABLE hooks_index ADD COLUMN scope TEXT NOT NULL DEFAULT 'global';"),
                ("project_id", "ALTER TABLE hooks_index ADD COLUMN project_id TEXT DEFAULT NULL;"),
            ]:
                if col not in existing_cols_hooks:
                    try:
                        conn.execute(ddl)
                    except Exception:
                        pass
            # Migration des colonnes commands_index
            existing_cols_commands = {r[1] for r in conn.execute("PRAGMA table_info(commands_index);").fetchall()}
            for col, ddl in [
                ("usage", "ALTER TABLE commands_index ADD COLUMN usage TEXT NOT NULL DEFAULT '';"),
                ("category", "ALTER TABLE commands_index ADD COLUMN category TEXT NOT NULL DEFAULT 'Système';"),
                ("scope", "ALTER TABLE commands_index ADD COLUMN scope TEXT NOT NULL DEFAULT 'global';"),
                ("project_id", "ALTER TABLE commands_index ADD COLUMN project_id TEXT DEFAULT NULL;"),
            ]:
                if col not in existing_cols_commands:
                    try:
                        conn.execute(ddl)
                    except Exception:
                        pass

            # Migration hooks_audit_log
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS hooks_audit_log (
                        id TEXT PRIMARY KEY,
                        hook_id TEXT NOT NULL,
                        hook_name TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        duration_ms REAL NOT NULL DEFAULT 0.0,
                        payload_summary TEXT NOT NULL DEFAULT '',
                        result_summary TEXT NOT NULL DEFAULT '',
                        error TEXT,
                        project_id TEXT,
                        created_at TEXT NOT NULL
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_hooks_audit_created ON hooks_audit_log(created_at DESC);")
            except Exception:
                pass

            # Migration FTS5 pour le Skill RAG
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
                        name,
                        description,
                        tags_json,
                        content='skills_index',
                        content_rowid='rowid'
                    );
                """)
                conn.execute("INSERT INTO skills_fts(skills_fts) VALUES('rebuild');")
            except Exception:
                pass


# Singleton de base de données globale
db = SqliteDatabase()
