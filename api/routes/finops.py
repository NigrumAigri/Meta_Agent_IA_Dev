from __future__ import annotations

import csv
import io
from typing import Any
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import PlainTextResponse
from storage.repository import agent_repo, finops_repo, project_repo
from services.benchmarks_client import benchmarks_client
from services.openrouter_client import openrouter_client

router = APIRouter(prefix="/api/v1/finops", tags=["FinOps, Télémétrie & Benchmarks"])


@router.get("/ledger", response_model=list[dict[str, Any]])
def get_finops_ledger(limit: int = Query(100, ge=1, le=500)):
    """Récupère le grand livre des inférences réelles, tokens et coûts déterministes."""
    metrics = finops_repo.list_all()
    # Retourner les plus récents en premier
    return [m.model_dump(mode="json") for m in reversed(metrics[-limit:])]


@router.get("/analytics", response_model=dict[str, Any])
def get_finops_analytics(project_id: str | None = Query(None, description="Filtrer par projet")):
    """Calcule les agrégats FinOps en temps réel (coût total, tokens in/out/cache, latence moyenne) et ventilation 100% dynamique par agent."""
    all_metrics = finops_repo.list_all()
    if project_id:
        # Récupérer UNIQUEMENT les agents configurés sur ce projet (aucune injection externe)
        target_agents = agent_repo.list_all(project_id=project_id)
        metrics = [m for m in all_metrics if m.project_id == project_id]
    else:
        # En mode Studio : Récupérer les méta-agents de base de la plateforme
        target_agents = agent_repo.list_all(is_core_only=True)
        metrics = all_metrics

    total_cost = sum(m.cost_usd for m in metrics)
    total_in = sum(m.prompt_tokens for m in metrics)
    total_out = sum(m.completion_tokens for m in metrics)
    total_cache = sum(m.reasoning_tokens for m in metrics)
    avg_lat = (sum(m.latency_ms for m in metrics) / len(metrics)) if metrics else 0.0

    if project_id:
        proj_obj = project_repo.get(project_id)
        budget_limit = proj_obj.budget_limit_usd if proj_obj else 0.0
    else:
        all_projs = project_repo.list_all()
        budget_limit = sum(p.budget_limit_usd for p in all_projs) if all_projs else 0.0
    budget_remaining = max(0.0, budget_limit - total_cost)

    # 1. Initialiser le breakdown avec STRICTEMENT les agents réels configurés sur ce périmètre
    agent_breakdown: dict[str, dict[str, Any]] = {}
    for a in target_agents:
        agent_breakdown[a.name] = {
            "cost_usd": 0.0,
            "tokens": 0,
            "calls": 0,
            "agent_id": a.id,
        }

    # 2. Associer les consommations réelles enregistrées aux agents actifs de ce périmètre
    agent_id_to_name = {a.id: a.name for a in target_agents}
    for m in metrics:
        if m.agent_id in agent_id_to_name:
            name = agent_id_to_name[m.agent_id]
            agent_breakdown[name]["cost_usd"] += m.cost_usd
            agent_breakdown[name]["tokens"] += m.prompt_tokens + m.completion_tokens
            agent_breakdown[name]["calls"] += 1
        elif m.agent_name and m.agent_name in agent_breakdown:
            name = m.agent_name
            agent_breakdown[name]["cost_usd"] += m.cost_usd
            agent_breakdown[name]["tokens"] += m.prompt_tokens + m.completion_tokens
            agent_breakdown[name]["calls"] += 1

    return {
        "project_id": project_id,
        "total_cost_usd": total_cost,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_cached_tokens": total_cache,
        "total_calls": len(metrics),
        "average_latency_ms": avg_lat,
        "budget_limit_usd": budget_limit,
        "budget_remaining_usd": budget_remaining,
        "agent_breakdown": agent_breakdown,
    }


