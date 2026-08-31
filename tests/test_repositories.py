from __future__ import annotations

import pytest
from core.domain import (
    AgentType,
    BenchmarkRecord,
    CheckpointData,
    DocumentAttachment,
    FinOpsBadge,
    FinOpsMetric,
    HitlRequest,
    HitlRequestStatus,
    LessonLearned,
    MessageRole,
    Project,
    SystemCopilotMessage,
    Thread,
)
from storage.repository import (
    agent_repo,
    benchmarks_repo,
    checkpoints_repo,
    finops_repo,
    hitl_repo,
    lessons_repo,
    project_repo,
)


def test_core_six_agents_seeding():
    """Vérifie que les 6 Meta-Agents officiels sont bien créés dans SQLite."""
    agents = agent_repo.list_all()
    assert len(agents) >= 6

    architect = agent_repo.get("agent_architect")
    assert architect is not None
    assert architect.agent_type == AgentType.ARCHITECT
    assert architect.is_core_meta_agent is True

    coder = agent_repo.get("agent_coder")
    assert coder is not None
    assert coder.agent_type == AgentType.CODER

    qa = agent_repo.get("agent_quality_judge")
    assert qa is not None
    assert qa.agent_type == AgentType.QUALITY_JUDGE

    finops = agent_repo.get("agent_finops_guardian")
    assert finops is not None
    assert finops.agent_type == AgentType.FINOPS_GUARDIAN

    copilot = agent_repo.get("agent_copilot")
    assert copilot is not None
    assert copilot.agent_type == AgentType.COPILOT

    model_matcher = agent_repo.get("agent_model_matcher")
    assert model_matcher is not None
    assert model_matcher.agent_type == AgentType.MODEL_MATCHER
    assert model_matcher.is_core_meta_agent is True


def test_project_and_threads_sqlite_crud():
    """Vérifie les opérations CRUD complètes sur les projets et les discussions étanches."""
    # 1. Créer un projet
    project = Project(name="CRM Multi-Agents v5", target_path="")
    saved = project_repo.save(project)
    assert saved.id == project.id

    # 2. Récupérer le projet
    fetched = project_repo.get(project.id)
    assert fetched is not None
    assert fetched.name == "CRM Multi-Agents v5"

    # 3. Créer un Thread et des Messages
    thread = Thread(project_id=str(project.id), title="Architecture & API")
    thread.add_message(
        role=MessageRole.USER,
        content="Comment structurer les endpoints ?",
        author_name="User",
    )
    thread.add_message(
        role=MessageRole.ASSISTANT,
        content="Utilisons FastAPI et Pydantic v2.",
        author_name="Architecte",
        agent_id="agent_architect",
    )
    project_repo.save_thread(thread)

    # 4. Vérifier la lecture des messages
    messages = project_repo.get_thread_messages(thread.id)
    assert len(messages) == 2
    assert messages[0].content == "Comment structurer les endpoints ?"
    assert messages[1].agent_id == "agent_architect"

    # 5. Supprimer
    assert project_repo.delete(project.id) is True
    assert project_repo.get(project.id) is None


def test_project_documents_persistence_and_retrieval():
    """FAIL-01 : Vérifie que project.documents et generated_files sont persistés et rechargés depuis SQLite."""
    # 1. Créer un projet avec des documents attachés
    doc1 = DocumentAttachment(
        filename="cahier_des_charges.md",
        raw_content="# Spécifications\nSystème de trading haute fréquence.",
        content_type="text/markdown",
    )
    doc2 = DocumentAttachment(
        filename="architecture.json",
        raw_content='{"microservices": ["gateway", "auth", "orders"]}',
        content_type="application/json",
    )
    project = Project(
        name="Trading Platform v5",
        target_path="",
        documents=[doc1, doc2],
        generated_files=["src/main.py", "tests/test_main.py"],
    )
    saved = project_repo.save(project)
    assert len(saved.documents) == 2
    assert len(saved.generated_files) == 2

    # 2. Recharger depuis SQLite via get()
    fetched = project_repo.get(project.id)
    assert fetched is not None
    assert len(fetched.documents) == 2
    assert fetched.documents[0].filename == "cahier_des_charges.md"
    assert "trading" in fetched.documents[0].raw_content
    assert fetched.documents[1].filename == "architecture.json"
    assert len(fetched.generated_files) == 2
    assert "src/main.py" in fetched.generated_files

    # 3. Vérifier via list_all()
    all_projects = project_repo.list_all()
    target = next((p for p in all_projects if p.id == project.id), None)
    assert target is not None
    assert len(target.documents) == 2
    assert len(target.generated_files) == 2

    # Nettoyage
    project_repo.delete(project.id)


