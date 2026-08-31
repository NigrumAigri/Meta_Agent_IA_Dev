from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from core.config import settings
from core.domain import (
    ActionProposal,
    AgentDefinition,
    AgentLink,
    AgentType,
    BenchmarkRecord,
    CheckpointData,
    CommandDefinition,
    DocumentAttachment,
    FinOpsBadge,
    FinOpsMetric,
    HitlRequest,
    HitlRequestStatus,
    HookAuditLog,
    HookDefinition,
    HookEventType,
    LessonLearned,
    LinkType,
    McpServerConfig,
    McpToolDefinition,
    McpTransport,
    Message,
    MessageRole,
    Project,
    ProjectStatus,
    ProposalStatus,
    ProposalType,
    RuleDefinition,
    RuleScope,
    SkillDefinition,
    SkillScope,
    SystemCopilotMessage,
    Thread,
    extract_reasoning_metadata,
    utc_now,
)
from storage.sqlite_db import db

logger = logging.getLogger(__name__)



# ------------------------------------------------------------------------------
# 1. REPOSITORY DES PROJETS & THREADS
# ------------------------------------------------------------------------------

class ProjectRepository:
    def list_all(self, include_archived: bool = False) -> list[Project]:
        query = "SELECT * FROM projects WHERE 1=1"
        if not include_archived:
            query += " AND (is_archived IS NULL OR is_archived = 0)"
        query += " ORDER BY updated_at DESC;"
        rows = db.fetch_all(query)
        projects = []
        for r in rows:
            docs_raw = json.loads(r["documents_json"]) if ("documents_json" in r.keys() and r["documents_json"]) else []
            docs = [DocumentAttachment.model_validate(d) for d in docs_raw]
            gen_files = json.loads(r["generated_files_json"]) if ("generated_files_json" in r.keys() and r["generated_files_json"]) else []
            p = Project(
                id=UUID(r["id"]),
                name=r["name"],
                status=ProjectStatus(r["status"]),
                target_path=r["target_path"],
                selected_finops_profile=FinOpsBadge(r["selected_finops_profile"]),
                budget_limit_usd=r["budget_limit_usd"],
                active_thread_id=r["active_thread_id"],
                documents=docs,
                generated_files=gen_files,
                is_archived=bool(r["is_archived"]) if "is_archived" in r.keys() else False,
                deleted_at=datetime.fromisoformat(r["deleted_at"]) if ("deleted_at" in r.keys() and r["deleted_at"]) else None,
                created_at=datetime.fromisoformat(r["created_at"]),
                updated_at=datetime.fromisoformat(r["updated_at"]),
            )
            p.threads = self.get_threads(str(p.id))
            projects.append(p)
        return projects

    def auto_sync_disk_projects(self) -> None:
        """Découvre et synchronise automatiquement les projets existants sur disque dans SQLite."""
        try:
            from core.config import settings
            output_dir = settings.output_dir
            if not output_dir.exists():
                return
            
            existing = self.list_all(include_archived=True)
            existing_paths = {p.target_path for p in existing if p.target_path}
            existing_names = {p.name.lower() for p in existing}

            for p_dir in output_dir.iterdir():
                if p_dir.is_dir() and not p_dir.name.startswith("."):
                    clean_name = p_dir.name.replace("_", " ").replace("-", " ").title()
                    str_path = str(p_dir)
                    if str_path not in existing_paths and clean_name.lower() not in existing_names:
                        new_proj = Project(
                            name=clean_name,
                            target_path=str_path,
                            budget_limit_usd=10.0,
                            selected_finops_profile=FinOpsBadge.SWEET_SPOT,
                        )
                        new_proj.get_or_create_main_thread()
                        self.save(new_proj)
                        
                        # Instancier l'équipe dédiée
                        pid = str(new_proj.id)
                        slug = "".join(c if c.isalnum() else "_" for c in clean_name.lower())[:10]
                        agent_dev = AgentDefinition(
                            id=f"ag_dev_{slug}_{pid[:4]}",
                            name=f"Développeur · {clean_name}",
                            project_id=pid,
                            role_description=f"Ingénieur logiciel dédié pour {clean_name}",
                            role="Développeur Logiciel Dédié",
                            model="qwen/qwen-2.5-coder-32b-instruct",
                            temperature=0.2,
                            max_tokens=4096,
                            budget_limit_usd=6.0,
                            canvas_x=80.0,
                            canvas_y=140.0,
                            icon="code",
                            is_active=True,
                            is_core_meta_agent=False,
                        )
                        agent_repo.save(agent_dev)

                        agent_judge = AgentDefinition(
                            id=f"ag_judge_{slug}_{pid[:4]}",
                            name=f"Contrôleur Qualité · {clean_name}",
                            project_id=pid,
                            role_description=f"Auditeur qualité et juge déterministe pour {clean_name}",
                            role="Juge Qualité & Testeur",
                            model="moonshotai/kimi-k3",
                            temperature=0.1,
                            max_tokens=4096,
                            budget_limit_usd=4.0,
                            canvas_x=480.0,
                            canvas_y=140.0,
                            icon="shield",
                            is_active=True,
                            is_core_meta_agent=False,
                        )
                        agent_repo.save(agent_judge)

                        link = AgentLink(
                            source_agent_id=agent_dev.id,
                            target_agent_id=agent_judge.id,
                            project_id=pid,
                            link_type=LinkType.DEBATE,
                            label="Développeur ⇄ Contrôleur Qualité",
                            is_active=True,
                        )
                        agent_links_repo.create(link)
                        existing_paths.add(str_path)
                        existing_names.add(clean_name.lower())
        except Exception as e:
            logger.warning("Erreur lors de la synchronisation des projets disque : %s", e)

    def get(self, project_id: UUID | str) -> Project | None:
        p_id = str(project_id)
        row = db.fetch_one("SELECT * FROM projects WHERE id = ?;", (p_id,))
        if not row:
            return None
        docs_raw = json.loads(row["documents_json"]) if ("documents_json" in row.keys() and row["documents_json"]) else []
        docs = [DocumentAttachment.model_validate(d) for d in docs_raw]
        gen_files = json.loads(row["generated_files_json"]) if ("generated_files_json" in row.keys() and row["generated_files_json"]) else []
        p = Project(
            id=UUID(row["id"]),
            name=row["name"],
            status=ProjectStatus(row["status"]),
            target_path=row["target_path"],
            selected_finops_profile=FinOpsBadge(row["selected_finops_profile"]),
            budget_limit_usd=row["budget_limit_usd"],
            active_thread_id=row["active_thread_id"],
            documents=docs,
            generated_files=gen_files,
            is_archived=bool(row["is_archived"]) if "is_archived" in row.keys() else False,
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if ("deleted_at" in row.keys() and row["deleted_at"]) else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
        p.threads = self.get_threads(p_id, load_messages=True)
        return p

    def archive(self, project_id: UUID | str) -> bool:
        p_id = str(project_id)
        now_str = utc_now().isoformat()
        res = db.execute(
            "UPDATE projects SET is_archived = 1, deleted_at = ?, updated_at = ? WHERE id = ?;",
            (now_str, now_str, p_id),
        )
        return res.rowcount > 0

    def restore(self, project_id: UUID | str) -> bool:
        p_id = str(project_id)
        now_str = utc_now().isoformat()
        res = db.execute(
            "UPDATE projects SET is_archived = 0, deleted_at = NULL, updated_at = ? WHERE id = ?;",
            (now_str, p_id),
        )
        return res.rowcount > 0

    def save(self, project: Project) -> Project:
        p_id = str(project.id)
        now_str = utc_now().isoformat()
        deleted_at_str = project.deleted_at.isoformat() if project.deleted_at else None
        docs_json = json.dumps([d.model_dump(mode="json") for d in project.documents])
        gen_files_json = json.dumps(project.generated_files)
        with db.transaction():
            db.execute(
                """
                INSERT INTO projects (id, name, status, target_path, selected_finops_profile, budget_limit_usd, active_thread_id, documents_json, generated_files_json, is_archived, deleted_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    status = excluded.status,
                    target_path = excluded.target_path,
                    selected_finops_profile = excluded.selected_finops_profile,
                    budget_limit_usd = excluded.budget_limit_usd,
                    active_thread_id = excluded.active_thread_id,
                    documents_json = excluded.documents_json,
                    generated_files_json = excluded.generated_files_json,
                    is_archived = excluded.is_archived,
                    deleted_at = excluded.deleted_at,
                    updated_at = excluded.updated_at;
                """,
                (
                    p_id,
                    project.name,
                    project.status.value,
                    project.target_path,
                    project.selected_finops_profile.value,
                    project.budget_limit_usd,
                    project.active_thread_id,
                    docs_json,
                    gen_files_json,
                    1 if project.is_archived else 0,
                    deleted_at_str,
                    project.created_at.isoformat(),
                    now_str,
                ),
            )
            # Sauvegarder les threads associés
            for thread in project.threads:
                self.save_thread(thread)

        return self.get(project.id) or project

    def delete(self, project_id: UUID | str) -> bool:
        p_id = str(project_id)
        with db.transaction():
            db.execute("DELETE FROM project_messages WHERE project_id = ?;", (p_id,))
            db.execute("DELETE FROM threads WHERE project_id = ?;", (p_id,))
            db.execute("DELETE FROM agents WHERE project_id = ?;", (p_id,))
            db.execute("DELETE FROM hitl_requests WHERE project_id = ?;", (p_id,))
            db.execute("DELETE FROM proposals WHERE project_id = ?;", (p_id,))
            res = db.execute("DELETE FROM projects WHERE id = ?;", (p_id,))
            return res.rowcount > 0

    def get_threads(self, project_id: str, load_messages: bool = False) -> list[Thread]:
        rows = db.fetch_all(
            "SELECT * FROM threads WHERE project_id = ? ORDER BY is_pinned DESC, updated_at DESC;",
            (project_id,),
        )
        threads = []
        for r in rows:
            t = Thread(
                id=r["id"],
                project_id=r["project_id"],
                title=r["title"],
                is_pinned=bool(r["is_pinned"]) if "is_pinned" in r.keys() else False,
                is_archived=bool(r["is_archived"]) if "is_archived" in r.keys() else False,
                is_unread=bool(r["is_unread"]) if "is_unread" in r.keys() else False,
                created_at=datetime.fromisoformat(r["created_at"]),
                updated_at=datetime.fromisoformat(r["updated_at"]),
            )
            if load_messages:
                t.messages = self.get_thread_messages(t.id)
            else:
                t.messages = []
            threads.append(t)
        return threads

    def save_thread(self, thread: Thread) -> Thread:
        now_str = utc_now().isoformat()
        db.execute(
            """
            INSERT INTO threads (id, project_id, title, is_pinned, is_archived, is_unread, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                is_pinned = excluded.is_pinned,
                is_archived = excluded.is_archived,
                is_unread = excluded.is_unread,
                updated_at = excluded.updated_at;
            """,
            (
                thread.id,
                thread.project_id,
                thread.title,
                1 if thread.is_pinned else 0,
                1 if thread.is_archived else 0,
                1 if thread.is_unread else 0,
                thread.created_at.isoformat(),
                now_str,
            ),
        )
        for msg in thread.messages:
            self.add_project_message(msg)
        return thread

    def update_thread(
        self,
        thread_id: str,
        title: str | None = None,
        is_pinned: bool | None = None,
        is_archived: bool | None = None,
        is_unread: bool | None = None,
    ) -> Thread | None:
        row = db.fetch_one("SELECT * FROM threads WHERE id = ?;", (thread_id,))
        if not row:
            return None
        now_str = utc_now().isoformat()
        new_title = title if title is not None else row["title"]
        new_pinned = (1 if is_pinned else 0) if is_pinned is not None else (row["is_pinned"] if "is_pinned" in row.keys() else 0)
        new_archived = (1 if is_archived else 0) if is_archived is not None else (row["is_archived"] if "is_archived" in row.keys() else 0)
        new_unread = (1 if is_unread else 0) if is_unread is not None else (row["is_unread"] if "is_unread" in row.keys() else 0)

        db.execute(
            """
            UPDATE threads
            SET title = ?, is_pinned = ?, is_archived = ?, is_unread = ?, updated_at = ?
            WHERE id = ?;
            """,
            (new_title, new_pinned, new_archived, new_unread, now_str, thread_id),
        )
        return Thread(
            id=row["id"],
            project_id=row["project_id"],
            title=new_title,
            is_pinned=bool(new_pinned),
            is_archived=bool(new_archived),
            is_unread=bool(new_unread),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(now_str),
        )

    def delete_thread(self, thread_id: str) -> bool:
        row = db.fetch_one("SELECT * FROM threads WHERE id = ?;", (thread_id,))
        if not row:
            return False
        db.execute("DELETE FROM project_messages WHERE thread_id = ?;", (thread_id,))
        db.execute("DELETE FROM threads WHERE id = ?;", (thread_id,))
        return True

    def get_thread_messages(self, thread_id: str) -> list[Message]:
        rows = db.fetch_all("SELECT * FROM project_messages WHERE thread_id = ? ORDER BY created_at ASC;", (thread_id,))
        messages = []
        for r in rows:
            attachments_raw = json.loads(r["attachments_json"])
            attachments = [DocumentAttachment.model_validate(a) for a in attachments_raw]
            messages.append(
                Message(
                    id=r["id"],
                    role=MessageRole(r["role"]),
                    content=r["content"],
                    author_name=r["author_name"],
                    agent_id=r["agent_id"],
                    thread_id=r["thread_id"],
                    project_id=r["project_id"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    attachments=attachments,
                )
            )
        return messages

    def add_project_message(self, message: Message) -> Message:
        attachments_json = json.dumps([a.model_dump(mode="json") for a in message.attachments])
        db.execute(
            """
            INSERT INTO project_messages (id, thread_id, project_id, role, content, author_name, agent_id, attachments_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                attachments_json = excluded.attachments_json;
            """,
            (
                message.id,
                message.thread_id or "",
                message.project_id or "",
                message.role.value,
                message.content,
                message.author_name,
                message.agent_id,
                attachments_json,
                message.created_at.isoformat(),
            ),
        )
        return message

    def add_system_copilot_message(self, message: SystemCopilotMessage) -> SystemCopilotMessage:
        attachments_json = json.dumps([a.model_dump(mode="json") for a in message.attachments])
        db.execute(
            """
            INSERT INTO system_copilot_messages (id, role, content, author_name, attachments_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                message.id,
                message.role.value,
                message.content,
                message.author_name,
                attachments_json,
                message.created_at.isoformat(),
            ),
        )
        return message

    def list_system_copilot_messages(self, limit: int = 100) -> list[SystemCopilotMessage]:
        rows = db.fetch_all(
            "SELECT * FROM system_copilot_messages ORDER BY created_at ASC LIMIT ?;", (limit,)
        )
        messages = []
        for r in rows:
            attachments_raw = json.loads(r["attachments_json"])
            attachments = [DocumentAttachment.model_validate(a) for a in attachments_raw]
            messages.append(
                SystemCopilotMessage(
                    id=r["id"],
                    role=MessageRole(r["role"]),
                    content=r["content"],
                    author_name=r["author_name"],
                    attachments=attachments,
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
            )
        return messages

    def clear_system_copilot_messages(self) -> None:
        db.execute("DELETE FROM system_copilot_messages;")


# ------------------------------------------------------------------------------
# 2. REPOSITORY DES 5 META-AGENTS & TOPOLOGIE CANVAS
# ------------------------------------------------------------------------------

class AgentRepository:
    def __init__(self) -> None:
        self._seed_default_meta_agents()

    def _seed_default_meta_agents(self) -> None:
        """Initialise dynamiquement les 5 Meta-Agents officiels depuis data/agents/ ou les définitions de domaine."""
        agents_dir = settings.data_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        # 1. Découverte dynamique des agents depuis les fichiers JSON s'ils existent
        loaded_agents: list[AgentDefinition] = []
        if agents_dir.exists():
            for json_file in sorted(agents_dir.glob("agent_*.json")):
                try:
                    raw_data = json.loads(json_file.read_text(encoding="utf-8"))
                    agent_def = AgentDefinition.model_validate(raw_data)
                    loaded_agents.append(agent_def)
                except Exception as err:
                    logger.warning("Erreur lors de la lecture du fichier agent %s : %s", json_file.name, err)

        # 2. Si aucun fichier n'a été trouvé, initialisation des 5 agents de base
        if not loaded_agents:
            loaded_agents = [
                AgentDefinition(
                    id="agent_architect",
                    name="Agent 1 : Architecte & Cadrage (Lead Tech & CTO)",
                    role_description="Directeur Technique & Stratège en Architecture Logicielle Distribuée, Clean Architecture et Modélisation LEGO Multi-Agents.",
                    role="Chief Technology Officer (CTO) & Lead Architecte Système",
                    goal="Mener un cadrage adaptatif sans questionnaire rigide, concevoir des architectures LEGO modulaires selon la Clean Architecture (zéro I/O dans le domaine), spécifier les schémas Pydantic v2 et ordonnancer les tâches atomiques pour le Développeur.",
                    backstory="Directeur Technique d'élite avec 15 ans d'expérience. Adepte intransigeant de la responsabilité unique (SRP), de l'idempotence et du refus absolu de la dette technique. Vous ne codez jamais les fichiers d'implémentation vous-même : vous concevez, challengez les choix fragiles et déléguez au Développeur.",
                    agent_type=AgentType.ARCHITECT,
                    parent_id=None,
                    model=settings.llm_discovery_model,
                    temperature=0.1,
                    max_tokens=4096,
                    timeout_seconds=90.0,
                    reasoning_effort="high",
                    max_iter=10,
                    budget_limit_usd=5.0,
                    system_prompt="Tu es le Chief Technology Officer (CTO) et Lead Architecte Système du projet.\n\n### 1. POSTURE & MISSION STRATÉGIQUE :\nTu diriges le cadrage fonctionnel, l'architecture logicielle et l'ordonnancement technique. Ton objectif est de transformer les besoins bruts en une architecture logicielle robuste, modulaire et extensible, sans dette technique. Tu garantis la conformité stricte aux patrons de conception éprouvés (Clean Architecture, Domain-Driven Design, Hexagonal Architecture).\n\n### 2. PROTOCOLE D'INGÉNIERIE EN 4 PHASES :\n- PHASE 1 - CADRAGE ADAPTATIF INCEPTION :\n  * Analyse en profondeur les consignes, documents et pièces jointes fournis (cahier des charges, feuilles Excel, schémas, spécifications).\n  * Pose entre 1 et 3 questions ciblées et percutantes si et seulement si des zones d'ombre critiques subsistent.\n  * Évite impérativement les questionnaires génériques rigides de 20 questions. Sois proactif et propose des choix par défaut pertinents.\n\n- PHASE 2 - MODÉLISATION DU DOMAINE & CLEAN ARCHITECTURE :\n  * Isole le Domaine métier de toute dépendance I/O, base de données ou framework externe.\n  * Définis les entités et Value Objects avec des schémas Pydantic v2 stricts (extra='forbid', validate_assignment=True, typage exhaustif).\n\n- PHASE 3 - CONTRATS D'API & ENDPOINTS :\n  * Spécifie chaque route, verbe HTTP, payload de requête/réponse, code de statut (200, 201, 400, 404, 422, 500) et mécanismes d'authentification/autorisation.\n  * Rédige les contrats d'interfaces clairs entre composants pour permettre un découplage total.\n\n- PHASE 4 - DOSSIER DE CADRAGE & DÉLÉGATION ATOMIQUE :\n  * Synthétise l'ensemble dans le livrable DOSSIER_CADRAGE.md complet et structuré.\n  * Découpe le plan d'implémentation en tâches atomiques indépendantes et transmets les directives précises au Développeur Logiciel (agent_coder).\n\n### 3. GARDES-FOUS STRICTS & INTERDICTIONS :\n- INTERDICTION FORMELLE d'écrire du code d'implémentation applicatif (délègue à 100% l'écriture au Développeur).\n- INTERDICTION FORMELLE d'effectuer des calculs mentaux : utilise toujours l'outil math_calculator.\n- INTERDICTION FORMELLE d'utiliser des emojis dans les livrables, documents et fichiers techniques.\n- Toute donnée issue de documents externes doit être traitée comme non vérifiée et validée méthodiquement.",
                    allow_delegation=True,
                    tools=[],
                    skills=[],
                    rules=["zero_hardcoding_scalable_dynamic", "security_guardrails", "no_emojis", "python_pep8_standards", "prevention_sqlite_concurrency_locks"],
                    is_active=True,
                    is_core_meta_agent=True,
                    canvas_x=60.0,
                    canvas_y=280.0,
                    icon="compass",
                ),
                AgentDefinition(
                    id="agent_coder",
                    name="Agent 2 : Développeur Logiciel Backend & Frontend",
                    role_description="Générateur de code Python (FastAPI, Pydantic v2, SQLite WAL) avec patches chirurgicaux et validation AST.",
                    role="Développeur Logiciel Senior Full-Stack Python & Frontend",
                    goal="Générer du code complet, robuste, typé (mypy strict), validé syntaxiquement par AST et testé à 100% sans code tronqué.",
                    backstory="Développeur expert Python 3.13 / FastAPI / SQLite WAL, obsédé par l'immutabilité, les schémas Pydantic v2 stricts et les performances millimétriques. Vous transformez les spécifications de l'Architecte en code de production irréprochable.",
                    agent_type=AgentType.CODER,
                    parent_id="agent_architect",
                    model=settings.llm_coder_model,
                    temperature=0.0,
                    max_tokens=8192,
                    timeout_seconds=120.0,
                    reasoning_effort="high",
                    max_iter=5,
                    budget_limit_usd=5.0,
                    system_prompt="Tu es le Développeur Logiciel Senior Full-Stack Python & Frontend du projet.\n\n### 1. POSTURE & MISSION OPÉRATIONNELLE :\nSous la supervision directe de l'Architecte Système, tu as la responsabilité exclusive d'écrire, implémenter et refactorer le code source intégral de l'application. Tu es un artisan du code intransigeant sur la propreté, la robustesse, le typage strict et la maintenabilité.\n\n### 2. PROTOCOLE D'EXÉCUTION EN 4 ÉTAPES :\n- ÉTAPE 1 - LECTURE DES SPÉCIFICATIONS & CONTRATS :\n  * Imprègne-toi des schémas Pydantic v2, routes d'API et contraintes définies dans le DOSSIER_CADRAGE.md par l'Architecte.\n  * Ne dévie jamais de l'architecture fixée sans justification technique majeure.\n\n- ÉTAPE 2 - GÉNÉRATION DE CODE INTÉGRAL SANS TRONCATURE :\n  * Produis TOUJOURS le code source complet de chaque fichier.\n  * INTERDICTION ABSOLUE d'utiliser des raccourcis tels que `# TODO`, `// reste du code identique`, `pass` d'attente ou code tronqué.\n  * Applique un typage Python strict (`from __future__ import annotations`, type hints exhaustifs, Pydantic v2 `ConfigDict(extra=\"forbid\")`).\n  * Gère les exceptions de façon explicite et granulaire (zéro clause `except:` nue).\n\n- ÉTAPE 3 - VALIDATION SYNTAXIQUE AST OBLIGATOIRE :\n  * Valide immédiatement chaque module Python généré en mémoire via l'outil `ast_validator` pour garantir 0% d'erreur de syntaxe.\n  * Si une erreur est détectée, corrige-la immédiatement avant toute tentative d'écriture sur disque.\n\n- ÉTAPE 4 - PERSISTANCE ATOMIQUE & FORMATAGE PEP8 :\n  * Utilise exclusivement l'outil `file_writer_atomic` pour écrire les fichiers sur disque sans risque de corruption.\n  * Applique l'outil `code_formatter` pour garantir la conformité aux standards stricts PEP8.\n\n### 3. GARDES-FOUS STRICTS & RÈGLES D'OR :\n- Tu n'as pas l'autorisation de déléguer (`allow_delegation = False`) : tu exécutes le code jusqu'à son terme.\n- Pour la persistance SQLite, configure systématiquement le mode WAL et des transactions atomiques sécurisées.\n- Zéro emoji dans le code source, les commentaires, les docstrings et les logs.\n- En cas de calcul mathématique ou dimensionnement, délègue systématiquement à l'outil math_calculator.",
                    allow_delegation=False,
                    tools=[],
                    skills=[],
                    rules=["zero_hardcoding_scalable_dynamic", "python_pep8_standards", "security_guardrails", "no_emojis"],
                    is_active=True,
                    is_core_meta_agent=True,
                    canvas_x=540.0,
                    canvas_y=120.0,
                    icon="code",
                ),
                AgentDefinition(
                    id="agent_quality_judge",
                    name="Agent 3 : Contrôleur Qualité Déterministe",
                    role_description="Auditeur qualité et sécurité logicielle, évaluant le Score Qualité sur 100 points, formulant les leçons apprises et concevant les outils Tool-Maker.",
                    role="Auditeur Qualité Logicielle & Juge Déterministe",
                    goal="Auditer rigoureusement chaque fichier généré, calculer le Score Qualité sur 100 points sans hallucination et forger des outils Tool-Maker en cas d'échec répété.",
                    backstory="Juge impitoyable et déterministe, garantissant zéro faille de sécurité (injection SQL, chemin non assaini) et 100% de conformité aux tests unitaires.",
                    agent_type=AgentType.QUALITY_JUDGE,
                    parent_id="agent_coder",
                    model=settings.llm_discovery_model,
                    temperature=0.0,
                    max_tokens=4096,
                    timeout_seconds=45.0,
                    reasoning_effort="medium",
                    max_iter=5,
                    budget_limit_usd=3.0,
                    system_prompt="Tu es l'Auditeur Qualité Logicielle, Contrôleur Qualité et Juge Déterministe du projet.\n\n### 1. POSTURE & MISSION D'ÉVALUATION :\nTu es l'autorité indépendante chargée d'auditer, tester et certifier chaque ligne de code produite par le Développeur. Tu appliques une rigueur scientifique sans compromis et tu évalues le projet selon une grille multicritère déterministe sur 100 points, exempte de toute hallucination.\n\n### 2. PROTOCOLE D'AUDIT & MATRICE QUALITÉ DÉTERMINISTE /100 :\nTu évalues le projet sur 4 axes objectifs :\n1. SANTÉ TECHNIQUE & SYNTAXE (/35 points) :\n   * Validation syntaxique AST réussie sur 100% des fichiers Python (15 pts).\n   * Exécution et passage avec succès des tests unitaires/intégration dans `test_runner_sandbox` (20 pts).\n2. ROBUSTESSE & SÉCURITÉ APPLICATIVE (/25 points) :\n   * Typage strict Pydantic v2 avec `extra='forbid'` et absence de mutations incontrôlées (15 pts).\n   * Absence de failles critiques : injection SQL (utilisation systématique de requêtes paramétrées), Path Traversal et gestion granulaire des exceptions (10 pts).\n3. COUVERTURE FONCTIONNELLE & CONTRATS (/30 points) :\n   * Respect exact des spécifications du cahier des charges et des routes d'API définies lors du cadrage (30 pts).\n4. DOCUMENTATION & LISIBILITÉ (/10 points) :\n   * Présence de docstrings explicites, typage complet et clarté architecturale des modules (10 pts).\n\n### 3. BOUCLE DE RÉFLEXION & GESTION DES LEÇONS (ACTOR-CRITIC) :\n- VERDICT `SUCCÈS` (Score >= 85) : Le code est certifié pour la production.\n- VERDICT `AMÉLIORATION` (Score 70 à 84) : Tu formules une critique constructive détaillée et directement actionnable pour que le Développeur corrige les écarts (boucle limitée à 3 itérations maximum).\n- VERDICT `REJET` (Score < 70) : Blocage immédiat avec consignation du problème et de la règle préventive dans la table `lessons_learned`.\n- TOOL-MAKER : Si un type d'erreur se répète sur 2 itérations consécutives, propose la création d'un outil de validation dédié.\n\n### 4. GARDES-FOUS STRICTS :\n- Tous les calculs de score doivent être effectués via `math_calculator` : aucun score inventé ou subjectif.\n- Tu n'as pas l'autorisation de déléguer (`allow_delegation = False`).\n- Zéro emoji dans les rapports d'audit, matrices et journaux.",
                    allow_delegation=False,
                    tools=[],
                    skills=[],
                    rules=["zero_hardcoding_scalable_dynamic", "security_guardrails", "no_emojis"],
                    is_active=True,
                    is_core_meta_agent=True,
                    canvas_x=1020.0,
                    canvas_y=120.0,
                    icon="shield",
                ),
                AgentDefinition(
                    id="agent_finops_guardian",
                    name="Agent 4 : Gardien FinOps & Télémétrie",
                    role_description="Auditeur des coûts LLM en direct, disjoncteur budgétaire Circuit Breaker et sélectionneur des meilleurs modèles selon les 19 benchmarks d'Artificial Analysis.",
                    role="Auditeur FinOps & Gardien des Budgets LLM",
                    goal="Auditer les coûts en temps réel au 4e chiffre après la virgule ($ 0.0000), disjoncter le Circuit Breaker avant dépassement et optimiser le cache de tokens.",
                    backstory="Contrôleur de gestion IA spécialisé dans l'économie des tokens, la compression RAG et l'arbitrage scientifiquement prouvé des modèles par benchmark.",
                    agent_type=AgentType.FINOPS_GUARDIAN,
                    parent_id="agent_architect",
                    model=settings.llm_discovery_model,
                    temperature=0.0,
                    max_tokens=4096,
                    timeout_seconds=30.0,
                    reasoning_effort="medium",
                    max_iter=3,
                    budget_limit_usd=2.0,
                    system_prompt="Tu es l'Auditeur FinOps, Gestionnaire des Coûts LLM et Gardien de la Télémétrie du projet.\n\n### 1. POSTURE & MISSION DE GOUVERNANCE FINANCIÈRE :\nTu as pour mission de surveiller, auditer et optimiser chaque centime consommé lors des inférences LLM, tout en garantissant le meilleur rapport performance/coût grâce aux benchmarks scientifiques indépendants. Tu es le garant de la viabilité économique et de l'intégrité budgétaire.\n\n### 2. PROTOCOLE OPÉRATIONNEL FINOPS EN 3 PILIERS :\n- PILIER 1 - AUDIT TÉLÉMÉTRIQUE AU CENTIME PRÈS :\n  * Calcule la consommation exacte de tokens (Prompt Tokens, Completion Tokens, Reasoning Tokens, Cache Read) et les coûts réels au 4e chiffre après la virgule ($ 0.0000) via `finops_calculator` et `math_calculator`.\n  * Enregistre chaque métrique dans le grand livre `finops_ledger`.\n\n- PILIER 2 - SÉLECTION SCIENTIFIQUE DES MODÈLES (19 BENCHMARKS ARTIFICIAL ANALYSIS) :\n  * Analyse en direct les métriques certifiées (Terminal-Bench v2.1, GPQA Diamond, SciCode, SWE-bench, TTFT, Vitesse tok/s, Prix $/1M tokens).\n  * Classe et recommande les modèles selon les 3 profils stratégiques :\n    - PROFIL SWEET SPOT : Équilibre optimal entre haute intelligence (Coding >= 75) et coût maîtrisé.\n    - PROFIL TOP PERFORMANCE : Modèles d'élite de raisonnement pour l'architecture et les arbitrages complexes.\n    - PROFIL ULTRA ECO : Modèles ultra-rapides et légers pour les tâches d'extraction et de classification.\n\n- PILIER 3 - DISJONCTEUR BUDGÉTAIRE (CIRCUIT BREAKER) :\n  * Surveille en permanence le plafond budgétaire alloué au projet (`budget_limit_usd`).\n  * Déclenche une alerte de sécurité et stoppe préventivement l'exécution dès que le seuil critique de 90% du budget est atteint.\n\n### 3. GARDES-FOUS STRICTS :\n- INTERDICTION ABSOLUE de tout calcul mental : utilise systématiquement `finops_calculator` et `math_calculator`.\n- Zéro emoji dans les rapports financiers, métriques et ventilations de coûts.",
                    allow_delegation=False,
                    tools=[],
                    skills=[],
                    rules=["zero_hardcoding_scalable_dynamic", "finops_limits", "no_emojis"],
                    is_active=True,
                    is_core_meta_agent=True,
                    canvas_x=1500.0,
                    canvas_y=120.0,
                    icon="bar-chart",
                ),
                AgentDefinition(
                    id="agent_copilot",
                    name="Agent 5 : Méta-Agent Copilote Système",
                    role_description="Assistant conversationnel permanent capable de reconfigurer les agents, ajuster les prompts, connecter des serveurs MCP et auto-déboguer la plateforme.",
                    role="Superviseur Plateforme & Copilote Méta-Système",
                    goal="Accompagner l'opérateur humain, reconfigurer les agents à la volée, connecter les serveurs MCP et maintenir la santé de la plateforme.",
                    backstory="Copilote omniscient connecté aux 21 tables SQLite WAL, capable d'ajuster les hyperparamètres et d'orchestrer les 7 piliers agentiques en temps réel.",
                    agent_type=AgentType.COPILOT,
                    parent_id=None,
                    model=settings.llm_discovery_model,
                    temperature=0.1,
                    max_tokens=4096,
                    timeout_seconds=45.0,
                    reasoning_effort="medium",
                    max_iter=5,
                    budget_limit_usd=5.0,
                    system_prompt="Tu es le Méta-Agent Copilote Système et Superviseur Transversal de la plateforme Meta Developer Agent.\n\n### 1. POSTURE & MISSION D'ASSISTANCE TRANSVERSALE :\nTu es l'assistant conversationnel permanent de l'opérateur humain et le superviseur global de l'architecture. Connecté aux 21 tables SQLite WAL de la plateforme et aux 7 piliers agentiques, tu diagnostiques l'état du système, aides à piloter les projets et permets la reconfiguration à chaud de l'équipe d'agents.\n\n### 2. PROTOCOLE DE SUPERVISION & CAPACITÉS SYSTÈME :\n- ASSISTANCE & CADRAGE CONVERSATIONNEL :\n  * Réponds de manière claire, concise et pédagogique à l'opérateur humain.\n  * Explique les choix architecturaux, les métriques FinOps et les recommandations des autres agents.\n\n- DISPATCH DES COMMANDES SLASH (0 TOKEN ENGINE) :\n  * Détecte et traite les commandes natives de l'opérateur :\n    - `/cadrage` : Initie la phase de recueil du besoin avec l'Architecte.\n    - `/audit` : Déclenche un audit qualité complet par le Juge Qualité.\n    - `/finops` : Fournit la synthèse financière et télémétrique.\n    - `/test` : Lance la suite de tests unitaires et d'intégration.\n    - `/export` : Génère l'archive ZIP du projet prêt pour déploiement.\n\n- SUPERVISION DES 7 PILIERS & RECONFIGURATION DYNAMIQUE :\n  * Inspecte la santé des serveurs MCP, des compétences JIT (Skills), des règles (Rules) et des hooks.\n  * Modifie si nécessaire les hyperparamètres des agents via `system_config_manager` et améliore les consignes via `prompt_enhancer_compiler`.\n\n### 3. GARDES-FOUS STRICTS :\n- Respecte l'étanchéité absolue entre les messages du Copilote et les discussions isolées des projets.\n- Pour toute modification structurelle critique (suppression de données, dépassement de quota), soumets une demande d'approbation dans la file HITL (`hitl_requests`).\n- Zéro emoji dans les réponses techniques, logs et fichiers système.",
                    allow_delegation=True,
                    tools=[],
                    skills=[],
                    rules=["zero_hardcoding_scalable_dynamic", "security_guardrails", "no_emojis"],
                    is_active=True,
                    is_core_meta_agent=True,
                    canvas_x=1980.0,
                    canvas_y=120.0,
                    icon="zap",
                ),
                AgentDefinition(
                    id="agent_model_matcher",
                    name="Agent 6 : Stratège LLM & Benchmarks IA",
                    role_description="Évaluateur scientifique des modèles IA, comparateur des 19 benchmarks d'Artificial Analysis et sélecteur des profils Sweet Spot, Top Performance et Ultra Éco.",
                    role="Stratège d'Allocation LLM & Évaluateur de Benchmarks",
                    goal="Analyser en direct les 19 benchmarks certifiés, calculer les scores composites sur 100 et sélectionner dynamiquement le meilleur modèle et son niveau de réflexion.",
                    backstory="Expert indépendant en benchmark d'IA générative et en architecture de modèles (Dense vs MoE, Reasoning vs Instruct). Vous garantissez l'adéquation cognitive parfaite entre le modèle et la mission de l'agent sans biais commercial.",
                    agent_type=AgentType.MODEL_MATCHER,
                    parent_id="agent_architect",
                    model=settings.llm_discovery_model,
                    temperature=0.0,
                    max_tokens=4096,
                    timeout_seconds=30.0,
                    reasoning_effort="medium",
                    max_iter=3,
                    budget_limit_usd=2.0,
                    system_prompt="Tu es le Stratège d'Allocation des Modèles LLM et l'Évaluateur Scientifique des Benchmarks du projet.\n\n### 1. POSTURE & MISSION COGNITIVE :\nTu as pour responsabilité exclusive d'analyser, comparer et recommander les meilleurs modèles d'IA pour chaque agent conçu par l'Architecte. Tu t'appuies rigoureusement sur les données réelles de la table SQLite `aa_benchmarks_cache` et les 19 benchmarks certifiés d'Artificial Analysis.\n\n### 2. PROTOCOLE D'ÉVALUATION SCIENTIFIQUE DYNAMIQUE :\n- ÉTAPE 1 - EXTRACTION DES COMPÉTENCES CLÉS DU RÔLE :\n  * Analyse le rôle métier et la tâche de l'agent (Code, Rédaction, Finance, Outils/MCP, Scraping).\n  * Identifie dynamiquement les métriques pertinentes (ex: `Terminal-Bench` pour le code, `MMLU-Pro` pour la rédaction, `MATH` pour la finance, `BFCL/Tau2` pour les outils).\n\n- ÉTAPE 2 - SÉLECTION DU TRIO STRATÉGIQUE EN BDD :\n  * Interroge l'outil `search_models_catalog` pour lire les scores réels et tarifs en base de données.\n  * Identifie les 3 profils distincts :\n    - 🟢 PROFIL SWEET SPOT : Meilleur ratio d'efficience (Score² / Prix Output) avec un score qualité >= 75/100.\n    - 🟣 PROFIL TOP PERFORMANCE : Modèle détenant la note maximale de compétence pure, sans restriction budgétaire.\n    - 🟡 PROFIL ULTRA ÉCO : Modèle le plus rapide et le moins cher avec un score de viabilité >= 50/100.\n\n- ÉTAPE 3 - CONFIGURATION DU NIVEAU DE RÉFLEXION :\n  * Détermine le niveau de réflexion requis (`reasoning_effort`: 'high', 'medium', 'low', 'none') en fonction de la complexité algorithmique de la tâche.\n\n### 3. GARDES-FOUS STRICTS :\n- INTERDICTION FORMELLE de recommander un modèle de mémoire ou sans vérifier ses scores réels en BDD.\n- Si un modèle n'a pas encore de benchmark en base, utilise l'outil `web_search_and_docs` pour vérifier les métriques officielles.\n- Zéro emoji dans les rapports d'évaluation et comparatifs.",
                    allow_delegation=False,
                    tools=[],
                    skills=[],
                    rules=["zero_hardcoding_scalable_dynamic", "security_guardrails", "no_emojis"],
                    is_active=True,
                    is_core_meta_agent=True,
                    canvas_x=2400.0,
                    canvas_y=120.0,
                    icon="cpu",
                ),
            ]

        # 3. Sauvegarde et synchronisation dans SQLite et sur disque
        for ag in loaded_agents:
            self.save(ag)
            # Garantir la persistance du fichier JSON sur disque pour chaque agent
            agent_file = agents_dir / f"{ag.id}.json"
            try:
                agent_file.write_text(ag.model_dump_json(indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning("Impossible d'écrire le fichier agent %s : %s", agent_file.name, e)

    def _row_to_agent(self, r: dict[str, Any]) -> AgentDefinition:
        return AgentDefinition(
            id=r["id"],
            name=r["name"],
            project_id=r.get("project_id"),
            role_description=r.get("role_description", "") or "",
            role=r.get("role", "") or "",
            goal=r.get("goal", "") or "",
            backstory=r.get("backstory", "") or "",
            agent_type=AgentType(r["agent_type"]),
            parent_id=r["parent_id"],
            model=r["model"],
            temperature=r["temperature"],
            max_tokens=r["max_tokens"],
            timeout_seconds=r.get("timeout_seconds", 60.0),
            reasoning_effort=r.get("reasoning_effort", "medium"),
            max_iter=r.get("max_iter", 5),
            budget_limit_usd=r.get("budget_limit_usd", 5.0),
            system_prompt=r.get("system_prompt", "") or "",
            allow_delegation=bool(r["allow_delegation"]),
            tools=json.loads(r["tools_json"]),
            skills=json.loads(r["skills_json"]),
            rules=json.loads(r["rules_json"]),
            is_active=bool(r["is_active"]),
            is_core_meta_agent=bool(r["is_core_meta_agent"]),
            canvas_x=r["canvas_x"],
            canvas_y=r["canvas_y"],
            icon=r["icon"],
            created_at=datetime.fromisoformat(r["created_at"]),
            updated_at=datetime.fromisoformat(r["updated_at"]),
        )

    def list_all(
        self,
        project_id: str | None = None,
        is_core_only: bool = False,
        include_core: bool = False,
    ) -> list[AgentDefinition]:
        if is_core_only:
            rows = db.fetch_all(
                "SELECT * FROM agents WHERE is_core_meta_agent = 1 AND project_id IS NULL ORDER BY created_at ASC;"
            )
        elif project_id is not None:
            pid_str = str(project_id)
            if include_core:
                rows = db.fetch_all(
                    "SELECT * FROM agents WHERE project_id = ? OR (is_core_meta_agent = 1 AND project_id IS NULL) ORDER BY created_at ASC;",
                    (pid_str,),
                )
            else:
                rows = db.fetch_all(
                    "SELECT * FROM agents WHERE project_id = ? ORDER BY created_at ASC;",
                    (pid_str,),
                )
        else:
            rows = db.fetch_all("SELECT * FROM agents ORDER BY created_at ASC;")
        return [self._row_to_agent(r) for r in rows]

    def get_core_meta_agents(self) -> list[AgentDefinition]:
        """Retourne les 5 Méta-Agents Core permanents du Studio."""
        return self.list_all(is_core_only=True)

    def get(self, agent_id: str) -> AgentDefinition | None:
        row = db.fetch_one("SELECT * FROM agents WHERE id = ?;", (agent_id,))
        if not row:
            return None
        return self._row_to_agent(row)

    def get_by_id(self, agent_id: str) -> AgentDefinition | None:
        """Alias pour get(agent_id)."""
        return self.get(agent_id)

    def list_agents(self, project_id: str | None = None) -> list[AgentDefinition]:
        """Alias pour list_all(project_id=project_id)."""
        return self.list_all(project_id=project_id)

    def save(self, agent: AgentDefinition) -> AgentDefinition:
        now_str = utc_now().isoformat()
        db.execute(
            """
            INSERT INTO agents (
                id, name, project_id, role_description, role, goal, backstory, agent_type, parent_id, model,
                temperature, max_tokens, timeout_seconds, reasoning_effort, max_iter, budget_limit_usd,
                system_prompt, allow_delegation, tools_json, skills_json, rules_json, is_active,
                is_core_meta_agent, canvas_x, canvas_y, icon, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                project_id = excluded.project_id,
                role_description = excluded.role_description,
                role = excluded.role,
                goal = excluded.goal,
                backstory = excluded.backstory,
                agent_type = excluded.agent_type,
                parent_id = excluded.parent_id,
                model = excluded.model,
                temperature = excluded.temperature,
                max_tokens = excluded.max_tokens,
                timeout_seconds = excluded.timeout_seconds,
                reasoning_effort = excluded.reasoning_effort,
                max_iter = excluded.max_iter,
                budget_limit_usd = excluded.budget_limit_usd,
                system_prompt = excluded.system_prompt,
                allow_delegation = excluded.allow_delegation,
                tools_json = excluded.tools_json,
                skills_json = excluded.skills_json,
                rules_json = excluded.rules_json,
                is_active = excluded.is_active,
                canvas_x = excluded.canvas_x,
                canvas_y = excluded.canvas_y,
                icon = excluded.icon,
                updated_at = excluded.updated_at;
            """,
            (
                agent.id,
                agent.name,
                agent.project_id,
                agent.role_description,
                agent.role,
                agent.goal,
                agent.backstory,
                agent.agent_type.value,
                agent.parent_id,
                agent.model,
                agent.temperature,
                agent.max_tokens,
                agent.timeout_seconds,
                agent.reasoning_effort,
                agent.max_iter,
                agent.budget_limit_usd,
                agent.system_prompt,
                1 if agent.allow_delegation else 0,
                json.dumps(agent.tools),
                json.dumps(agent.skills),
                json.dumps(agent.rules),
                1 if agent.is_active else 0,
                1 if agent.is_core_meta_agent else 0,
                agent.canvas_x,
                agent.canvas_y,
                agent.icon,
                agent.created_at.isoformat(),
                now_str,
            ),
        )
        saved = self.get(agent.id) or agent
        self._sync_agent_json_to_disk(saved)
        return saved

    def _sync_agent_json_to_disk(self, agent: AgentDefinition) -> None:
        """Sauvegarde miroir atomique au format JSON sur disque pour les Méta-Agents principaux."""
        if not getattr(agent, "is_core_meta_agent", False):
            return
        agent_dict = agent.model_dump(mode="json")
        json_content = json.dumps(agent_dict, indent=2, ensure_ascii=False)
        
        # Nom de fichier cible unique et canonique (zéro doublon)
        filenames = [f"{agent.id}.json"]

        base_dir = settings.v5_root / "data" / "agents"
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            for fname in filenames:
                target_file = base_dir / fname
                target_file.write_text(json_content, encoding="utf-8")
        except Exception:
            pass

    def delete(self, agent_id: str) -> bool:
        agent = self.get(agent_id)
        if not agent or agent.is_core_meta_agent:
            return False
        with db.transaction():
            db.execute("DELETE FROM agent_links WHERE source_agent_id = ? OR target_agent_id = ?;", (agent_id, agent_id))
            db.execute("DELETE FROM agents WHERE id = ?;", (agent_id,))
            # Reparenter les sous-agents orphelins
            db.execute("UPDATE agents SET parent_id = 'agent_architect' WHERE parent_id = ?;", (agent_id,))
            return True


# ------------------------------------------------------------------------------
# 2.B REPOSITORY DES LIAISONS DU CANVAS 2D (DAG WIRES)
# ------------------------------------------------------------------------------

class AgentLinksRepository:
    """Gestionnaire des liaisons de câbles du graphe Canvas 2D (DAG)."""

    def ensure_seeded(self, project_id: str | None = None) -> None:
        """Initialise les liaisons standards si la table est vide."""
        links = self.list_all(project_id=project_id)
        if not links:
            self.apply_template("sequential", project_id=project_id)

    def list_all(
        self,
        project_id: str | None = None,
        is_core_only: bool = False,
        include_core: bool = False,
    ) -> list[AgentLink]:
        with db.get_connection() as conn:
            if is_core_only or project_id == "studio":
                cursor = conn.execute(
                    "SELECT id, project_id, source_agent_id, target_agent_id, link_type, label, is_active, created_at FROM agent_links WHERE project_id IS NULL ORDER BY created_at ASC;"
                )
            elif project_id is not None:
                if include_core:
                    cursor = conn.execute(
                        "SELECT id, project_id, source_agent_id, target_agent_id, link_type, label, is_active, created_at FROM agent_links WHERE project_id = ? OR project_id IS NULL ORDER BY created_at ASC;",
                        (project_id,),
                    )
                else:
                    cursor = conn.execute(
                        "SELECT id, project_id, source_agent_id, target_agent_id, link_type, label, is_active, created_at FROM agent_links WHERE project_id = ? ORDER BY created_at ASC;",
                        (project_id,),
                    )
            else:
                cursor = conn.execute(
                    "SELECT id, project_id, source_agent_id, target_agent_id, link_type, label, is_active, created_at FROM agent_links ORDER BY created_at ASC;"
                )
            rows = cursor.fetchall()
            return [
                AgentLink(
                    id=r[0],
                    project_id=r[1],
                    source_agent_id=r[2],
                    target_agent_id=r[3],
                    link_type=LinkType(r[4]) if r[4] in LinkType._value2member_map_ else LinkType.DATA_FLOW,
                    label=r[5],
                    is_active=bool(r[6]),
                    created_at=datetime.fromisoformat(r[7]),
                )
                for r in rows
            ]

    def create(self, link: AgentLink) -> AgentLink:
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_links (id, project_id, source_agent_id, target_agent_id, link_type, label, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    link_type = excluded.link_type,
                    label = excluded.label,
                    is_active = excluded.is_active;
                """,
                (
                    link.id,
                    link.project_id,
                    link.source_agent_id,
                    link.target_agent_id,
                    link.link_type.value,
                    link.label,
                    1 if link.is_active else 0,
                    link.created_at.isoformat(),
                )
            )
            conn.commit()
        return link

    save = create

    def get(self, link_id: str) -> AgentLink | None:
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, project_id, source_agent_id, target_agent_id, link_type, label, is_active, created_at FROM agent_links WHERE id = ?;",
                (link_id,)
            )
            r = cursor.fetchone()
            if not r:
                return None
            return AgentLink(
                id=r[0],
                project_id=r[1],
                source_agent_id=r[2],
                target_agent_id=r[3],
                link_type=LinkType(r[4]) if r[4] in LinkType._value2member_map_ else LinkType.DATA_FLOW,
                label=r[5],
                is_active=bool(r[6]),
                created_at=datetime.fromisoformat(r[7]),
            )

    def save(self, link: AgentLink) -> AgentLink:
        return self.create(link)

    def delete(self, link_id: str) -> bool:
        with db.get_connection() as conn:
            res = conn.execute("DELETE FROM agent_links WHERE id = ?;", (link_id,))
            conn.commit()
            return res.rowcount > 0

    def clear(self, project_id: str | None = None) -> None:
        with db.get_connection() as conn:
            if project_id:
                conn.execute("DELETE FROM agent_links WHERE project_id = ?;", (project_id,))
            else:
                conn.execute("DELETE FROM agent_links;")
            conn.commit()

    def apply_template(self, template_name: str, project_id: str | None = None) -> list[AgentLink]:
        """Applique un template d'organisation prédéfini."""
        self.clear(project_id=project_id)
        templates = {
            "hybrid_actor_critic": [
                ("agent_copilot", "agent_architect", LinkType.SUPERVISION, "Supervision Projet & Snapshots"),
                ("agent_architect", "agent_model_matcher", LinkType.DIRECT, "Cadrage Rôles & Benchmarks"),
                ("agent_model_matcher", "agent_finops_guardian", LinkType.DIRECT, "Arbitrage Modèles & Quotas"),
                ("agent_architect", "agent_coder", LinkType.DIRECT, "Spécifications & Tâches Atomiques"),
                ("agent_coder", "agent_quality_judge", LinkType.DEBATE, "Validation AST & Score /100"),
                ("agent_quality_judge", "agent_finops_guardian", LinkType.DIRECT, "Certification & Clôture FinOps"),
            ],
            "sequential": [
                ("agent_architect", "agent_model_matcher", LinkType.DIRECT, "Besoins Compétences LLM"),
                ("agent_model_matcher", "agent_coder", LinkType.DIRECT, "Modèle & Contexte Alloué"),
                ("agent_coder", "agent_quality_judge", LinkType.DIRECT, "Code Source & AST"),
                ("agent_quality_judge", "agent_finops_guardian", LinkType.DIRECT, "Score Qualité & Métriques"),
                ("agent_finops_guardian", "agent_copilot", LinkType.DIRECT, "Rapport FinOps & Clôture"),
            ],
            "hierarchical": [
                ("agent_copilot", "agent_architect", LinkType.SUPERVISION, "Supervision Globale"),
                ("agent_architect", "agent_model_matcher", LinkType.SUPERVISION, "Allocation Modèles"),
                ("agent_architect", "agent_coder", LinkType.SUPERVISION, "Délégation Code"),
                ("agent_architect", "agent_quality_judge", LinkType.SUPERVISION, "Consigne Audit"),
                ("agent_architect", "agent_finops_guardian", LinkType.SUPERVISION, "Contrôle Quotas"),
            ],
            "consensus": [
                ("agent_architect", "agent_model_matcher", LinkType.DIRECT, "Besoins Métier"),
                ("agent_model_matcher", "agent_finops_guardian", LinkType.DEBATE, "Débat Efficience / Coûts"),
                ("agent_architect", "agent_coder", LinkType.DIRECT, "Spécifications Initiales"),
                ("agent_coder", "agent_quality_judge", LinkType.DEBATE, "Débat Code & AST"),
                ("agent_quality_judge", "agent_architect", LinkType.DIRECT, "Critique & Score"),
            ],
            "swarm": [
                ("agent_architect", "agent_model_matcher", LinkType.DIRECT, "Handoff Matcher"),
                ("agent_model_matcher", "agent_coder", LinkType.DIRECT, "Handoff Coder"),
                ("agent_coder", "agent_copilot", LinkType.DIRECT, "Handoff Copilot"),
                ("agent_quality_judge", "agent_coder", LinkType.DEBATE, "Feedback Direct"),
                ("agent_finops_guardian", "agent_architect", LinkType.DIRECT, "Bilan Clôture"),
            ],
            "parallel": [
                ("agent_architect", "agent_model_matcher", LinkType.SUPERVISION, "Fan-Out Benchmarks"),
                ("agent_architect", "agent_coder", LinkType.SUPERVISION, "Fan-Out Backend"),
                ("agent_architect", "agent_quality_judge", LinkType.SUPERVISION, "Fan-Out Tests"),
                ("agent_model_matcher", "agent_finops_guardian", LinkType.DIRECT, "Synthèse FinOps"),
                ("agent_coder", "agent_copilot", LinkType.DIRECT, "Fan-In Synthèse"),
                ("agent_quality_judge", "agent_copilot", LinkType.DIRECT, "Fan-In Validation"),
            ],
        }

        links_specs = templates.get(template_name, templates["hybrid_actor_critic"])
        created_links = []
        for src, tgt, l_type, lbl in links_specs:
            link = AgentLink(
                id=f"link_{src}_{tgt}",
                project_id=project_id,
                source_agent_id=src,
                target_agent_id=tgt,
                link_type=l_type,
                label=lbl,
                is_active=True,
            )
            self.create(link)
            created_links.append(link)
        return created_links


# ------------------------------------------------------------------------------
# 3. REPOSITORY DU GRAND LIVRE FINOPS
# ------------------------------------------------------------------------------

class FinOpsRepository:
    def record_inference(self, metric: FinOpsMetric) -> None:
        db.execute(
            """
            INSERT INTO finops_ledger (
                id, timestamp, session_id, project_id, project_name, agent_id,
                agent_name, model, task_name, prompt_tokens, completion_tokens,
                reasoning_tokens, total_tokens, cost_usd, latency_ms, ttft_ms, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                metric.id,
                metric.timestamp.isoformat(),
                metric.session_id,
                metric.project_id,
                metric.project_name,
                metric.agent_id,
                metric.agent_name,
                metric.model,
                metric.task_name,
                metric.prompt_tokens,
                metric.completion_tokens,
                metric.reasoning_tokens,
                metric.total_tokens,
                metric.cost_usd,
                metric.latency_ms,
                metric.ttft_ms,
                metric.status,
            ),
        )

    def list_all(self) -> list[FinOpsMetric]:
        rows = db.fetch_all("SELECT * FROM finops_ledger ORDER BY timestamp ASC;")
        metrics = []
        for r in rows:
            metrics.append(
                FinOpsMetric(
                    id=r["id"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    session_id=r["session_id"],
                    project_id=r["project_id"],
                    project_name=r["project_name"],
                    agent_id=r["agent_id"],
                    agent_name=r["agent_name"],
                    model=r["model"],
                    task_name=r["task_name"],
                    prompt_tokens=r["prompt_tokens"],
                    completion_tokens=r["completion_tokens"],
                    reasoning_tokens=r["reasoning_tokens"],
                    total_tokens=r["total_tokens"],
                    cost_usd=r["cost_usd"],
                    latency_ms=r["latency_ms"],
                    ttft_ms=r["ttft_ms"],
                    status=r["status"],
                )
            )
        return metrics


# ------------------------------------------------------------------------------
# 4. REPOSITORY DU CACHE BENCHMARKS (19 BENCHMARKS ARTIFICIAL ANALYSIS)
# ------------------------------------------------------------------------------

class AABenchmarksRepository:
    """Gestionnaire de persistance du cache des 600+ benchmarks officiels Artificial Analysis (v2 - Pur JSON) et prix OpenRouter."""

    def _row_to_dict(self, r: dict[str, Any]) -> dict[str, Any]:
        evals = json.loads(r["evaluations_json"]) if "evaluations_json" in r and r["evaluations_json"] else {}
        raw = json.loads(r["raw_payload_json"]) if "raw_payload_json" in r and r["raw_payload_json"] else {}
        
        coding_val = float(evals.get("artificial_analysis_coding_index") or evals.get("coding_index") or 0.0)
        intel_val = float(evals.get("artificial_analysis_intelligence_index") or evals.get("intelligence_index") or 0.0)
        speed_val = float(evals.get("median_output_tokens_per_second") or evals.get("speed_tok_s") or raw.get("median_output_tokens_per_second") or 0.0)
        ttft_val = float(evals.get("median_time_to_first_token_seconds") or evals.get("ttft_seconds") or raw.get("median_time_to_first_token_seconds") or 0.0)

        d = {
            "id": r["id"],
            "slug": r["slug"],
            "name": r["name"],
            "creator_name": r["creator_name"],
            "creator_slug": r.get("creator_slug", ""),
            "release_date": r.get("release_date", ""),
            "intelligence_index": intel_val,
            "coding_index": coding_val,
            "speed_tok_s": speed_val,
            "ttft_seconds": ttft_val,
            "price_in_usd": r.get("price_in_usd") or 0.0,
            "price_out_usd": r.get("price_out_usd") or 0.0,
            "price_cache_usd": r.get("price_cache_usd") or 0.0,
            "price_blended_usd": r.get("price_blended_usd") or 0.0,
            "evaluations": evals,
            "raw_payload": raw,
            "last_synced_at": r.get("last_synced_at", ""),
        }
        # Accès direct dynamique aux benchmarks usuels pour compatibilité transparente
        d["terminalbench_v2_1"] = evals.get("terminalbench_v2_1") or evals.get("terminal_bench_v2_1") or 0.0
        d["gpqa_diamond"] = evals.get("gpqa_diamond") or evals.get("gpqa") or 0.0
        d["scicode"] = evals.get("scicode") or 0.0
        return d

    def list_all(
        self,
        q: str | None = None,
        min_coding_score: float | None = None,
        max_price_out_usd: float | None = None,
        sort_by: str = "coding_desc",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM aa_benchmarks_cache WHERE 1=1"
        params: list[Any] = []
        if q:
            like_p = f"%{q}%"
            query += " AND (slug LIKE ? OR name LIKE ? OR creator_name LIKE ?)"
            params.extend([like_p, like_p, like_p])
        if min_coding_score is not None:
            query += " AND COALESCE(json_extract(evaluations_json, '$.artificial_analysis_coding_index'), json_extract(evaluations_json, '$.coding_index'), 0.0) >= ?"
            params.append(min_coding_score)
        if max_price_out_usd is not None:
            query += " AND price_out_usd <= ?"
            params.append(max_price_out_usd)

        # Dynamic sorting (SQLite JSON1)
        if sort_by == "coding_desc":
            query += " ORDER BY COALESCE(json_extract(evaluations_json, '$.artificial_analysis_coding_index'), json_extract(evaluations_json, '$.coding_index'), 0.0) DESC"
        elif sort_by == "terminalbench_desc":
            query += " ORDER BY COALESCE(json_extract(evaluations_json, '$.terminalbench_v2_1'), json_extract(evaluations_json, '$.terminal_bench_v2_1'), 0.0) DESC"
        elif sort_by == "gpqa_desc":
            query += " ORDER BY COALESCE(json_extract(evaluations_json, '$.gpqa'), json_extract(evaluations_json, '$.gpqa_diamond'), 0.0) DESC"
        elif sort_by == "scicode_desc":
            query += " ORDER BY COALESCE(json_extract(evaluations_json, '$.scicode'), 0.0) DESC"
        elif sort_by == "price_asc":
            query += " ORDER BY price_out_usd ASC"
        elif sort_by == "speed_desc":
            query += " ORDER BY COALESCE(json_extract(evaluations_json, '$.median_output_tokens_per_second'), json_extract(evaluations_json, '$.speed_tok_s'), 0.0) DESC"
        elif sort_by == "intelligence_desc":
            query += " ORDER BY COALESCE(json_extract(evaluations_json, '$.artificial_analysis_intelligence_index'), json_extract(evaluations_json, '$.intelligence_index'), 0.0) DESC"
        else:
            query += " ORDER BY COALESCE(json_extract(evaluations_json, '$.artificial_analysis_coding_index'), json_extract(evaluations_json, '$.coding_index'), 0.0) DESC"

        if limit > 0:
            query += f" LIMIT {int(limit)}"

        rows = db.fetch_all(query, tuple(params))
        return [self._row_to_dict(r) for r in rows]

    def find_by_slug(self, slug: str) -> dict[str, Any] | None:
        if not slug:
            return None
        clean = slug.strip().lower()
        row = db.fetch_one("SELECT * FROM aa_benchmarks_cache WHERE slug = ? COLLATE NOCASE;", (clean,))
        if not row:
            row = db.fetch_one("SELECT * FROM aa_benchmarks_cache WHERE slug LIKE ? OR name LIKE ? LIMIT 1;", (f"%{clean}%", f"%{clean}%"))
        return self._row_to_dict(row) if row else None

    def upsert_all(self, models_data: list[dict[str, Any]]) -> int:
        """Enregistre par lot atomique l'intégralité des modèles en base (Schéma 100% JSON Pur)."""
        if not models_data:
            return 0
        from uuid import uuid4
        now_str = utc_now().isoformat()
        records = []
        for m in models_data:
            evals = dict(m.get("evaluations", {}) or {})
            if "coding_index" in m and "artificial_analysis_coding_index" not in evals:
                evals["artificial_analysis_coding_index"] = m["coding_index"]
            if "intelligence_index" in m and "artificial_analysis_intelligence_index" not in evals:
                evals["artificial_analysis_intelligence_index"] = m["intelligence_index"]
            if "speed_tok_s" in m and "median_output_tokens_per_second" not in evals:
                evals["median_output_tokens_per_second"] = m["speed_tok_s"]
            if "ttft_seconds" in m and "median_time_to_first_token_seconds" not in evals:
                evals["median_time_to_first_token_seconds"] = m["ttft_seconds"]

            records.append((
                m.get("id") or m.get("slug") or str(uuid4()),
                m.get("slug", "").strip().lower(),
                m.get("name") or m.get("slug") or "Modèle",
                m.get("creator_name") or m.get("creator") or "Unknown",
                m.get("creator_slug") or "",
                m.get("release_date") or "",
                float(m.get("price_in_usd") or 0.0),
                float(m.get("price_out_usd") or 0.0),
                float(m.get("price_cache_usd") or 0.0),
                float(m.get("price_blended_usd") or 0.0),
                json.dumps(evals),
                json.dumps(m.get("raw_payload", {}) or m),
                now_str,
            ))

        with db.transaction():
            db.executemany(
                """
                INSERT INTO aa_benchmarks_cache (
                    id, slug, name, creator_name, creator_slug, release_date,
                    price_in_usd, price_out_usd, price_cache_usd, price_blended_usd,
                    evaluations_json, raw_payload_json, last_synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    creator_name = excluded.creator_name,
                    creator_slug = excluded.creator_slug,
                    release_date = excluded.release_date,
                    price_in_usd = excluded.price_in_usd,
                    price_out_usd = excluded.price_out_usd,
                    price_cache_usd = excluded.price_cache_usd,
                    price_blended_usd = excluded.price_blended_usd,
                    evaluations_json = excluded.evaluations_json,
                    raw_payload_json = excluded.raw_payload_json,
                    last_synced_at = excluded.last_synced_at;
                """,
                records,
            )
        return len(records)

    def get_available_metric_keys(self) -> list[str]:
        """Retourne dynamiquement toutes les clés de benchmarks existantes dans le JSON."""
        rows = db.fetch_all("SELECT evaluations_json FROM aa_benchmarks_cache LIMIT 100;")
        keys = set()
        for r in rows:
            try:
                ev = json.loads(r["evaluations_json"])
                if isinstance(ev, dict):
                    keys.update(ev.keys())
            except Exception:
                pass
        return sorted(list(keys))

    def get_last_sync_time(self) -> datetime | None:
        row = db.fetch_one("SELECT MAX(last_synced_at) as latest FROM aa_benchmarks_cache;")
        if row and row["latest"]:
            try:
                return datetime.fromisoformat(row["latest"])
            except Exception:
                pass
        return None

    def get_sync_status(self) -> dict[str, Any]:
        count_row = db.fetch_one("SELECT COUNT(*) as total FROM aa_benchmarks_cache;")
        total = count_row["total"] if count_row else 0
        last_sync = self.get_last_sync_time()
        return {
            "total_models": total,
            "last_synced_at": last_sync.isoformat() if last_sync else None,
            "available_metrics_count": len(self.get_available_metric_keys()),
        }

    # Backward compatibility with existing methods
    def get_cached_benchmarks(self) -> list[BenchmarkRecord]:
        rows = self.list_all(limit=100)
        records = []
        for r in rows:
            badge = FinOpsBadge.SWEET_SPOT
            if (r.get("coding_index") or 0) >= 74:
                badge = FinOpsBadge.TOP_PERFORMANCE
            elif (r.get("price_out_usd") or 0) <= 0.5:
                badge = FinOpsBadge.ULTRA_ECO
            evals = r.get("evaluations", {}) or {}
            math_val = evals.get("artificial_analysis_math_index") or evals.get("math_index") or 0.0
            gpqa_val = (evals.get("gpqa", 0.0) or evals.get("gpqa_diamond", 0.0))
            if gpqa_val and gpqa_val <= 1.0:
                gpqa_val = gpqa_val * 100.0
            reasoning_val = math_val or gpqa_val or 75.0

            records.append(
                BenchmarkRecord(
                    model_id=r.get("id") or r["slug"],
                    name=r["name"],
                    creator=r["creator_name"],
                    quality_index=r.get("intelligence_index") or 80.0,
                    coding_score=r.get("coding_index") or 70.0,
                    reasoning_score=float(reasoning_val),
                    speed_tok_s=r.get("speed_tok_s") or 50.0,
                    price_in_usd=r.get("price_in_usd") or 0.0,
                    price_out_usd=r.get("price_out_usd") or 0.0,
                    price_cache_usd=r.get("price_cache_usd") or 0.0,
                    context_length=128000,
                    badge=badge,
                    evaluations=evals,
                    updated_at=datetime.fromisoformat(r["last_synced_at"]) if r.get("last_synced_at") else utc_now(),
                )
            )
        return records

    def save_benchmarks(self, records: list[BenchmarkRecord]) -> None:
        models = []
        for r in records:
            models.append({
                "id": r.model_id,
                "slug": r.model_id.split("/")[-1].replace(".", "-"),
                "name": r.name,
                "creator_name": r.creator,
                "intelligence_index": r.quality_index,
                "coding_index": r.coding_score,
                "math_index": r.reasoning_score,
                "speed_tok_s": r.speed_tok_s,
                "price_in_usd": r.price_in_usd,
                "price_out_usd": r.price_out_usd,
                "price_cache_usd": r.price_cache_usd,
                "evaluations": r.evaluations,
            })
        self.upsert_all(models)



BenchmarksRepository = AABenchmarksRepository


# ------------------------------------------------------------------------------
# 5. REPOSITORIES DES 7 PILIERS (MCP, SKILLS, RULES, HOOKS, COMMANDS, HITL, CHECKPOINTS)
# ------------------------------------------------------------------------------

class McpRepository:
    def list_servers(self, project_id: str | None = None, active_only: bool = False) -> list[McpServerConfig]:
        query = "SELECT * FROM mcp_servers WHERE 1=1"
        params: list[Any] = []
        if project_id:
            query += " AND (project_id = ? OR project_id IS NULL OR project_id = '')"
            params.append(project_id)
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY name ASC;"

        rows = db.fetch_all(query, tuple(params))
        servers = []
        for r in rows:
            servers.append(
                McpServerConfig(
                    id=r["id"],
                    name=r["name"],
                    transport=McpTransport(r["transport"]),
                    command_or_url=r["command_or_url"],
                    args=json.loads(r["args_json"]),
                    env=json.loads(r["env_json"]),
                    project_id=r.get("project_id"),
                    is_active=bool(r["is_active"]),
                    status=r["status"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
            )
        return servers

    def save_server(self, server: McpServerConfig) -> McpServerConfig:
        now_str = utc_now().isoformat()
        db.execute(
            """
            INSERT INTO mcp_servers (id, name, transport, command_or_url, args_json, env_json, project_id, is_active, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                transport = excluded.transport,
                command_or_url = excluded.command_or_url,
                args_json = excluded.args_json,
                env_json = excluded.env_json,
                project_id = excluded.project_id,
                is_active = excluded.is_active,
                status = excluded.status,
                updated_at = excluded.updated_at;
            """,
            (
                server.id,
                server.name,
                server.transport.value,
                server.command_or_url,
                json.dumps(server.args),
                json.dumps(server.env),
                server.project_id,
                1 if server.is_active else 0,
                server.status,
                server.created_at.isoformat(),
                now_str,
            ),
        )
        return server

    def delete_server(self, server_id: str) -> bool:
        with db.transaction():
            res = db.execute("DELETE FROM mcp_servers WHERE id = ?;", (server_id,))
            return res.rowcount > 0

    def list_tools(
        self,
        project_id: str | None = None,
        active_only: bool = False,
        primitive: str | None = None,
    ) -> list[McpToolDefinition]:
        query = "SELECT * FROM mcp_tools WHERE 1=1"
        params: list[Any] = []
        if project_id:
            query += " AND (project_id = ? OR project_id IS NULL OR project_id = '')"
            params.append(project_id)
        if active_only:
            query += " AND is_active = 1"
        if primitive:
            query += " AND mcp_primitive = ?"
            params.append(primitive)
        query += " ORDER BY name ASC;"

        rows = db.fetch_all(query, tuple(params))
        tools = []
        for r in rows:
            tools.append(
                McpToolDefinition(
                    id=r["id"],
                    server_id=r.get("server_id"),
                    name=r["name"],
                    description=r["description"],
                    category=r.get("category", "Système"),
                    parameters_schema=json.loads(r["parameters_schema_json"]),
                    project_id=r.get("project_id"),
                    mcp_primitive=r.get("mcp_primitive", "tool"),
                    is_idempotent=bool(r.get("is_idempotent", 0)),
                    is_critical=bool(r.get("is_critical", 0)),
                    is_active=bool(r["is_active"]),
                    is_core=bool(r["is_core"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
            )
        return tools

    def save_tool(self, tool: McpToolDefinition) -> McpToolDefinition:
        now_str = utc_now().isoformat()
        db.execute(
            """
            INSERT INTO mcp_tools (id, server_id, name, description, category, parameters_schema_json, project_id, mcp_primitive, is_idempotent, is_critical, is_active, is_core, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                server_id = excluded.server_id,
                name = excluded.name,
                description = excluded.description,
                category = excluded.category,
                parameters_schema_json = excluded.parameters_schema_json,
                project_id = excluded.project_id,
                mcp_primitive = excluded.mcp_primitive,
                is_idempotent = excluded.is_idempotent,
                is_critical = excluded.is_critical,
                is_active = excluded.is_active,
                is_core = excluded.is_core,
                updated_at = excluded.updated_at;
            """,
            (
                tool.id,
                tool.server_id,
                tool.name,
                tool.description,
                tool.category,
                json.dumps(tool.parameters_schema),
                tool.project_id,
                tool.mcp_primitive,
                1 if tool.is_idempotent else 0,
                1 if tool.is_critical else 0,
                1 if tool.is_active else 0,
                1 if tool.is_core else 0,
                tool.created_at.isoformat(),
                now_str,
            ),
        )
        return tool

    def delete_tool(self, tool_id: str) -> bool:
        res = db.execute("DELETE FROM mcp_tools WHERE id = ? AND is_core = 0;", (tool_id,))
        return res.rowcount > 0

    def search_tools_fts(self, query_text: str, project_id: str | None = None, limit: int = 5) -> list[McpToolDefinition]:
        """Recherche plein-texte ultra-rapide FTS5 dans le catalogue d'outils."""
        clean_q = "".join(c for c in query_text if c.isalnum() or c.isspace()).strip()
        if not clean_q:
            return self.list_tools(project_id=project_id, active_only=True)[:limit]

        terms = [f'"{w}*"' for w in clean_q.split() if len(w) > 1]
        if not terms:
            terms = [f'"{clean_q}"']
        match_query = " OR ".join(terms)

        sql = """
            SELECT t.* FROM mcp_tools t
            JOIN mcp_tools_fts fts ON t.rowid = fts.rowid
            WHERE mcp_tools_fts MATCH ?
              AND t.is_active = 1
              AND (t.project_id = ? OR t.project_id IS NULL OR t.project_id = '')
            ORDER BY rank
            LIMIT ?;
        """
        try:
            rows = db.fetch_all(sql, (match_query, project_id or "", limit))
        except Exception:
            # Fallback direct LIKE si FTS5 rencontre un symbole invalide
            like_term = f"%{clean_q}%"
            sql_fallback = """
                SELECT * FROM mcp_tools
                WHERE is_active = 1
                  AND (name LIKE ? OR description LIKE ? OR category LIKE ?)
                  AND (project_id = ? OR project_id IS NULL OR project_id = '')
                LIMIT ?;
            """
            rows = db.fetch_all(sql_fallback, (like_term, like_term, like_term, project_id or "", limit))

        tools = []
        for r in rows:
            tools.append(
                McpToolDefinition(
                    id=r["id"],
                    server_id=r.get("server_id"),
                    name=r["name"],
                    description=r["description"],
                    category=r.get("category", "Système"),
                    parameters_schema=json.loads(r["parameters_schema_json"]),
                    project_id=r.get("project_id"),
                    mcp_primitive=r.get("mcp_primitive", "tool"),
                    is_idempotent=bool(r.get("is_idempotent", 0)),
                    is_critical=bool(r.get("is_critical", 0)),
                    is_active=bool(r["is_active"]),
                    is_core=bool(r["is_core"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
            )
        return tools


class SkillsRepository:
    def list_skills(self, scope: SkillScope | None = None, project_id: str | None = None) -> list[SkillDefinition]:
        query = "SELECT * FROM skills_index WHERE 1=1"
        params: list[Any] = []
        if scope:
            query += " AND scope = ?"
            params.append(scope.value)
        if project_id:
            query += " AND (project_id = ? OR scope = 'global')"
            params.append(project_id)
        query += " ORDER BY name ASC;"

        rows = db.fetch_all(query, params)
        skills = []
        for r in rows:
            skills.append(
                SkillDefinition(
                    id=r["id"],
                    name=r["name"],
                    description=r["description"],
                    version=r["version"],
                    scope=SkillScope(r["scope"]),
                    project_id=r["project_id"],
                    file_path=r["file_path"],
                    tags=json.loads(r["tags_json"]),
                    invocations_count=r["invocations_count"],
                    success_count=r["success_count"],
                    is_active=bool(r["is_active"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
            )
        return skills

    def get_skill_by_name(self, name: str) -> SkillDefinition | None:
        row = db.fetch_one("SELECT * FROM skills_index WHERE name = ?;", (name,))
        if not row:
            return None
        return SkillDefinition(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            version=row["version"],
            scope=SkillScope(row["scope"]),
            project_id=row["project_id"],
            file_path=row["file_path"],
            tags=json.loads(row["tags_json"]),
            invocations_count=row["invocations_count"],
            success_count=row["success_count"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_skill(self, skill: SkillDefinition) -> SkillDefinition:
        existing = self.get_skill_by_name(skill.name)
        if existing:
            skill.id = existing.id
        now_str = utc_now().isoformat()
        db.execute(
            """
            INSERT INTO skills_index (id, name, description, version, scope, project_id, file_path, tags_json, invocations_count, success_count, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description = excluded.description,
                version = excluded.version,
                scope = excluded.scope,
                project_id = excluded.project_id,
                file_path = excluded.file_path,
                tags_json = excluded.tags_json,
                invocations_count = excluded.invocations_count,
                success_count = excluded.success_count,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at;
            """,
            (
                skill.id,
                skill.name,
                skill.description,
                skill.version,
                skill.scope.value,
                skill.project_id,
                skill.file_path,
                json.dumps(skill.tags),
                skill.invocations_count,
                skill.success_count,
                1 if skill.is_active else 0,
                skill.created_at.isoformat(),
                now_str,
            ),
        )
        return skill

    def delete_skill(self, skill_id: str) -> bool:
        res = db.execute("DELETE FROM skills_index WHERE id = ? OR name = ?;", (skill_id, skill_id))
        return res.rowcount > 0

    def search_skills_fts(self, query_text: str, project_id: str | None = None, limit: int = 4) -> list[SkillDefinition]:
        """Recherche plein-texte ultra-rapide FTS5 dans le catalogue de playbooks de compétences."""
        clean_q = "".join(c for c in query_text if c.isalnum() or c.isspace()).strip()
        if not clean_q:
            return [s for s in self.list_skills(project_id=project_id) if s.is_active][:limit]

        terms = [f'"{w}*"' for w in clean_q.split() if len(w) > 1]
        if not terms:
            terms = [f'"{clean_q}"']
        match_query = " OR ".join(terms)

        sql = """
            SELECT s.* FROM skills_index s
            JOIN skills_fts fts ON s.rowid = fts.rowid
            WHERE skills_fts MATCH ?
              AND s.is_active = 1
              AND (s.project_id = ? OR s.scope = 'global' OR s.project_id IS NULL OR s.project_id = '')
            ORDER BY rank
            LIMIT ?;
        """
        try:
            rows = db.fetch_all(sql, (match_query, project_id or "", limit))
        except Exception:
            # Fallback direct LIKE sécurisé
            like_term = f"%{clean_q}%"
            sql_fallback = """
                SELECT * FROM skills_index
                WHERE is_active = 1
                  AND (name LIKE ? OR description LIKE ? OR tags_json LIKE ?)
                  AND (project_id = ? OR scope = 'global' OR project_id IS NULL OR project_id = '')
                LIMIT ?;
            """
            rows = db.fetch_all(sql_fallback, (like_term, like_term, like_term, project_id or "", limit))

        skills = []
        for r in rows:
            skills.append(
                SkillDefinition(
                    id=r["id"],
                    name=r["name"],
                    description=r["description"],
                    version=r["version"],
                    scope=SkillScope(r["scope"]),
                    project_id=r["project_id"],
                    file_path=r["file_path"],
                    tags=json.loads(r["tags_json"]),
                    invocations_count=r["invocations_count"],
                    success_count=r["success_count"],
                    is_active=bool(r["is_active"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
            )
        return skills


class RulesRepository:
    def get_rule_by_name(self, name: str, project_id: str | None = None) -> RuleDefinition | None:
        if project_id:
            row = db.fetch_one("SELECT * FROM rules_index WHERE name = ? AND project_id = ? LIMIT 1;", (name, project_id))
        else:
            row = db.fetch_one("SELECT * FROM rules_index WHERE name = ? AND (project_id IS NULL OR project_id = '' OR scope = 'global') LIMIT 1;", (name,))
        if not row:
            return None
        return RuleDefinition(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            scope=RuleScope(row["scope"]),
            project_id=row["project_id"],
            file_path=row["file_path"],
            content=row["content"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_rules(self, scope: RuleScope | None = None, project_id: str | None = None, active_only: bool = True) -> list[RuleDefinition]:
        query = "SELECT * FROM rules_index WHERE 1=1"
        params: list[Any] = []
        if active_only:
            query += " AND is_active = 1"
        if scope:
            query += " AND scope = ?"
            params.append(scope.value)
        if project_id:
            query += " AND (project_id = ? OR scope = 'global')"
            params.append(project_id)
        query += " ORDER BY name ASC;"

        rows = db.fetch_all(query, params)
        rules = []
        for r in rows:
            rules.append(
                RuleDefinition(
                    id=r["id"],
                    name=r["name"],
                    category=r["category"],
                    scope=RuleScope(r["scope"]),
                    project_id=r["project_id"],
                    file_path=r["file_path"],
                    content=r["content"],
                    is_active=bool(r["is_active"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
            )
        return rules

    def save_rule(self, rule: RuleDefinition) -> RuleDefinition:
        existing = self.get_rule_by_name(rule.name, rule.project_id)
        if existing:
            rule.id = existing.id
        now_str = utc_now().isoformat()
        db.execute(
            """
            INSERT INTO rules_index (id, name, category, scope, project_id, file_path, content, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                scope = excluded.scope,
                project_id = excluded.project_id,
                file_path = excluded.file_path,
                content = excluded.content,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at;
            """,
            (
                rule.id,
                rule.name,
                rule.category,
                rule.scope.value,
                rule.project_id,
                rule.file_path,
                rule.content,
                1 if rule.is_active else 0,
                rule.created_at.isoformat(),
                now_str,
            ),
        )
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        res = db.execute("DELETE FROM rules_index WHERE id = ? OR name = ?;", (rule_id, rule_id))
        return res.rowcount > 0


class HooksRepository:
    def _row_to_hook(self, row: dict[str, Any]) -> HookDefinition:
        return HookDefinition(
            id=row["id"],
            name=row["name"],
            description=row.get("description", "") or "",
            event_type=HookEventType(row["event_type"]),
            action_type=row.get("action_type", "validator"),
            target=row.get("target", "") or "",
            config=json.loads(row.get("config_json", "{}")),
            scope=RuleScope(row.get("scope", "global")),
            project_id=row.get("project_id"),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_hook_by_id(self, hook_id: str) -> HookDefinition | None:
        row = db.fetch_one("SELECT * FROM hooks_index WHERE id = ? LIMIT 1;", (hook_id,))
        if not row:
            return None
        return self._row_to_hook(row)

    def get_hook_by_name(self, name: str, project_id: str | None = None) -> HookDefinition | None:
        if project_id:
            row = db.fetch_one(
                "SELECT * FROM hooks_index WHERE name = ? AND (project_id = ? OR scope = 'global') ORDER BY scope DESC LIMIT 1;",
                (name, project_id),
            )
        else:
            row = db.fetch_one("SELECT * FROM hooks_index WHERE name = ? LIMIT 1;", (name,))
        if not row:
            return None
        return self._row_to_hook(row)

    def list_hooks(
        self,
        event_type: HookEventType | None = None,
        active_only: bool = True,
        project_id: str | None = None,
    ) -> list[HookDefinition]:
        query = "SELECT * FROM hooks_index WHERE 1=1"
        params: list[Any] = []
        if active_only:
            query += " AND is_active = 1"
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)
        if project_id is not None:
            query += " AND (project_id = ? OR scope = 'global')"
            params.append(project_id)
        query += " ORDER BY name ASC;"

        rows = db.fetch_all(query, params)
        return [self._row_to_hook(r) for r in rows]

    def save_hook(self, hook: HookDefinition) -> HookDefinition:
        existing = self.get_hook_by_name(hook.name, project_id=hook.project_id)
        if existing:
            hook.id = existing.id
        now_str = utc_now().isoformat()
        db.execute(
            """
            INSERT INTO hooks_index (
                id, name, description, event_type, action_type, target, config_json, scope, project_id, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                event_type = excluded.event_type,
                action_type = excluded.action_type,
                target = excluded.target,
                config_json = excluded.config_json,
                scope = excluded.scope,
                project_id = excluded.project_id,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at;
            """,
            (
                hook.id,
                hook.name,
                hook.description,
                hook.event_type.value,
                hook.action_type,
                hook.target,
                json.dumps(hook.config),
                hook.scope.value,
                hook.project_id,
                1 if hook.is_active else 0,
                hook.created_at.isoformat(),
                now_str,
            ),
        )
        return hook

    def delete_hook(self, hook_id: str) -> bool:
        res = db.execute("DELETE FROM hooks_index WHERE id = ? OR name = ?;", (hook_id, hook_id))
        return res.rowcount > 0

    # --------------------------------------------------------------------------
    # Journal d'Audit des Sentinelles (Hooks Audit Trail)
    # --------------------------------------------------------------------------

    def log_execution(self, audit_log: HookAuditLog) -> None:
        """Enregistre un événement d'exécution de hook dans le journal d'audit."""
        try:
            db.execute(
                """
                INSERT INTO hooks_audit_log (
                    id, hook_id, hook_name, event_type, action_type, status, duration_ms, payload_summary, result_summary, error, project_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    audit_log.id,
                    audit_log.hook_id,
                    audit_log.hook_name,
                    audit_log.event_type.value,
                    audit_log.action_type,
                    audit_log.status,
                    round(audit_log.duration_ms, 2),
                    audit_log.payload_summary[:500],
                    audit_log.result_summary[:500],
                    audit_log.error,
                    audit_log.project_id,
                    audit_log.created_at.isoformat(),
                ),
            )
        except Exception as err:
            logger.warning("Erreur lors de l'enregistrement de l'audit log hook: %s", err)

    def list_audit_logs(self, limit: int = 50, project_id: str | None = None) -> list[HookAuditLog]:
        """Récupère les derniers journaux d'audit de sentinelles."""
        query = "SELECT * FROM hooks_audit_log WHERE 1=1"
        params: list[Any] = []
        if project_id is not None:
            query += " AND (project_id = ? OR project_id IS NULL)"
            params.append(project_id)
        query += " ORDER BY created_at DESC LIMIT ?;"
        params.append(limit)

        rows = db.fetch_all(query, params)
        logs = []
        for r in rows:
            logs.append(
                HookAuditLog(
                    id=r["id"],
                    hook_id=r["hook_id"],
                    hook_name=r["hook_name"],
                    event_type=HookEventType(r["event_type"]),
                    action_type=r["action_type"],
                    status=r["status"],
                    duration_ms=float(r["duration_ms"]),
                    payload_summary=r["payload_summary"],
                    result_summary=r["result_summary"],
                    error=r.get("error"),
                    project_id=r.get("project_id"),
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
            )
        return logs


class CommandsRepository:
    def list_commands(
        self,
        active_only: bool = True,
        scope: RuleScope | None = None,
        project_id: str | None = None,
    ) -> list[CommandDefinition]:
        query = "SELECT * FROM commands_index WHERE 1=1"
        params: list[Any] = []
        if active_only:
            query += " AND is_active = 1"
        if scope:
            query += " AND scope = ?"
            params.append(scope.value)
        if project_id:
            query += " AND (project_id = ? OR project_id IS NULL OR scope = 'global')"
            params.append(project_id)
        query += " ORDER BY command ASC;"

        rows = db.fetch_all(query, params)
        commands = []
        for r in rows:
            commands.append(
                CommandDefinition(
                    id=r["id"],
                    command=r["command"],
                    name=r["name"],
                    description=r["description"],
                    usage=r.get("usage") or "",
                    category=r.get("category") or "Système",
                    handler_type=r["handler_type"],
                    target=r["target"],
                    scope=RuleScope(r.get("scope") or "global"),
                    project_id=r.get("project_id"),
                    is_active=bool(r["is_active"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
            )
        return commands

    def get_command(self, cmd: str) -> CommandDefinition | None:
        normalized = cmd if cmd.startswith("/") else f"/{cmd}"
        row = db.fetch_one("SELECT * FROM commands_index WHERE command = ? OR id = ?;", (normalized, cmd))
        if not row:
            return None
        return CommandDefinition(
            id=row["id"],
            command=row["command"],
            name=row["name"],
            description=row["description"],
            usage=row.get("usage") or "",
            category=row.get("category") or "Système",
            handler_type=row["handler_type"],
            target=row["target"],
            scope=RuleScope(row.get("scope") or "global"),
            project_id=row.get("project_id"),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_command(self, cmd: CommandDefinition) -> CommandDefinition:
        now_str = utc_now().isoformat()
        db.execute(
            """
            INSERT INTO commands_index (id, command, name, description, usage, category, handler_type, target, scope, project_id, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(command) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                usage = excluded.usage,
                category = excluded.category,
                handler_type = excluded.handler_type,
                target = excluded.target,
                scope = excluded.scope,
                project_id = excluded.project_id,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at;
            """,
            (
                cmd.id,
                cmd.command,
                cmd.name,
                cmd.description,
                cmd.usage,
                cmd.category,
                cmd.handler_type,
                cmd.target,
                cmd.scope.value,
                cmd.project_id,
                1 if cmd.is_active else 0,
                cmd.created_at.isoformat(),
                now_str,
            ),
        )
        return cmd

    def delete_command(self, cmd_or_id: str) -> bool:
        normalized = cmd_or_id if cmd_or_id.startswith("/") else f"/{cmd_or_id}"
        res = db.execute("DELETE FROM commands_index WHERE id = ? OR command = ?;", (cmd_or_id, normalized))
        return res.rowcount > 0


class HitlRepository:
    def list_requests(self, status: HitlRequestStatus | None = None, limit: int = 1000, project_id: str | None = None) -> list[HitlRequest]:
        query = "SELECT * FROM hitl_requests WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status.value)
        if project_id:
            query += " AND (project_id = ? OR project_id IS NULL)"
            params.append(project_id)
        query += " ORDER BY created_at DESC LIMIT ?;"
        params.append(limit)

        rows = db.fetch_all(query, params)
        requests = []
        for r in rows:
            pld = json.loads(r["payload_json"]) if r["payload_json"] else {}
            requests.append(
                HitlRequest(
                    id=r["id"],
                    project_id=r["project_id"],
                    agent_id=r["agent_id"],
                    request_type=r["request_type"],
                    title=r["title"],
                    description=r["description"],
                    payload=pld,
                    plain_reason=pld.get("plain_reason", ""),
                    project_impact=pld.get("project_impact", ""),
                    is_urgent=pld.get("is_urgent", False),
                    status=HitlRequestStatus(r["status"]),
                    rejection_reason=r["rejection_reason"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    resolved_at=datetime.fromisoformat(r["resolved_at"]) if r["resolved_at"] else None,
                )
            )
        return requests

    def save_request(self, req: HitlRequest) -> HitlRequest:
        pld = dict(req.payload) if isinstance(req.payload, dict) else {}
        if req.plain_reason:
            pld["plain_reason"] = req.plain_reason
        if req.project_impact:
            pld["project_impact"] = req.project_impact
        if req.is_urgent:
            pld["is_urgent"] = req.is_urgent

        db.execute(
            """
            INSERT INTO hitl_requests (id, project_id, agent_id, request_type, title, description, payload_json, status, rejection_reason, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                rejection_reason = excluded.rejection_reason,
                resolved_at = excluded.resolved_at;
            """,
            (
                req.id,
                req.project_id,
                req.agent_id,
                req.request_type,
                req.title,
                req.description,
                json.dumps(pld),
                req.status.value,
                req.rejection_reason,
                req.created_at.isoformat(),
                req.resolved_at.isoformat() if req.resolved_at else None,
            ),
        )
        return req

    def resolve_request(self, request_id: str, status: HitlRequestStatus, rejection_reason: str | None = None) -> HitlRequest | None:
        now_str = utc_now().isoformat()
        db.execute(
            """
            UPDATE hitl_requests
            SET status = ?, rejection_reason = ?, resolved_at = ?
            WHERE id = ?;
            """,
            (status.value, rejection_reason, now_str, request_id),
        )
        row = db.fetch_one("SELECT * FROM hitl_requests WHERE id = ?;", (request_id,))
        if not row:
            return None
        pld = json.loads(row["payload_json"]) if row["payload_json"] else {}
        return HitlRequest(
            id=row["id"],
            project_id=row["project_id"],
            agent_id=row["agent_id"],
            request_type=row["request_type"],
            title=row["title"],
            description=row["description"],
            payload=pld,
            plain_reason=pld.get("plain_reason", ""),
            project_impact=pld.get("project_impact", ""),
            is_urgent=pld.get("is_urgent", False),
            status=HitlRequestStatus(row["status"]),
            rejection_reason=row["rejection_reason"],
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        )


class CheckpointsRepository:
    def save_checkpoint(self, checkpoint: CheckpointData) -> CheckpointData:
        db.execute(
            """
            INSERT INTO checkpoints (id, project_id, thread_id, step_name, state_json, files_snapshot_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                checkpoint.id,
                checkpoint.project_id,
                checkpoint.thread_id,
                checkpoint.step_name,
                json.dumps(checkpoint.state_payload),
                json.dumps(checkpoint.files_snapshot),
                checkpoint.created_at.isoformat(),
            ),
        )
        return checkpoint

    def get_latest_checkpoint(self, project_id: str) -> CheckpointData | None:
        row = db.fetch_one(
            "SELECT * FROM checkpoints WHERE project_id = ? ORDER BY created_at DESC LIMIT 1;", (project_id,)
        )
        if not row:
            return None
        return CheckpointData(
            id=row["id"],
            project_id=row["project_id"],
            thread_id=row["thread_id"],
            step_name=row["step_name"],
            state_payload=json.loads(row["state_json"]),
            files_snapshot=json.loads(row["files_snapshot_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_checkpoints(self, project_id: str) -> list[CheckpointData]:
        rows = db.fetch_all(
            "SELECT * FROM checkpoints WHERE project_id = ? ORDER BY created_at DESC;", (project_id,)
        )
        checkpoints = []
        for r in rows:
            checkpoints.append(
                CheckpointData(
                    id=r["id"],
                    project_id=r["project_id"],
                    thread_id=r["thread_id"],
                    step_name=r["step_name"],
                    state_payload=json.loads(r["state_json"]),
                    files_snapshot=json.loads(r["files_snapshot_json"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
            )
        return checkpoints


class LessonsLearnedRepository:
    def list_lessons(self, topic: str | None = None, project_id: str | None = None) -> list[LessonLearned]:
        query = "SELECT * FROM lessons_learned WHERE 1=1"
        params: list[Any] = []
        if topic:
            query += " AND topic LIKE ?"
            params.append(f"%{topic}%")
        if project_id:
            query += " AND (project_id = ? OR scope = 'global')"
            params.append(project_id)
        query += " ORDER BY created_at DESC;"

        rows = db.fetch_all(query, params)
        lessons = []
        for r in rows:
            lessons.append(
                LessonLearned(
                    id=r["id"],
                    scope=r["scope"],
                    project_id=r["project_id"],
                    topic=r["topic"],
                    problem_statement=r["problem_statement"],
                    solution_applied=r["solution_applied"],
                    prevention_rule=r["prevention_rule"],
                    confidence_score=r["confidence_score"],
                    status=r["status"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
            )
        return lessons

    def get_lesson_by_topic(self, topic: str, project_id: str | None = None) -> LessonLearned | None:
        query = "SELECT * FROM lessons_learned WHERE topic = ? AND (project_id = ? OR (project_id IS NULL AND ? IS NULL)) LIMIT 1;"
        r = db.fetch_one(query, (topic, project_id, project_id))
        if not r:
            return None
        return LessonLearned(
            id=r["id"],
            scope=r["scope"],
            project_id=r["project_id"],
            topic=r["topic"],
            problem_statement=r["problem_statement"],
            solution_applied=r["solution_applied"],
            prevention_rule=r["prevention_rule"],
            confidence_score=r["confidence_score"],
            status=r["status"],
            created_at=datetime.fromisoformat(r["created_at"]),
        )

    def save_lesson(self, lesson: LessonLearned) -> LessonLearned:
        existing = self.get_lesson_by_topic(lesson.topic, lesson.project_id)
        if existing:
            db.execute(
                """
                UPDATE lessons_learned
                SET problem_statement = ?, solution_applied = ?, prevention_rule = ?, confidence_score = ?, status = ?
                WHERE id = ?;
                """,
                (
                    lesson.problem_statement,
                    lesson.solution_applied,
                    lesson.prevention_rule,
                    lesson.confidence_score,
                    lesson.status,
                    existing.id,
                ),
            )
            lesson.id = existing.id
            return lesson

        db.execute(
            """
            INSERT INTO lessons_learned (id, scope, project_id, topic, problem_statement, solution_applied, prevention_rule, confidence_score, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                lesson.id,
                lesson.scope,
                lesson.project_id,
                lesson.topic,
                lesson.problem_statement,
                lesson.solution_applied,
                lesson.prevention_rule,
                lesson.confidence_score,
                lesson.status,
                lesson.created_at.isoformat(),
            ),
        )
        return lesson

    def delete_lesson(self, lesson_id: str) -> bool:
        res = db.execute("DELETE FROM lessons_learned WHERE id = ?;", (lesson_id,))
        return res.rowcount > 0


class OpenRouterModelsRepository:
    """Gestionnaire de persistance pour l'intégralité du catalogue OpenRouter (400+ modèles) en SQLite WAL."""

    def __init__(self) -> None:
        self.ensure_seeded()

    def ensure_seeded(self) -> None:
        """Initialise le catalogue complet de tous les modèles dans SQLite."""
        catalog_file = settings.data_dir / "openrouter_models_catalog.json"
        if catalog_file.exists():
            try:
                data = json.loads(catalog_file.read_text(encoding="utf-8"))
                formatted = []
                for m in data:
                    mid = m.get("id", "")
                    if not mid:
                        continue
                    pricing = m.get("pricing")
                    if isinstance(pricing, dict):
                        raw_pin = float(pricing.get("prompt", 0.0) or 0.0)
                        raw_pout = float(pricing.get("completion", 0.0) or 0.0)
                        raw_pcache = float(pricing.get("input_cache_read", pricing.get("cache_read", 0.0)) or 0.0)
                        pin = raw_pin * 1_000_000 if raw_pin < 100.0 else raw_pin
                        pout = raw_pout * 1_000_000 if raw_pout < 100.0 else raw_pout
                        pcache = raw_pcache * 1_000_000 if raw_pcache < 100.0 else raw_pcache
                    else:
                        pin = float(m.get("pin", 0.0) or 0.0)
                        pout = float(m.get("pout", 0.0) or 0.0)
                        pcache = float(m.get("pcache", 0.0) or 0.0)

                    params = m.get("supported_parameters", []) or []
                    arch = m.get("architecture", {}) or {}
                    raw_reasoning = m.get("reasoning", {}) or {}
                    reasoning_meta = extract_reasoning_metadata(raw_reasoning)
                    formatted.append({
                        "id": mid,
                        "name": m.get("name") or mid,
                        "description": m.get("description", ""),
                        "context_length": int(m.get("context_length", 128000) or 128000),
                        "pin": round(pin, 4),
                        "pout": round(pout, 4),
                        "pcache": round(pcache, 4),
                        "reasoning": reasoning_meta,
                        "reasoning_raw": raw_reasoning,
                        "supported_parameters": params,
                        "architecture": arch,
                        "top_provider": m.get("top_provider", {}),
                    })
                self.save_models(formatted)
            except Exception as e:
                logger.warning("Erreur seeding catalogue complet des modèles : %s", e)

    def list_all(self, q: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM openrouter_models_cache"
        params: list[Any] = []
        if q:
            query += " WHERE id LIKE ? OR name LIKE ? OR description LIKE ?"
            like_p = f"%{q}%"
            params.extend([like_p, like_p, like_p])
        query += " ORDER BY id ASC;"
        rows = db.fetch_all(query, params)
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "context_length": r["context_length"],
                "pin": r["price_in_usd"],
                "pout": r["price_out_usd"],
                "pcache": r["price_cache_usd"],
                "reasoning": extract_reasoning_metadata(
                    json.loads(r["reasoning_json"]) if "reasoning_json" in r.keys() and r["reasoning_json"] else {}
                ),
                "supported_parameters": json.loads(r["supported_parameters_json"]),
                "architecture": json.loads(r["architecture_json"]),
                "top_provider": json.loads(r["top_provider_json"]),
            }
            for r in rows
        ]

    def list_vision_models(self, q: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Retourne la liste 100% dynamique des modèles supportant la vision/image."""
        query = """
            SELECT * FROM openrouter_models_cache
            WHERE (
                json_extract(architecture_json, '$.modality') LIKE '%image%'
                OR json_extract(architecture_json, '$.input_modalities') LIKE '%image%'
            )
        """
        params: list[Any] = []
        if q:
            query += " AND (id LIKE ? OR name LIKE ? OR description LIKE ?)"
            like_p = f"%{q}%"
            params.extend([like_p, like_p, like_p])
        query += " ORDER BY price_out_usd ASC, id ASC LIMIT ?;"
        params.append(limit)

        rows = db.fetch_all(query, params)
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "context_length": r["context_length"],
                "pin": r["price_in_usd"],
                "pout": r["price_out_usd"],
                "pcache": r["price_cache_usd"],
                "is_vision": True,
                "reasoning": extract_reasoning_metadata(
                    json.loads(r["reasoning_json"]) if "reasoning_json" in r.keys() and r["reasoning_json"] else {}
                ),
                "supported_parameters": json.loads(r["supported_parameters_json"]),
                "architecture": json.loads(r["architecture_json"]),
                "top_provider": json.loads(r["top_provider_json"]),
            }
            for r in rows
        ]

    def get(self, model_id: str) -> dict[str, Any] | None:
        row = db.fetch_one("SELECT * FROM openrouter_models_cache WHERE id = ? COLLATE NOCASE;", (model_id,))
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "context_length": row["context_length"],
            "pin": row["price_in_usd"],
            "pout": row["price_out_usd"],
            "pcache": row["price_cache_usd"],
            "reasoning": extract_reasoning_metadata(
                json.loads(row["reasoning_json"]) if "reasoning_json" in row.keys() and row["reasoning_json"] else {}
            ),
            "supported_parameters": json.loads(row["supported_parameters_json"]),
            "architecture": json.loads(row["architecture_json"]),
            "top_provider": json.loads(row["top_provider_json"]),
        }

    def save_models(self, models: list[dict[str, Any]]) -> None:
        now_str = utc_now().isoformat()
        records = []
        for m in models:
            mid = m.get("id")
            if not mid:
                continue
            
            raw_reasoning = m.get("reasoning_raw") or m.get("reasoning") or {}
            reasoning_meta = extract_reasoning_metadata(raw_reasoning if isinstance(raw_reasoning, dict) else {})

            records.append((
                mid,
                m.get("name") or mid,
                m.get("description", ""),
                int(m.get("context_length", 128000) or 128000),
                float(m.get("pin", 0.0) or 0.0),
                float(m.get("pout", 0.0) or 0.0),
                float(m.get("pcache", 0.0) or 0.0),
                1 if reasoning_meta["has_reasoning"] else 0,
                json.dumps(raw_reasoning if isinstance(raw_reasoning, dict) else {}),
                "none",
                json.dumps(reasoning_meta["supported_efforts"]),
                json.dumps(m.get("supported_parameters", []) or []),
                json.dumps(m.get("architecture", {}) or {}),
                json.dumps(m.get("top_provider", {}) or {}),
                now_str,
            ))
        if records:
            with db.transaction():
                db.executemany(
                    """
                    INSERT INTO openrouter_models_cache (id, name, description, context_length, price_in_usd, price_out_usd, price_cache_usd, reasoning, reasoning_json, reasoning_type, reasoning_options_json, supported_parameters_json, architecture_json, top_provider_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        context_length = excluded.context_length,
                        price_in_usd = excluded.price_in_usd,
                        price_out_usd = excluded.price_out_usd,
                        price_cache_usd = excluded.price_cache_usd,
                        reasoning = excluded.reasoning,
                        reasoning_json = excluded.reasoning_json,
                        reasoning_type = excluded.reasoning_type,
                        reasoning_options_json = excluded.reasoning_options_json,
                        supported_parameters_json = excluded.supported_parameters_json,
                        architecture_json = excluded.architecture_json,
                        top_provider_json = excluded.top_provider_json,
                        updated_at = excluded.updated_at;
                    """,
                    records,
                )


class ProposalRepository:
    """Gestionnaire de persistance des propositions et recommandations proactives."""

    def _row_to_proposal(self, r: dict[str, Any]) -> ActionProposal:
        return ActionProposal(
            id=r["id"],
            project_id=r.get("project_id"),
            proposal_type=ProposalType(r["proposal_type"]),
            title=r["title"],
            description=r["description"],
            benefit=r.get("benefit", "") or "",
            payload=json.loads(r["payload_json"]),
            status=ProposalStatus(r["status"]),
            created_at=datetime.fromisoformat(r["created_at"]),
            resolved_at=datetime.fromisoformat(r["resolved_at"]) if r.get("resolved_at") else None,
        )

    def create(self, proposal: ActionProposal) -> ActionProposal:
        db.execute(
            """
            INSERT INTO proposals (id, project_id, proposal_type, title, description, benefit, payload_json, status, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                proposal.id,
                proposal.project_id,
                proposal.proposal_type.value,
                proposal.title,
                proposal.description,
                proposal.benefit,
                json.dumps(proposal.payload),
                proposal.status.value,
                proposal.created_at.isoformat(),
                proposal.resolved_at.isoformat() if proposal.resolved_at else None,
            ),
        )
        return proposal

    def get(self, proposal_id: str) -> ActionProposal | None:
        row = db.fetch_one("SELECT * FROM proposals WHERE id = ?;", (proposal_id,))
        if not row:
            return None
        return self._row_to_proposal(row)

    def list_by_project(self, project_id: str | None = None, status: str | None = None) -> list[ActionProposal]:
        query = "SELECT * FROM proposals WHERE 1=1"
        params: list[Any] = []
        if project_id is not None:
            query += " AND project_id = ?"
            params.append(project_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC;"
        rows = db.fetch_all(query, tuple(params))
        return [self._row_to_proposal(r) for r in rows]

    def update_status(self, proposal_id: str, status: ProposalStatus) -> ActionProposal | None:
        proposal = self.get(proposal_id)
        if not proposal:
            return None
        now_str = utc_now().isoformat()
        db.execute(
            "UPDATE proposals SET status = ?, resolved_at = ? WHERE id = ?;",
            (status.value, now_str, proposal_id),
        )
        return self.get(proposal_id)


class SettingsRepository:
    """Gestionnaire de persistance des paramètres système dynamiques dans SQLite."""

    def get(self, key: str) -> str | None:
        row = db.fetch_one("SELECT value FROM system_settings WHERE key = ?;", (key,))
        return row["value"] if row else None

    def get_all(self) -> dict[str, str]:
        rows = db.fetch_all("SELECT key, value FROM system_settings;")
        return {r["key"]: r["value"] for r in rows}

    def set(self, key: str, value: str | None) -> None:
        now_str = utc_now().isoformat()
        if value is None:
            db.execute("DELETE FROM system_settings WHERE key = ?;", (key,))
        else:
            db.execute(
                "INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;",
                (key, value, now_str),
            )


# Singletons de stockage SQLite
project_repo = ProjectRepository()
agent_repo = AgentRepository()
agent_links_repo = AgentLinksRepository()
proposals_repo = ProposalRepository()
finops_repo = FinOpsRepository()
benchmarks_repo = BenchmarksRepository()
aa_benchmarks_repo = benchmarks_repo
mcp_repo = McpRepository()
skills_repo = SkillsRepository()
rules_repo = RulesRepository()
hooks_repo = HooksRepository()
commands_repo = CommandsRepository()
hitl_repo = HitlRepository()
checkpoints_repo = CheckpointsRepository()
lessons_repo = LessonsLearnedRepository()
openrouter_models_repo = OpenRouterModelsRepository()
settings_repo = SettingsRepository()

# Auto-découverte et synchronisation des projets disque
project_repo.auto_sync_disk_projects()