@router.get("/summary", response_model=dict[str, Any])
def get_finops_summary():
    """Synthèse financière consolidée multi-projets et Studio pour le tableau de bord FinOps Enterprise."""
    all_metrics = finops_repo.list_all()
    all_projects = project_repo.list_all()
    all_agents = agent_repo.list_all()

    agent_id_to_name = {a.id: a.name for a in all_agents}
    project_id_to_name = {str(p.id): p.name for p in all_projects}

    total_cost = sum(m.cost_usd for m in all_metrics)
    total_in = sum(m.prompt_tokens for m in all_metrics)
    total_out = sum(m.completion_tokens for m in all_metrics)
    total_cache = sum(m.reasoning_tokens for m in all_metrics)
    total_tokens = total_in + total_out
    total_calls = len(all_metrics)

    # 1. Ventilation par Projet
    projects_data: list[dict[str, Any]] = []
    project_metrics_map: dict[str | None, list[Any]] = {}
    for m in all_metrics:
        pid = m.project_id
        if pid not in project_metrics_map:
            project_metrics_map[pid] = []
        project_metrics_map[pid].append(m)

    for p in all_projects:
        pid_str = str(p.id)
        p_metrics = project_metrics_map.get(pid_str, [])
        p_cost = sum(m.cost_usd for m in p_metrics)
        p_tokens = sum(m.prompt_tokens + m.completion_tokens for m in p_metrics)
        p_calls = len(p_metrics)
        p_agents = agent_repo.list_all(project_id=pid_str)
        p_pct = round((p_cost / total_cost * 100), 1) if total_cost > 0 else 0.0

        projects_data.append({
            "id": pid_str,
            "name": p.name,
            "cost_usd": p_cost,
            "tokens": p_tokens,
            "calls": p_calls,
            "agents_count": len(p_agents),
            "pct": p_pct,
            "quality_score": float(getattr(p, "quality_score", 0.0) or 0.0),
        })

    # Dépenses Studio / Cadrage hors projet
    studio_metrics = project_metrics_map.get(None, [])
    studio_cost = sum(m.cost_usd for m in studio_metrics)
    studio_tokens = sum(m.prompt_tokens + m.completion_tokens for m in studio_metrics)
    studio_calls = len(studio_metrics)
    studio_pct = round((studio_cost / total_cost * 100), 1) if total_cost > 0 else 0.0

    projects_data.append({
        "id": "studio",
        "name": "Studio & Inception Globale (Hors Projets)",
        "cost_usd": studio_cost,
        "tokens": studio_tokens,
        "calls": studio_calls,
        "agents_count": len(agent_repo.list_all(is_core_only=True)),
        "pct": studio_pct,
        "quality_score": 96,
        "is_studio": True,
    })

    projects_data.sort(key=lambda x: x["cost_usd"], reverse=True)

    # 2. Ventilation par Agent
    agent_breakdown: dict[str, dict[str, Any]] = {}
    for m in all_metrics:
        name = agent_id_to_name.get(m.agent_id) or m.agent_name or m.agent_id
        if name not in agent_breakdown:
            agent_breakdown[name] = {"cost_usd": 0.0, "tokens": 0, "calls": 0}
        agent_breakdown[name]["cost_usd"] += m.cost_usd
        agent_breakdown[name]["tokens"] += m.prompt_tokens + m.completion_tokens
        agent_breakdown[name]["calls"] += 1

    agents_data = [
        {
            "name": name,
            "cost_usd": data["cost_usd"],
            "tokens": data["tokens"],
            "calls": data["calls"],
            "pct": round((data["cost_usd"] / total_cost * 100), 1) if total_cost > 0 else 0.0,
        }
        for name, data in agent_breakdown.items()
    ]
    agents_data.sort(key=lambda x: x["cost_usd"], reverse=True)

    # 3. Dernières transactions réelles
    recent_transactions = [
        {
            "id": m.id,
            "timestamp": m.timestamp.isoformat() if hasattr(m, "timestamp") and m.timestamp else "",
            "project_id": m.project_id,
            "project_name": project_id_to_name.get(m.project_id, "Studio"),
            "agent_id": m.agent_id,
            "agent_name": agent_id_to_name.get(m.agent_id, m.agent_name or m.agent_id),
            "model": m.model or "moonshotai/kimi-k3",
            "prompt_tokens": m.prompt_tokens,
            "completion_tokens": m.completion_tokens,
            "reasoning_tokens": m.reasoning_tokens,
            "cost_usd": m.cost_usd,
            "latency_ms": m.latency_ms,
        }
        for m in reversed(all_metrics[-20:])
    ]

    total_budget = sum(p.budget_limit_usd for p in all_projects) if all_projects else 0.0

    return {
        "total_cost_usd": total_cost,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_cached_tokens": total_cache,
        "total_tokens": total_tokens,
        "total_calls": total_calls,
        "budget_limit_usd": round(total_budget, 2),
        "budget_remaining_usd": max(0.0, round(total_budget - total_cost, 4)),
        "projects_breakdown": projects_data,
        "agents_breakdown": agents_data,
        "recent_transactions": recent_transactions,
    }


