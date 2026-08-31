from __future__ import annotations

import asyncio
import pytest
from core.domain import (
    CadrageSynthesis,
    Project,
    ProjectStatus,
    QualityScoreMatrix,
    TopologyMode,
)
from storage.repository import project_repo
from services.blackboard import blackboard
from services.orchestrator import orchestrator


def test_blackboard_shared_state_operations():
    """Vérifie la publication et la lecture de livrables typés dans le Tableau Noir."""
    proj_id = "proj_blackboard_test"

    # 1. Cadrage
    synthesis = CadrageSynthesis(
        project_title="Plateforme E-Commerce",
        summary="Application de vente en ligne",
        technical_stack=["FastAPI", "SQLite WAL", "Pydantic v2"],
    )
    blackboard.update_cadrage(proj_id, synthesis)

    # 2. Publication de fichier
    blackboard.publish_file(proj_id, "src/main.py", "app = FastAPI()")

    # 3. Test results
    blackboard.publish_test_results(proj_id, {"status": "passed", "passed": 12, "failed": 0})

    # 4. Score Qualité
    score = QualityScoreMatrix(
        technical_health=35.0,
        robustness_security=25.0,
        functional_coverage=30.0,
        documentation=10.0,
        total_score=100.0,
        verdict="SUCCÈS",
    )
    blackboard.publish_quality_score(proj_id, score)

    # 5. Export de contexte
    ctx = blackboard.export_context_for_agent(proj_id)
    assert "src/main.py" in ctx
    assert "FastAPI" in ctx
    assert "100.0/100" in ctx


def test_all_5_lego_topologies():
    """Vérifie l'exécution des 5 topologies multi-agents interchangeables."""
    async def runner():
        project = Project(name="Test Topologies", budget_limit_usd=20.0)
        project_repo.save(project)

        # 1. Topologie Séquentielle
        res_seq = await orchestrator.execute_multi_agent_workflow(
            project, "Mission test", topology=TopologyMode.SEQUENTIAL
        )
        assert res_seq["status"] == "success"
        assert res_seq["topology"] == "sequential"

        # 2. Topologie Hiérarchique
        res_hier = await orchestrator.execute_multi_agent_workflow(
            project, "Mission test", topology=TopologyMode.HIERARCHICAL
        )
        assert res_hier["status"] == "success"
        assert res_hier["topology"] == "hierarchical"

        # 3. Topologie Débat & Consensus
        res_debate = await orchestrator.execute_multi_agent_workflow(
            project, "Mission test", topology=TopologyMode.CONSENSUS_DEBATE
        )
        assert res_debate["status"] == "success"
        assert res_debate["topology"] == "consensus_debate"

        # 4. Topologie Essaim (Swarms)
        res_swarm = await orchestrator.execute_multi_agent_workflow(
            project, "Mission test", topology=TopologyMode.SWARM
        )
        assert res_swarm["status"] == "success"
        assert res_swarm["topology"] == "swarm"

        # 5. Topologie Parallèle (Fan-Out / Fan-In)
        res_parallel = await orchestrator.execute_multi_agent_workflow(
            project, "Mission test", topology=TopologyMode.PARALLEL
        )
        assert res_parallel["status"] == "success"
        assert res_parallel["topology"] == "parallel"
        assert len(res_parallel["parallel_tasks"]) == 3

        # 6. Graphe Dynamique (DAG Links réels)
        res_dag = await orchestrator.execute_multi_agent_workflow(
            project, "Mission test", topology=TopologyMode.CUSTOM_DAG
        )
        assert res_dag["status"] == "success"
        assert res_dag["topology"] == "custom_dag"
        assert res_dag["active_links_count"] >= 4
        assert len(res_dag["agents_involved"]) >= 2

    asyncio.run(runner())


def test_agent_links_repository_crud():
    """Vérifie le stockage SQLite des liaisons et l'application des templates."""
    from storage.repository import agent_links_repo
    from core.domain import AgentLink, LinkType

    # 1. Application template
    links = agent_links_repo.apply_template("sequential")
    assert len(links) == 5
    assert links[0].source_agent_id == "agent_architect"
    assert links[0].target_agent_id in ("agent_coder", "agent_model_matcher")
    assert links[0].link_type in (LinkType.DIRECT, LinkType.SPEC_TO_CODE)

    # 2. Création nouveau lien
    custom_link = AgentLink(
        id="link_test_src_tgt",
        source_agent_id="agent_coder",
        target_agent_id="agent_copilot",
        link_type=LinkType.DATA_FLOW,
        label="Pipeline Custom",
    )
    saved = agent_links_repo.create(custom_link)
    assert saved.id == "link_test_src_tgt"

    all_links = agent_links_repo.list_all()
    assert any(l.id == "link_test_src_tgt" for l in all_links)

    # 3. Suppression
    del_ok = agent_links_repo.delete("link_test_src_tgt")
    assert del_ok is True


def test_cadrage_inception_turn():
    """Vérifie le dialogue de cadrage adaptatif sans questionnaire rigide."""
    async def runner():
        project = Project(name="Projet Cadrage Inception", budget_limit_usd=15.0)
        project_repo.save(project)

        updated_p = await orchestrator.run_cadrage_turn(
            project, "Je souhaite créer une API de réservation de salles."
        )

        assert updated_p.status == ProjectStatus.CADRAGE
        thread = updated_p.get_or_create_main_thread()
        assert len(thread.messages) == 2  # 1 User + 1 Assistant

    asyncio.run(runner())
