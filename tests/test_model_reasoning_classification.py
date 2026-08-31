from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app
from core.domain import extract_reasoning_metadata


@pytest.fixture
def client():
    return TestClient(app)


def test_extract_reasoning_metadata_direct():
    """Vérifie l'extraction directe et 100% native des métadonnées reasoning de l'API OpenRouter."""
    # 1. Gemini 3.7 Flash
    raw_gemini = {
        "mandatory": True,
        "default_enabled": True,
        "supported_efforts": ["high", "medium", "low"],
        "default_effort": "medium"
    }
    meta_gemini = extract_reasoning_metadata(raw_gemini)
    assert meta_gemini["has_reasoning"] is True
    assert meta_gemini["supported_efforts"] == ["high", "medium", "low"]
    assert meta_gemini["default_effort"] == "medium"
    assert meta_gemini["mandatory"] is True

    # 2. OpenAI GPT-5.6 Terra Pro
    raw_terra = {
        "mandatory": False,
        "default_enabled": True,
        "supported_efforts": ["max", "xhigh", "high", "medium", "low", "none"],
        "default_effort": "medium"
    }
    meta_terra = extract_reasoning_metadata(raw_terra)
    assert meta_terra["has_reasoning"] is True
    assert meta_terra["supported_efforts"] == ["max", "xhigh", "high", "medium", "low", "none"]

    # 3. Muse Spark
    raw_muse = {
        "mandatory": True,
        "supported_efforts": ["xhigh", "high", "medium", "low", "minimal"],
        "default_effort": "medium"
    }
    meta_muse = extract_reasoning_metadata(raw_muse)
    assert meta_muse["has_reasoning"] is True
    assert meta_muse["supported_efforts"] == ["xhigh", "high", "medium", "low", "minimal"]

    # 4. Modèle standard sans reasoning (ex: GPT-4o)
    meta_std = extract_reasoning_metadata({})
    assert meta_std["has_reasoning"] is False
    assert meta_std["supported_efforts"] == []
    assert meta_std["default_effort"] == "none"


def test_api_models_endpoint_returns_real_openrouter_reasoning(client):
    """Vérifie que l'API /api/v1/finops/models renvoie bien les objets reasoning natifs d'OpenRouter."""
    res = client.get("/api/v1/finops/models")
    assert res.status_code == 200
    models = res.json()
    assert len(models) >= 100

    # Gemini 3.7 Flash
    gemini = next((m for m in models if m["id"] == "google/gemini-3.7-flash"), None)
    if gemini:
        assert gemini["reasoning"]["has_reasoning"] is True
        assert gemini["reasoning"]["supported_efforts"] == ["high", "medium", "low"]

    # GPT-4o
    gpt4o = next((m for m in models if m["id"] == "openai/gpt-4o"), None)
    if gpt4o:
        assert gpt4o["reasoning"]["has_reasoning"] is False
        assert gpt4o["reasoning"]["supported_efforts"] == []


def test_api_get_model_info(client):
    """Vérifie la résolution dynamique d'un modèle via GET /api/v1/finops/models/info."""
    # Modèle avec reasoning
    res_gemini = client.get("/api/v1/finops/models/info?model_id=google/gemini-3.7-flash")
    assert res_gemini.status_code == 200
    data = res_gemini.json()
    assert data["reasoning"]["has_reasoning"] is True
    assert data["reasoning"]["supported_efforts"] == ["high", "medium", "low"]

    # Modèle sans reasoning
    res_std = client.get("/api/v1/finops/models/info?model_id=openai/gpt-4o")
    assert res_std.status_code == 200
    data_std = res_std.json()
    assert data_std["reasoning"]["has_reasoning"] is False
    assert data_std["reasoning"]["supported_efforts"] == []
