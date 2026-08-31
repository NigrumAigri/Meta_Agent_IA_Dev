from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app
from storage.repository import agent_links_repo, agent_repo

client = TestClient(app)


def test_project_scaffolds_dedicated_team():
    """Vérifie que la création d'un projet instancie une équipe dédiée et non les 5 Méta-Agents génériques."""
    res = client.post(
        "/api/v1/projects",
        json={"name": "Fintech Ledger App", "budget_limit_usd": 15.0},
    )
    assert res.status_code == 201
    proj_id = res.json()["id"]

    # 1. Vérifier les agents spécifiques du projet
    agents = agent_repo.list_all(project_id=proj_id)
    assert len(agents) == 2
    assert any("Développeur" in a.name for a in agents)
    assert any("Contrôleur Qualité" in a.name for a in agents)

    # 2. Vérifier le câble initial entre eux
    links = agent_links_repo.list_all(project_id=proj_id)
    assert len(links) == 1
    assert links[0].link_type.value == "debate"

    # 3. Vérifier que le Studio a toujours ses 6 Core Meta-Agents intacts
    studio_agents = agent_repo.get_core_meta_agents()
    assert len(studio_agents) == 6


def test_chat_natural_language_canvas_control():
    """Vérifie que parler dans le chat permet de créer des agents et câbles en direct."""
    res_p = client.post("/api/v1/projects", json={"name": "E-Commerce App"})
    proj_id = res_p.json()["id"]

    # 1. Commande Chat en langage naturel : ajouter un agent
    res_chat = client.post(
        "/api/v1/chat/message",
        json={
            "project_id": proj_id,
            "message": "Ajoute un agent de paiement Stripe pour gérer les abonnements",
        },
    )
    assert res_chat.status_code == 200
    data = res_chat.json()
    assert data["canvas_updated"] is True
    assert len(data["actions_executed"]) >= 1
    assert any(a["type"] == "create_agent" for a in data["actions_executed"])

    # 2. Vérifier que l'agent est bien présent sur le projet
    agents = agent_repo.list_all(project_id=proj_id)
    assert len(agents) == 3
    assert any("Paiement Stripe" in a.name for a in agents)