def test_project_soft_delete_and_restoration_lifecycle():
    """Vérifie le cycle complet Soft Delete (archivage), filtrage et Restauration d'un projet."""
    # 1. Création d'un projet
    proj = Project(name="Projet Audit FinOps", target_path="")
    saved = project_repo.save(proj)
    assert saved.is_archived is False
    assert saved.deleted_at is None

    # 2. Vérifier présence dans list_all(include_archived=False)
    active_projects = project_repo.list_all(include_archived=False)
    assert any(p.id == saved.id for p in active_projects)

    # 3. Soft Delete / Archivage
    archived = project_repo.archive(saved.id)
    assert archived is True

    # 4. Vérifier qu'il n'apparaît plus dans la liste active mais est dans include_archived=True
    active_after = project_repo.list_all(include_archived=False)
    assert not any(p.id == saved.id for p in active_after)

    all_including_archived = project_repo.list_all(include_archived=True)
    archived_match = next((p for p in all_including_archived if p.id == saved.id), None)
    assert archived_match is not None
    assert archived_match.is_archived is True
    assert archived_match.deleted_at is not None

    # 5. Restauration
    restored = project_repo.restore(saved.id)
    assert restored is True

    # 6. Vérifier réapparition dans les projets actifs
    active_restored = project_repo.list_all(include_archived=False)
    restored_match = next((p for p in active_restored if p.id == saved.id), None)
    assert restored_match is not None
    assert restored_match.is_archived is False
    assert restored_match.deleted_at is None

    # 7. Nettoyage (Purge définitive)
    project_repo.delete(saved.id)


def test_system_copilot_messages_isolation():
    """Vérifie que les messages du Copilote Système sont étanches et séparés des projets."""
    msg = SystemCopilotMessage(
        role=MessageRole.USER,
        content="Configure l'agent Développeur sur Qwen 2.5 Coder",
        author_name="Admin",
    )
    project_repo.add_system_copilot_message(msg)

    copilot_msgs = project_repo.list_system_copilot_messages()
    assert len(copilot_msgs) > 0
    assert any(m.content == msg.content for m in copilot_msgs)


def test_finops_ledger_and_benchmarks_cache():
    """Vérifie l'enregistrement dans le grand livre FinOps et le cache des 19 benchmarks."""
    metric = FinOpsMetric(
        agent_id="agent_coder",
        agent_name="Développeur Logiciel",
        model="qwen/qwen-2.5-coder-32b-instruct",
        prompt_tokens=250,
        completion_tokens=500,
        reasoning_tokens=100,
        total_tokens=850,
        cost_usd=0.00035,
        latency_ms=350,
    )
    finops_repo.record_inference(metric)

    all_metrics = finops_repo.list_all()
    assert len(all_metrics) > 0
    assert any(m.id == metric.id for m in all_metrics)

    # Benchmarks
    b_rec = BenchmarkRecord(
        model_id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet",
        creator="Anthropic",
        quality_index=95.0,
        coding_score=93.7,
        reasoning_score=78.3,
        speed_tok_s=85.0,
        price_in_usd=3.00,
        price_out_usd=15.00,
        badge=FinOpsBadge.TOP_PERFORMANCE,
        evaluations={"terminal_bench_v2_1": 89.0, "scicode": 56.0, "gpqa_diamond": 93.0},
    )
    benchmarks_repo.save_benchmarks([b_rec])
    cached = benchmarks_repo.get_cached_benchmarks()
    assert len(cached) > 0
    assert any(b.model_id == b_rec.model_id for b in cached)


def test_hitl_checkpoints_and_lessons_repositories():
    """Vérifie les tables HITL, Checkpoints Time Travel et Leçons Apprises."""
    # HITL Request
    hitl_req = HitlRequest(
        project_id="proj_123",
        agent_id="agent_quality_judge",
        request_type="new_skill",
        title="Proposition de Playbook FastApi",
        description="Création automatique du playbook suite au run.",
    )
    hitl_repo.save_request(hitl_req)
    pending = hitl_repo.list_requests(status=HitlRequestStatus.PENDING)
    assert any(r.id == hitl_req.id for r in pending)

    resolved = hitl_repo.resolve_request(hitl_req.id, HitlRequestStatus.APPROVED)
    assert resolved is not None
    assert resolved.status == HitlRequestStatus.APPROVED

    # Checkpoints Time Travel
    proj = Project(name="Checkpoint Project")
    project_repo.save(proj)

    checkpoint = CheckpointData(
        project_id=str(proj.id),
        step_name="architecture_validation",
        state_payload={"status": "architecture_approved"},
        files_snapshot={"main.py": "print('hello v5')"},
    )
    checkpoints_repo.save_checkpoint(checkpoint)
    latest = checkpoints_repo.get_latest_checkpoint(str(proj.id))
    assert latest is not None
    assert latest.step_name == "architecture_validation"
    assert "main.py" in latest.files_snapshot

    # Leçons Apprises
    lesson = LessonLearned(
        topic="SQLite Concurrency",
        problem_statement="Database locked on concurrent writes",
        solution_applied="Configured PRAGMA journal_mode=WAL and PRAGMA busy_timeout=5000",
        prevention_rule="Always use WAL mode in SQLite for multi-agent workloads",
    )
    lessons_repo.save_lesson(lesson)
    lessons = lessons_repo.list_lessons("SQLite")
    assert len(lessons) > 0
