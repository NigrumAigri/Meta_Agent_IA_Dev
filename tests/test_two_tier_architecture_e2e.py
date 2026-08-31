from __future__ import annotations

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


def test_two_tier_architecture_full_scenario():
    """Scénario de bout en bout validant l'architecture 2-Tier :
    - Studio Méta-Agent (Collectif des Méta-Agents Core protégés)
    - Projets Isolés avec équipes dédiées
    - Contrôle bi-directionnel Chat ➔ Canvas
    - Propositions d'actions proactives en 1-clic
    """

    # 1. Vérification du Studio Méta-Agent
    res_studio = client.get("/api/v1/agents?project_id=studio")
    assert res_studio.status_code == 200
    studio_agents = res_studio.json()
    assert len(studio_agents) >= 1
    assert all(a["is_core_meta_agent"] for a in studio_agents)

    # 2. Création de deux projets distincts
    res_p1 = client.post("/api/v1/projects", json={"name": "Projet FinTech Alpha"})
    assert res_p1.status_code == 201
    pid1 = res_p1.json()["id"]

    res_p2 = client.post("/api/v1/projects", json={"name": "Projet HealthTech Beta"})
    assert res_p2.status_code == 201
    pid2 = res_p2.json()["id"]

    # 3. Vérification de l'isolation étanche des équipes dédiées
    agents_p1 = client.get(f"/api/v1/agents?project_id={pid1}").json()
    agents_p2 = client.get(f"/api/v1/agents?project_id={pid2}").json()

    assert len(agents_p1) == 2
    assert len(agents_p2) == 2
    p1_ids = {a["id"] for a in agents_p1}
    p2_ids = {a["id"] for a in agents_p2}
    assert p1_ids.isdisjoint(p2_ids)

    # 4. Contrôle bi-directionnel depuis le Chat du Projet 1 (ajout d'agent)
    res_chat = client.post(
        "/api/v1/chat/message",
        json={
            "project_id": pid1,
            "message": "Ajoute un agent de conformité bancaire pour auditer les flux SEPA",
        },
    )
    assert res_chat.status_code == 200
    assert res_chat.json()["canvas_updated"] is True

    # Vérifier que l'agent a été ajouté uniquement sur le Projet 1
    updated_p1 = client.get(f"/api/v1/agents?project_id={pid1}").json()
    updated_p2 = client.get(f"/api/v1/agents?project_id={pid2}").json()
    assert len(updated_p1) == 3
    assert len(updated_p2) == 2

    # 5. Câblage via Chat sur le Projet 1
    new_agent_id = next(a["id"] for a in updated_p1 if "Conformité" in a["name"] or "bancaire" in a["name"].lower())
    target_dev_id = next(a["id"] for a in updated_p1 if "Développeur" in a["name"])

    res_link_chat = client.post(
        "/api/v1/chat/message",
        json={
            "project_id": pid1,
            "message": f"Connecte {new_agent_id} vers {target_dev_id} en mode débat",
        },
    )
    assert res_link_chat.status_code == 200
    assert res_link_chat.json()["canvas_updated"] is True

    links_p1 = client.get(f"/api/v1/agents/links?project_id={pid1}").json()
    assert len(links_p1) == 2

    # 6. Proposition proactive émise et acceptée en 1-clic sur le Projet 2
    res_prop = client.post(
        "/api/v1/proposals",
        json={
            "project_id": pid2,
            "proposal_type": "agent",
            "title": "Agent HL7 FHIR Medical Parser",
            "description": "Validation déterministe des dossiers patients",
            "benefit": "+100% interopérabilité santé",
            "payload": {
                "id": f"ag_fhir_{uuid4().hex[:6]}",
                "name": "Agent HL7 FHIR Medical Parser",
                "model": "moonshotai/kimi-k3",
                "connect_to_agent_id": updated_p2[0]["id"],
            },
        },
    )
    assert res_prop.status_code == 201
    prop_id = res_prop.json()["id"]

    # Acceptation
    res_accept = client.post(f"/api/v1/proposals/{prop_id}/accept")
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "applied"

    # Vérification Projet 2 après acceptation
    final_p2_agents = client.get(f"/api/v1/agents?project_id={pid2}").json()
    assert len(final_p2_agents) == 3
    final_p2_links = client.get(f"/api/v1/agents/links?project_id={pid2}").json()
    assert len(final_p2_links) == 2

    # 7. Vérification finale : le collectif Studio est intact et protégé contre les pollutions
    final_studio = client.get("/api/v1/agents?project_id=studio").json()
    assert len(final_studio) == len(studio_agents)
    assert all(a["is_core_meta_agent"] for a in final_studio)
