from __future__ import annotations

from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from core.config import reload_settings, settings

router = APIRouter(prefix="/api/v1/config", tags=["Configuration & Clés API"])


class UpdateConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    llm_provider: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    artificial_analysis_api_key: str | None = None
    llm_discovery_model: str | None = None
    llm_coder_model: str | None = None
    server_port: int | None = None
    ast_validation_enabled: bool | None = None
    hitl_validation_enabled: bool | None = None
    circuit_breaker_enabled: bool | None = None
    prompt_caching_enabled: bool | None = None


def mask_key(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "••••••••"
    return key[:4] + "••••••••" + key[-4:]


@router.get("", response_model=dict[str, Any])
def get_system_config():
    """Récupère l'état actuel de la configuration et des connexions externes avec synchronisation dynamique."""
    cfg = reload_settings()
    llm_key = cfg.get_llm_api_key()
    aa_key = cfg.get_aa_api_key()
    return {
        "llm_provider": cfg.llm_provider,
        "llm_base_url": cfg.llm_base_url,
        "llm_api_key_masked": mask_key(llm_key),
        "is_openrouter_connected": bool(llm_key),
        "artificial_analysis_key_masked": mask_key(aa_key),
        "is_artificial_analysis_live": bool(aa_key),
        "llm_discovery_model": cfg.llm_discovery_model,
        "llm_coder_model": cfg.llm_coder_model,
        "server_port": cfg.server_port,
        "db_path": str(cfg.db_path),
        "ast_validation_enabled": cfg.ast_validation_enabled,
        "hitl_validation_enabled": cfg.hitl_validation_enabled,
        "circuit_breaker_enabled": cfg.circuit_breaker_enabled,
        "prompt_caching_enabled": cfg.prompt_caching_enabled,
    }


@router.put("", response_model=dict[str, Any])
@router.patch("", response_model=dict[str, Any])
def update_system_config(payload: UpdateConfigPayload):
    """Met à jour les paramètres dynamiques dans SQLite sans modifier le fichier .env."""
    from storage.repository import settings_repo

    if payload.llm_provider is not None:
        settings_repo.set("llm_provider", payload.llm_provider)
    if payload.llm_base_url is not None:
        settings_repo.set("llm_base_url", payload.llm_base_url)
    if payload.llm_api_key is not None:
        settings_repo.set("llm_api_key", payload.llm_api_key or None)
    if payload.artificial_analysis_api_key is not None:
        settings_repo.set("artificial_analysis_api_key", payload.artificial_analysis_api_key or None)
    if payload.llm_discovery_model is not None:
        settings_repo.set("llm_discovery_model", payload.llm_discovery_model)
    if payload.llm_coder_model is not None:
        settings_repo.set("llm_coder_model", payload.llm_coder_model)
    if payload.ast_validation_enabled is not None:
        settings_repo.set("ast_validation_enabled", "true" if payload.ast_validation_enabled else "false")
    if payload.hitl_validation_enabled is not None:
        settings_repo.set("hitl_validation_enabled", "true" if payload.hitl_validation_enabled else "false")
    if payload.circuit_breaker_enabled is not None:
        settings_repo.set("circuit_breaker_enabled", "true" if payload.circuit_breaker_enabled else "false")
    if payload.prompt_caching_enabled is not None:
        settings_repo.set("prompt_caching_enabled", "true" if payload.prompt_caching_enabled else "false")

    new_settings = reload_settings()
    return {
        "status": "success",
        "message": "Configuration mise à jour et rechargée avec succès.",
        "config": {
            "llm_provider": new_settings.llm_provider,
            "llm_base_url": new_settings.llm_base_url,
            "is_openrouter_connected": new_settings.is_openrouter_connected,
            "is_artificial_analysis_live": new_settings.is_artificial_analysis_live,
            "llm_discovery_model": new_settings.llm_discovery_model,
            "llm_coder_model": new_settings.llm_coder_model,
            "server_port": new_settings.server_port,
            "ast_validation_enabled": new_settings.ast_validation_enabled,
            "hitl_validation_enabled": new_settings.hitl_validation_enabled,
            "circuit_breaker_enabled": new_settings.circuit_breaker_enabled,
            "prompt_caching_enabled": new_settings.prompt_caching_enabled,
        },
    }


class TestConnectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str | None = None
    openrouter_api_key: str | None = None
    artificial_analysis_api_key: str | None = None
    service: str | None = "all"  # "all", "openrouter", "artificial_analysis"


async def check_openrouter_key(key: str | None) -> dict[str, Any]:
    import time
    import httpx

    target_key = (key.strip() if key and key.strip() else None) or settings.get_llm_api_key()
    if not target_key or target_key.startswith("your_") or len(target_key) < 8:
        return {
            "status": "error",
            "is_connected": False,
            "message": "Aucune clé API renseignée ou clé invalide.",
            "latency_ms": 0,
        }

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {target_key}",
                "HTTP-Referer": "https://meta-agent-v5.internal",
                "X-Title": "Meta Developer Agent v5 Enterprise",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            res = await client.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
            lat_ms = int((time.time() - t0) * 1000)

            if res.status_code == 200:
                data = res.json().get("data", {})
                label = data.get("label") or "Clé Active"
                limit = data.get("limit")
                limit_info = f" · Limite: ${limit}" if limit else ""
                return {
                    "status": "success",
                    "is_connected": True,
                    "message": f"Connectée & Opérationnelle ({label}{limit_info})",
                    "latency_ms": lat_ms,
                    "data": data,
                }
            elif res.status_code == 401:
                return {
                    "status": "error",
                    "is_connected": False,
                    "message": "Clé API non reconnue ou expirée (HTTP 401 Unauthorized).",
                    "latency_ms": lat_ms,
                }
            else:
                res_models = await client.get(f"{settings.llm_base_url}/models", headers=headers)
                lat_ms = int((time.time() - t0) * 1000)
                if res_models.status_code == 200:
                    return {
                        "status": "success",
                        "is_connected": True,
                        "message": "Connectée & Opérationnelle (Catalogue 420+ modèles accessible)",
                        "latency_ms": lat_ms,
                    }
                return {
                    "status": "error",
                    "is_connected": False,
                    "message": f"Échec de connexion (HTTP {res.status_code}).",
                    "latency_ms": lat_ms,
                }
    except Exception as e:
        lat_ms = int((time.time() - t0) * 1000)
        return {
            "status": "error",
            "is_connected": False,
            "message": f"Impossible de joindre OpenRouter : {str(e)[:120]}",
            "latency_ms": lat_ms,
        }


async def check_aa_key(key: str | None) -> dict[str, Any]:
    import time
    import httpx

    target_key = (key.strip() if key and key.strip() else None) or settings.get_aa_api_key()
    if not target_key or target_key.startswith("your_") or len(target_key) < 5:
        return {
            "status": "not_configured",
            "is_connected": False,
            "message": "Clé non renseignée (Optionnelle pour les 19 benchmarks).",
            "latency_ms": 0,
        }

    t0 = time.time()
    try:
        headers = {
            "x-api-key": target_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Tester le endpoint data/llms/models (compatible Free Tier & Pro Tier)
            res = await client.get(
                "https://artificialanalysis.ai/api/v2/data/llms/models",
                headers=headers,
            )
            lat_ms = int((time.time() - t0) * 1000)

            # 2. Si non 200, essayer le endpoint alternatif language/models
            if res.status_code != 200:
                res_alt = await client.get(
                    "https://artificialanalysis.ai/api/v2/language/models",
                    headers=headers,
                )
                if res_alt.status_code == 200:
                    res = res_alt
                    lat_ms = int((time.time() - t0) * 1000)

            err_detail = ""
            try:
                data = res.json()
                if isinstance(data, dict):
                    err_detail = data.get("error") or data.get("message") or data.get("detail") or ""
            except Exception:
                err_detail = res.text[:120] if res.text else ""

            if res.status_code == 200:
                count = 0
                try:
                    data = res.json()
                    models_list = data.get("data") if isinstance(data, dict) else data
                    if isinstance(models_list, list):
                        count = len(models_list)
                except Exception:
                    pass
                count_str = f" ({count} modèles synchronisés)" if count > 0 else ""
                return {
                    "status": "success",
                    "is_connected": True,
                    "message": f"Connectée & Opérationnelle{count_str}",
                    "latency_ms": lat_ms,
                }
            elif res.status_code == 403:
                msg = f"Clé valide mais accès refusé par Artificial Analysis (HTTP 403 Forbidden : {err_detail or 'Tier/Abonnement restreint'}). Rendez-vous sur votre compte https://artificialanalysis.ai/app/api-keys pour activer l'accès API."
                return {
                    "status": "error",
                    "is_connected": False,
                    "message": msg,
                    "latency_ms": lat_ms,
                }
            elif res.status_code == 401:
                msg = f"Clé non reconnue par Artificial Analysis (HTTP 401 Unauthorized : {err_detail or 'Invalid API key'})."
                return {
                    "status": "error",
                    "is_connected": False,
                    "message": msg,
                    "latency_ms": lat_ms,
                }
            else:
                return {
                    "status": "error",
                    "is_connected": False,
                    "message": f"Réponse API (HTTP {res.status_code}) : {err_detail}",
                    "latency_ms": lat_ms,
                }
    except Exception as e:
        lat_ms = int((time.time() - t0) * 1000)
        return {
            "status": "error",
            "is_connected": False,
            "message": f"Impossible de joindre Artificial Analysis : {str(e)[:120]}",
            "latency_ms": lat_ms,
        }


@router.post("/test-connection", response_model=dict[str, Any])
async def test_api_connection(payload: TestConnectionPayload | None = None):
    """Teste en direct la validité et la connectivité d'OpenRouter et d'Artificial Analysis."""
    req_service = (payload.service if payload else None) or "all"
    or_key = (payload.openrouter_api_key or payload.api_key) if payload else None
    aa_key = payload.artificial_analysis_api_key if payload else None

    if req_service == "openrouter":
        or_res = await check_openrouter_key(or_key)
        return {
            "status": or_res["status"],
            "is_connected": or_res["is_connected"],
            "message": or_res["message"],
            "latency_ms": or_res["latency_ms"],
            "openrouter": or_res,
        }
    elif req_service == "artificial_analysis":
        aa_res = await check_aa_key(aa_key)
        return {
            "status": aa_res["status"],
            "is_connected": aa_res["is_connected"],
            "message": aa_res["message"],
            "latency_ms": aa_res["latency_ms"],
            "artificial_analysis": aa_res,
        }
    else:
        # Tester les deux en parallèle
        import asyncio
        or_res, aa_res = await asyncio.gather(
            check_openrouter_key(or_key),
            check_aa_key(aa_key),
        )
        overall_connected = or_res["is_connected"]
        return {
            "status": "success" if overall_connected else "error",
            "is_connected": overall_connected,
            "message": or_res["message"],
            "latency_ms": or_res["latency_ms"],
            "openrouter": or_res,
            "artificial_analysis": aa_res,
        }