@router.get("/export/csv")
def export_finops_csv():
    """Exporte l'intégralité du grand livre FinOps en format CSV."""
    all_metrics = finops_repo.list_all()
    all_projects = project_repo.list_all()
    all_agents = agent_repo.list_all()

    agent_id_to_name = {a.id: a.name for a in all_agents}
    project_id_to_name = {str(p.id): p.name for p in all_projects}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID Transaction",
        "Horodatage",
        "Projet",
        "Agent",
        "Modele LLM",
        "Tokens Entree",
        "Tokens Sortie",
        "Tokens Cache",
        "Cout USD",
        "Latence (ms)",
    ])

    for m in all_metrics:
        ts = m.timestamp.isoformat() if hasattr(m, "timestamp") and m.timestamp else ""
        proj_name = project_id_to_name.get(m.project_id, "Studio")
        ag_name = agent_id_to_name.get(m.agent_id, m.agent_name or m.agent_id)
        writer.writerow([
            m.id,
            ts,
            proj_name,
            ag_name,
            m.model or "",
            m.prompt_tokens,
            m.completion_tokens,
            m.reasoning_tokens,
            f"{m.cost_usd:.6f}",
            f"{m.latency_ms:.1f}",
        ])

    csv_data = output.getvalue()
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=finops_ledger.csv"},
    )


from storage.repository import aa_benchmarks_repo


@router.get("/benchmarks", response_model=list[dict[str, Any]])
def get_benchmarks(
    q: str | None = Query(None, description="Filtre textuel"),
    sort_by: str = Query("coding_desc", description="Tri des modèles"),
    min_coding_score: float | None = Query(None, description="Score coding min"),
    max_price_out_usd: float | None = Query(None, description="Prix max sortie"),
    limit: int = Query(100, ge=1, le=1000, description="Limite"),
):
    """Récupère le catalogue unifié des 600+ modèles Artificial Analysis enrichi avec tarifs OpenRouter."""
    return aa_benchmarks_repo.list_all(
        q=q,
        min_coding_score=min_coding_score,
        max_price_out_usd=max_price_out_usd,
        sort_by=sort_by,
        limit=limit,
    )


@router.get("/benchmarks/status", response_model=dict[str, Any])
def get_benchmarks_sync_status():
    """Statut de synchronisation de la base de benchmarks et prochain créneau planifié."""
    return benchmarks_client.get_sync_status()


@router.post("/benchmarks/sync", response_model=dict[str, Any])
@router.post("/benchmarks/refresh", response_model=dict[str, Any])
async def sync_benchmarks():
    """Déclenche la synchronisation complète (API v2 Artificial Analysis + tarifs OpenRouter en temps réel)."""
    return await benchmarks_client.sync_all(force=True)


@router.post("/benchmarks/test-key", response_model=dict[str, Any])
async def test_benchmarks_key(payload: dict[str, Any] | None = None):
    """Teste la validité d'une clé API Artificial Analysis en direct."""
    key = payload.get("api_key") if payload else None
    return await benchmarks_client.test_aa_connection(api_key=key)


@router.get("/models", response_model=list[dict[str, Any]])
async def get_openrouter_models(
    q: str | None = Query(None, description="Filtre de recherche textuel"),
    force_refresh: bool = Query(False, description="Forcer le rafraîchissement en direct depuis OpenRouter"),
):
    """Récupère la totalité du catalogue des modèles OpenRouter (400+ modèles) avec tarifs exacts et indicateurs de raisonnement."""
    models = await openrouter_client.get_formatted_models(force_refresh=force_refresh)
    if q:
        q_lower = q.lower().strip()
        models = [
            m for m in models
            if q_lower in m["id"].lower()
            or q_lower in m["name"].lower()
            or q_lower in m.get("description", "").lower()
        ]
    return models


@router.post("/models/refresh", response_model=list[dict[str, Any]])
async def refresh_openrouter_models():
    """Force la synchronisation immédiate de tous les modèles et tarifs depuis OpenRouter."""
    return await openrouter_client.get_formatted_models(force_refresh=True)


@router.get("/models/info", response_model=dict[str, Any])
async def get_model_info(model_id: str = Query(..., description="ID du modèle OpenRouter")):
    """Résout dynamiquement les métadonnées exactes et les options de raisonnement pour un modèle donné."""
    info = await openrouter_client.get_model_info(model_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Modèle '{model_id}' non trouvé")
    return info


@router.get("/models/match", response_model=dict[str, Any])
def match_models(role: str = Query("coding", pattern="^(coding|reasoning)$")):
    """Sélectionne scientifiquement les 3 profils 1-clic (Top Perf, Sweet Spot, Ultra Eco)."""
    matched = benchmarks_client.match_best_models_for_role(role=role)
    return {
        badge.value: record.model_dump(mode="json")
        for badge, record in matched.items()
    }


@router.get("/models/vision", response_model=list[dict[str, Any]])
def get_vision_models(
    q: str | None = Query(None, description="Filtre textuel"),
    limit: int = Query(100, ge=1, le=500),
):
    """Retourne la liste 100% dynamique de tous les modèles supportant la vision/image."""
    from storage.repository import openrouter_models_repo
    return openrouter_models_repo.list_vision_models(q=q, limit=limit)

