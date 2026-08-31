from __future__ import annotations

import re
import pytest
from fastapi.testclient import TestClient

from api.app import app
from core.domain import AgentDefinition, AgentLink, LinkType, Project
from storage.repository import agent_links_repo, agent_repo, project_repo

client = TestClient(app)

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]",
    flags=re.UNICODE,
)


def has_no_emojis(text: str) -> bool:
    return not bool(EMOJI_PATTERN.search(text))


@pytest.fixture
def clean_project():
    p = Project(name="Projet Test Hermetique", target_path="")
    saved = project_repo.save(p)

    # 2 agents dedies
    ag1 = AgentDefinition(
        id=f"ag_dev_{str(saved.id)[:6]}",
        name=f"Dev {saved.name}",
        project_id=str(saved.id),
        role="Developpeur",
        model="qwen/qwen-2.5-coder-32b-instruct",
        is_active=True,
    )
    ag2 = AgentDefinition(
        id=f"ag_qa_{str(saved.id)[:6]}",
        name=f"QA {saved.name}",
        project_id=str(saved.id),
        role="Controleur Qualite",
        model="moonshotai/kimi-k3",
        is_active=True,
    )
    agent_repo.save(ag1)
    agent_repo.save(ag2)

    # Liaison
    link = AgentLink(
        project_id=str(saved.id),
        source_agent_id=ag1.id,
        target_agent_id=ag2.id,
        link_type=LinkType.DIRECT,
        label=f"{ag1.name} -> {ag2.name}",
        is_active=True,
    )
    agent_links_repo.save(link)

    yield saved


def test_api_multi_agent_pipeline_hermetic_execution(clean_project: Project):
    payload = {
        "project_id": str(clean_project.id),
        "instruction": "Construire et valider le module de paiement",
        "topology": "custom_dag",
    }
    response = client.post("/api/v1/chat/multi-agent", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["project_id"] == str(clean_project.id)
    assert "quality_score" in data
    assert len(data["steps_log"]) >= 1

    # Verifier l'absence d'emojis
    assert has_no_emojis(data["summary"])
    for step in data["steps_log"]:
        assert has_no_emojis(step)

    # Verifier le thread de discussion du projet
    messages = project_repo.get_thread_messages(f"thread_{str(clean_project.id)[:8]}_main")
    last_msg = messages[-1]
    assert "Pipeline Multi-Agents" in last_msg.content
    assert has_no_emojis(last_msg.content)


def test_api_multi_agent_pipeline_studio_scope():
    payload = {
        "project_id": None,
        "instruction": "Validation globale du Studio",
        "topology": "custom_dag",
    }
    response = client.post("/api/v1/chat/multi-agent", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert has_no_emojis(data["summary"])


def test_api_multi_agent_pipeline_not_found():
    from uuid import uuid4
    fake_id = str(uuid4())
    payload = {
        "project_id": fake_id,
        "instruction": "Test",
    }
    response = client.post("/api/v1/chat/multi-agent", json=payload)
    assert response.status_code == 404


def test_hermetic_isolation_between_two_projects():
    p1 = project_repo.save(Project(name="Projet Alpha Test", target_path=""))
    p2 = project_repo.save(Project(name="Projet Beta Test", target_path=""))

    # Lancer sur p1
    res1 = client.post("/api/v1/chat/multi-agent", json={"project_id": str(p1.id)})
    assert res1.status_code == 200

    # Verifier que p2 n'a pas recu le message de p1
    p2_messages = project_repo.get_thread_messages(f"thread_{str(p2.id)[:8]}_main")
    assert not any(p1.name in m.content for m in p2_messages)
