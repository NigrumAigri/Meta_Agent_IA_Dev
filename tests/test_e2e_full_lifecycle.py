from __future__ import annotations

import io
import zipfile
import pytest
from fastapi.testclient import TestClient

from api.app import app
from core.domain import TopologyMode
from storage.repository import project_repo

client = TestClient(app)


def test_e2e_full_lifecycle_enterprise_project():
    """Test End-to-End complet du cycle de vie d'un projet Enterprise v5.0.0.

    1. Création de projet
    2. Ingestion du cahier des charges
    3. Cadrage adaptatif Inception avec l'Architecte
    4. Basculement de topologie multi-agents
    5. Validation syntaxique AST en mémoire
    6. Évaluation du Score Qualité /100 par le Contrôleur Qualité
    7. Vérification de la télémétrie FinOps
    8. Capture de checkpoint Time Travel
    9. Exportation et intégrité de l'archive ZIP
    """
    # --------------------------------------------------------------------------
    # 1. Création du projet dans SQLite WAL
    # --------------------------------------------------------------------------
    res_create = client.post(
        "/api/v1/projects",
        json={
            "name": "FinTech Payment Gateway Enterprise",
            "budget_limit_usd": 25.0,
            "selected_finops_profile": "sweet_spot",
        },
    )
    assert res_create.status_code == 201
    project_data = res_create.json()
    project_id = project_data["id"]
    assert project_data["name"] == "FinTech Payment Gateway Enterprise"

    # --------------------------------------------------------------------------
    # 2. Ingestion du cahier des charges et spécifications techniques
    # --------------------------------------------------------------------------
    specs_content = """# Spécifications Passerelle de Paiement
    - API REST FastAPI avec validation stricte Pydantic v2
    - Mode SQLite WAL pour la persistance des transactions
    - Traitement asynchrone des webhooks bancaires
    """
    res_doc = client.post(
        f"/api/v1/projects/{project_id}/documents",
        json={
            "filename": "cahier_des_charges_paiement.md",
            "content": specs_content,
            "content_type": "text/markdown",
        },
    )
    assert res_doc.status_code == 201

    # --------------------------------------------------------------------------
    # 3. Cadrage Inception adaptatif avec l'Architecte
    # --------------------------------------------------------------------------
    res_chat = client.post(
        "/api/v1/chat/message",
        json={
            "project_id": project_id,
            "message": "Bonjour Architecte, propose l'architecture complète de la passerelle de paiement.",
        },
    )
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    assert chat_data["status"] == "success"
    assert "reply" in chat_data

    # --------------------------------------------------------------------------
    # 4. Basculement de la Topologie Multi-Agents (Consensus Debate)
    # --------------------------------------------------------------------------
    res_topo = client.post(
        "/api/v1/agents/topology",
        json={"topology": TopologyMode.CONSENSUS_DEBATE.value},
    )
    assert res_topo.status_code == 200
    assert res_topo.json()["topology"] == "consensus_debate"

    # --------------------------------------------------------------------------
    # 5. Validation syntaxique AST par le MCP Hub
    # --------------------------------------------------------------------------
    python_code = """from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="Payment Gateway")

class PaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: float
    currency: str

@app.post("/api/v1/payments")
def process_payment(payload: PaymentRequest):
    try:
        return {"status": "authorized", "amount": payload.amount, "currency": payload.currency}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""
    res_ast = client.post(
        "/api/v1/mcp/tools/ast_validator/execute",
        json={"arguments": {"code_content": python_code, "filename": "src/payments.py"}},
    )
    assert res_ast.status_code == 200
    assert res_ast.json()["is_valid"] is True

    # --------------------------------------------------------------------------
    # 6. Évaluation du Score Qualité /100 par le Contrôleur Qualité
    # --------------------------------------------------------------------------
    from services.quality_judge import quality_judge
    proj_obj = project_repo.get(project_id)
    assert proj_obj is not None

    score_matrix = quality_judge.evaluate_project(
        proj_obj,
        files={
            "src/main.py": python_code,
            "tests/test_payments.py": "def test_payment(): assert True\n",
            "README.md": "# Payment Gateway Documentation\n",
        },
    )
    assert score_matrix.total_score >= 85.0
    assert score_matrix.verdict == "SUCCÈS"

    # --------------------------------------------------------------------------
    # 7. Vérification de la télémétrie FinOps
    # --------------------------------------------------------------------------
    res_finops = client.get("/api/v1/finops/ledger")
    assert res_finops.status_code == 200
    ledger_entries = res_finops.json()
    assert len(ledger_entries) > 0

    # --------------------------------------------------------------------------
    # 8. Capture de Checkpoint Time Travel
    # --------------------------------------------------------------------------
    from services.time_travel import time_travel
    checkpoint = time_travel.create_checkpoint(
        project_id=project_id,
        step_name="architecture_et_code_valides",
        files_snapshot={"src/main.py": python_code},
    )
    assert checkpoint.id is not None

    res_ckpts = client.get(f"/api/v1/projects/{project_id}/checkpoints")
    assert res_ckpts.status_code == 200
    assert len(res_ckpts.json()) >= 1

    # --------------------------------------------------------------------------
    # 9. Exportation et intégrité de l'archive ZIP
    # --------------------------------------------------------------------------
    res_zip = client.get(f"/api/v1/projects/{project_id}/export/zip")
    assert res_zip.status_code == 200
    assert res_zip.headers["content-type"] == "application/zip"

    # Vérification que le ZIP est bien lisible
    with zipfile.ZipFile(io.BytesIO(res_zip.content), "r") as z:
        namelist = z.namelist()
        assert any("main.py" in n for n in namelist)
        assert any("README.md" in n for n in namelist)
