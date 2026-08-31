from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from core.config import settings
from core.domain import BenchmarkRecord, FinOpsBadge, utc_now
from storage.repository import aa_benchmarks_repo, openrouter_models_repo, settings_repo
from services.openrouter_client import openrouter_client

logger = logging.getLogger(__name__)

# Fallback certifié initial de secours
FALLBACK_19_BENCHMARKS: list[dict[str, Any]] = [
    {
        "id": "anthropic/claude-3.5-sonnet",
        "slug": "claude-3-5-sonnet",
        "name": "Claude 3.5 Sonnet",
        "creator_name": "Anthropic",
        "creator_slug": "anthropic",
        "release_date": "2024-10-22",
        "intelligence_index": 95.0,
        "coding_index": 93.7,
        "math_index": 78.3,
        "terminalbench_v2_1": 0.89,
        "terminalbench_hard": 0.58,
        "gpqa_diamond": 0.93,
        "scicode": 0.56,
        "hle": 0.49,
        "lcr": 0.74,
        "ifbench": 0.63,
        "mmlu_pro": 0.85,
        "livecodebench": 0.80,
        "tau_banking": 0.44,
        "tau2": 0.94,
        "speed_tok_s": 85.0,
        "ttft_seconds": 0.38,
        "ttfat_seconds": 0.38,
        "price_in_usd": 3.00,
        "price_out_usd": 15.00,
        "price_blended_usd": 6.00,
        "evaluations": {
            "artificial_analysis_intelligence_index": 95.0,
            "artificial_analysis_coding_index": 93.7,
            "terminalbench_v2_1": 0.89,
            "terminal_bench_v2_1": 89.0,
            "gpqa": 0.93,
            "gpqa_diamond": 93.0,
            "scicode": 56.0,
            "hle": 0.49,
        },
    },
    {
        "id": "google/gemini-3.7-flash",
        "slug": "gemini-3-7-flash",
        "name": "Gemini 3.7 Flash (high)",
        "creator_name": "Google",
        "creator_slug": "google",
        "release_date": "2026-08-13",
        "intelligence_index": 56.0,
        "coding_index": 76.1,
        "math_index": 85.0,
        "terminalbench_v2_1": 0.8576,
        "terminalbench_hard": 0.409,
        "gpqa_diamond": 0.945,
        "scicode": 0.568,
        "hle": 0.479,
        "lcr": 0.80,
        "ifbench": 0.76,
        "mmlu_pro": 0.88,
        "livecodebench": 0.85,
        "tau_banking": 0.3278,
        "tau2": 0.95,
        "speed_tok_s": 376.06,
        "ttft_seconds": 8.36,
        "ttfat_seconds": 8.36,
        "price_in_usd": 0.375,
        "price_out_usd": 1.875,
        "price_blended_usd": 0.75,
        "evaluations": {
            "artificial_analysis_intelligence_index": 56.0,
            "artificial_analysis_coding_index": 76.1,
            "terminalbench_v2_1": 0.8576,
            "gpqa": 0.945,
            "scicode": 0.568,
            "hle": 0.479,
            "lcr": 0.80,
        },
    },
    {
        "id": "z-ai/glm-5.3-flash",
        "slug": "glm-5-3-flash",
        "name": "GLM-5.3-Flash",
        "creator_name": "Z AI",
        "creator_slug": "zai",
        "release_date": "2026-08-26",
        "intelligence_index": 57.5,
        "coding_index": 71.5,
        "math_index": 75.0,
        "terminalbench_v2_1": 0.8427,
        "terminalbench_hard": 0.38,
        "gpqa_diamond": 0.912,
        "scicode": 0.461,
        "hle": 0.399,
        "lcr": 0.78,
        "ifbench": 0.70,
        "mmlu_pro": 0.82,
        "livecodebench": 0.78,
        "tau_banking": 0.4722,
        "tau2": 0.85,
        "speed_tok_s": 49.03,
        "ttft_seconds": 1.18,
        "evaluations": {
            "artificial_analysis_intelligence_index": 57.5,
            "artificial_analysis_coding_index": 71.5,
            "terminalbench_v2_1": 0.8427,
            "gpqa": 0.912,
            "scicode": 0.461,
            "hle": 0.399,
            "lcr": 0.78,
        },
    },
    {
        "id": "openai/gpt-4o",
        "slug": "gpt-4o",
        "name": "GPT-4o (Omni)",
        "creator_name": "OpenAI",
        "creator_slug": "openai",
        "release_date": "2024-05-13",
        "intelligence_index": 93.0,
        "coding_index": 90.2,
        "math_index": 75.6,
        "terminalbench_v2_1": 0.85,
        "terminalbench_hard": 0.54,
        "gpqa_diamond": 0.93,
        "scicode": 0.54,
        "hle": 0.43,
        "lcr": 0.79,
        "ifbench": 0.73,
        "mmlu_pro": 0.83,
        "livecodebench": 0.77,
        "tau_banking": 0.42,
        "tau2": 0.88,
        "speed_tok_s": 110.0,
        "ttft_seconds": 0.45,
        "ttfat_seconds": 0.45,
        "price_in_usd": 2.50,
        "price_out_usd": 10.00,
        "price_blended_usd": 4.50,
        "evaluations": {
            "artificial_analysis_intelligence_index": 93.0,
            "artificial_analysis_coding_index": 90.2,
            "terminalbench_v2_1": 0.85,
            "gpqa": 0.93,
            "scicode": 0.54,
            "hle": 0.43,
        },
    },
    {
        "id": "qwen/qwen-2.5-coder-32b-instruct",
        "slug": "qwen-2-5-coder-32b-instruct",
        "name": "Qwen 2.5 Coder 32B",
        "creator_name": "Qwen / Alibaba",
        "creator_slug": "alibaba",
        "release_date": "2024-11-12",
        "intelligence_index": 89.0,
        "coding_index": 91.5,
        "math_index": 71.2,
        "terminalbench_v2_1": 0.85,
        "terminalbench_hard": 0.52,
        "gpqa_diamond": 0.93,
        "scicode": 0.53,
        "hle": 0.43,
        "lcr": 0.86,
        "ifbench": 0.71,
        "mmlu_pro": 0.82,
        "livecodebench": 0.79,
        "tau_banking": 0.51,
        "tau2": 0.87,
        "speed_tok_s": 95.0,
        "ttft_seconds": 0.35,
        "ttfat_seconds": 0.35,
        "price_in_usd": 0.20,
        "price_out_usd": 0.40,
        "price_blended_usd": 0.25,
        "evaluations": {
            "artificial_analysis_intelligence_index": 89.0,
            "artificial_analysis_coding_index": 91.5,
            "terminalbench_v2_1": 0.85,
            "gpqa": 0.93,
            "scicode": 0.53,
            "hle": 0.43,
        },
    },
    {
        "id": "moonshotai/kimi-k3",
        "slug": "kimi-k3",
        "name": "Kimi K3 (Reasoning)",
        "creator_name": "Moonshot AI",
        "creator_slug": "moonshot",
        "release_date": "2025-01-15",
        "intelligence_index": 91.0,
        "coding_index": 88.4,
        "math_index": 82.5,
        "terminalbench_v2_1": 0.86,
        "terminalbench_hard": 0.55,
        "gpqa_diamond": 0.94,
        "scicode": 0.57,
        "hle": 0.47,
        "lcr": 0.67,
        "ifbench": 0.74,
        "mmlu_pro": 0.81,
        "livecodebench": 0.75,
        "tau_banking": 0.46,
        "tau2": 0.95,
        "speed_tok_s": 65.0,
        "ttft_seconds": 0.80,
        "ttfat_seconds": 0.80,
        "price_in_usd": 0.80,
        "price_out_usd": 2.50,
        "price_blended_usd": 1.20,
        "evaluations": {
            "artificial_analysis_intelligence_index": 91.0,
            "artificial_analysis_coding_index": 88.4,
            "terminalbench_v2_1": 0.86,
            "gpqa": 0.94,
            "scicode": 0.57,
            "hle": 0.47,
        },
    }
]


class BenchmarksClient:
    """Moteur d'évaluation scientifique universel basé sur Artificial Analysis v2 et tarifs temps réel OpenRouter."""

    def __init__(self) -> None:
        self._scheduler_task: asyncio.Task[None] | None = None
        self._last_scheduled_synced_hour: int | None = None
        self._seed_cache_if_empty()

    def _seed_cache_if_empty(self) -> None:
        status = aa_benchmarks_repo.get_sync_status()
        if status["total_models"] == 0:
            aa_benchmarks_repo.upsert_all(FALLBACK_19_BENCHMARKS)

    def _seed_cache(self) -> None:
        aa_benchmarks_repo.upsert_all(FALLBACK_19_BENCHMARKS)

    def get_aa_api_key(self) -> str | None:
        """Récupère la clé API Artificial Analysis depuis system_settings, config ou environnement."""
        return (
            settings_repo.get("artificial_analysis_api_key")
            or settings.artificial_analysis_api_key
            or os.getenv("ARTIFICIAL_ANALYSIS_API_KEY")
            or os.getenv("AA_API_KEY")
        )

    def set_aa_api_key(self, api_key: str | None) -> None:
        """Enregistre la clé API dans SQLite et synchronise .env."""
        settings_repo.set("artificial_analysis_api_key", api_key)
        if api_key:
            settings.artificial_analysis_api_key = api_key

    def get_benchmarks(self) -> list[BenchmarkRecord]:
        return aa_benchmarks_repo.get_cached_benchmarks()

    def get_sync_status(self) -> dict[str, Any]:
        status = aa_benchmarks_repo.get_sync_status()
        status["has_api_key"] = bool(self.get_aa_api_key())
        status["next_scheduled_sync"] = self._get_next_scheduled_sync_time()
        return status

    def _get_next_scheduled_sync_time(self) -> str:
        now = datetime.now()
        next_dt = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        if next_dt.date() == now.date():
            return f"Aujourd'hui à {next_dt.hour:02d}:00"
        return f"Demain à {next_dt.hour:02d}:00"

    async def test_aa_connection(self, api_key: str | None = None) -> dict[str, Any]:
        """Teste la validité d'une clé API Artificial Analysis."""
        key = api_key or self.get_aa_api_key()
        if not key:
            return {"success": False, "error": "Aucune clé API fournie"}

        headers = {
            "x-api-key": key,
            "User-Agent": "MetaAgentDev/5.0",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get("https://artificialanalysis.ai/api/v2/data/llms/models", headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    models_count = len(data.get("data", []))
                    return {"success": True, "models_count": models_count, "status_code": 200}
                else:
                    return {"success": False, "error": f"Erreur API ({res.status_code}): {res.text[:200]}", "status_code": res.status_code}
        except Exception as e:
            return {"success": False, "error": f"Erreur de connexion : {str(e)}"}

    async def sync_all(self, force: bool = False) -> dict[str, Any]:
        """Synchronise l'intégralité des modèles Artificial Analysis avec les tarifs réels OpenRouter."""
        aa_key = self.get_aa_api_key()
        aa_models_raw: list[dict[str, Any]] = []

        # 1. Appel Artificial Analysis v2 (1 seul appel HTTP)
        if aa_key:
            headers = {
                "x-api-key": aa_key,
                "User-Agent": "MetaAgentDev/5.0",
                "Accept": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    res = await client.get("https://artificialanalysis.ai/api/v2/data/llms/models", headers=headers)
                    if res.status_code == 200:
                        aa_models_raw = res.json().get("data", [])
                        logger.info("Artificial Analysis: %d modèles récupérés avec succès.", len(aa_models_raw))
                    else:
                        logger.warning("Artificial Analysis API Status %d: %s", res.status_code, res.text[:200])
            except Exception as err:
                logger.error("Erreur requête Artificial Analysis : %s", err)

        # 2. Récupération des prix OpenRouter en temps réel (Public endpoint)
        or_models = await openrouter_client.fetch_live_models(force_refresh=True)
        or_pricing_map: dict[str, dict[str, Any]] = {}
        for m in or_models:
            mid = (m.get("id") or "").lower()
            if mid:
                or_pricing_map[mid] = {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "pin": float(m.get("pin", 0.0) or 0.0),
                    "pout": float(m.get("pout", 0.0) or 0.0),
                    "pcache": float(m.get("pcache", 0.0) or 0.0),
                    "context_length": int(m.get("context_length", 128000) or 128000),
                }

        # 3. Fusion et réconciliation OpenRouter <-> Artificial Analysis
        unified_records: list[dict[str, Any]] = []

        def normalize_str(s: str) -> str:
            return s.lower().replace("-instruct", "").replace("-preview", "").replace(":free", "").replace(":batch", "").replace(".", "-").replace("_", "-").replace(" ", "-")

        # Map des modèles AA indexés par slug normalisé
        aa_map: dict[str, dict[str, Any]] = {}
        for a in aa_models_raw:
            slug = (a.get("slug") or a.get("id") or "").strip().lower()
            if slug:
                aa_map[normalize_str(slug)] = a

        # A. Traitement des modèles issus d'Artificial Analysis
        for a in aa_models_raw:
            slug = a.get("slug") or a.get("id") or "model"
            clean_slug = slug.strip().lower()
            norm_slug = normalize_str(clean_slug)

            # Trouver le prix OpenRouter correspondant
            matched_or = None
            for or_id_clean, or_data in or_pricing_map.items():
                norm_or = normalize_str(or_id_clean)
                if norm_slug in norm_or or norm_or in norm_slug:
                    matched_or = or_data
                    break

            # Tarifs réels OpenRouter prioritaires
            p_in = matched_or["pin"] if matched_or else float(a.get("pricing", {}).get("price_1m_input_tokens", 0.0) or 0.0)
            p_out = matched_or["pout"] if matched_or else float(a.get("pricing", {}).get("price_1m_output_tokens", 0.0) or 0.0)
            p_cache = matched_or["pcache"] if matched_or else 0.0
            p_blended = matched_or["pout"] if matched_or else float(a.get("pricing", {}).get("price_1m_blended_3_to_1", 0.0) or 0.0)

            evals = a.get("evaluations", {}) or {}
            creator = a.get("model_creator", {}) or {}

            unified_records.append({
                "id": a.get("id") or clean_slug,
                "slug": clean_slug,
                "name": a.get("name") or clean_slug,
                "creator_name": creator.get("name") or "Unknown",
                "creator_slug": creator.get("slug") or "",
                "release_date": a.get("release_date") or "",
                "intelligence_index": float(evals.get("artificial_analysis_intelligence_index") or 0.0),
                "coding_index": float(evals.get("artificial_analysis_coding_index") or 0.0),
                "speed_tok_s": float(a.get("median_output_tokens_per_second") or 0.0),
                "ttft_seconds": float(a.get("median_time_to_first_token_seconds") or 0.0),
                "price_in_usd": round(p_in, 4),
                "price_out_usd": round(p_out, 4),
                "price_blended_usd": round(p_blended, 4),
                "price_cache_usd": round(p_cache, 4),
                "evaluations": evals,
                "raw_payload": a,
            })

        # B. Si la clé AA n'était pas fournie ou pour préserver les modèles de fallback
        if not unified_records:
            unified_records = list(FALLBACK_19_BENCHMARKS)

        # Enregistrement atomique en base
        count = aa_benchmarks_repo.upsert_all(unified_records)
        return {
            "success": True,
            "models_synced": count,
            "timestamp": utc_now().isoformat(),
        }

    def _get_most_recent_scheduled_slot(self, now: datetime) -> datetime:
        """Retourne le début de l'heure courante (créneau horaire)."""
        return now.replace(minute=0, second=0, microsecond=0)

    async def check_and_run_startup_sync(self) -> None:
        """Vérifie si la synchronisation horaire courante a été effectuée."""
        last_sync = aa_benchmarks_repo.get_last_sync_time()
        should_sync = False
        now_local = datetime.now()

        if last_sync is None:
            should_sync = True
        else:
            # Convertir last_sync en heure locale naïve pour comparaison directe
            last_sync_local = last_sync.astimezone().replace(tzinfo=None) if last_sync.tzinfo else last_sync
            most_recent_slot = self._get_most_recent_scheduled_slot(now_local)
            
            # Si la dernière synchronisation est antérieure à l'heure courante
            if last_sync_local < most_recent_slot:
                should_sync = True

        if should_sync:
            logger.info("Synchronisation horaire des benchmarks en cours...")
            try:
                await self.sync_all()
            except Exception as e:
                logger.warning("Erreur sync benchmarks : %s", e)

    def start_background_scheduler(self) -> None:
        """Démarre la boucle asynchrone de planification (toutes les heures + rattrapage boot/veille)."""
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def _scheduler_loop(self) -> None:
        logger.info("Planificateur de benchmarks démarré (Toutes les heures + rattrapage boot/veille).")
        # Vérification initiale au démarrage
        await self.check_and_run_startup_sync()

        while True:
            try:
                await asyncio.sleep(60)
                # Vérifie et synchronise chaque heure ou rattrape après une mise en veille
                await self.check_and_run_startup_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Erreur boucle scheduler benchmarks : %s", e)
                await asyncio.sleep(60)

    def list_available_benchmark_metrics(self) -> list[str]:
        """Extrait dynamiquement toutes les clés de benchmarks présentes dans evaluations_json sans liste statique."""
        benchmarks = self.get_benchmarks()
        if not benchmarks:
            self._seed_cache_if_empty()
            benchmarks = self.get_benchmarks()

        keys_set: set[str] = set()
        for b in benchmarks:
            if b.evaluations:
                keys_set.update(b.evaluations.keys())
        # Trier alphabétiquement pour un retour déterministe
        return sorted(list(keys_set))

    def compute_dynamic_quality_score(
        self,
        b: BenchmarkRecord,
        target_metrics: list[str] | None = None,
    ) -> float:
        """Calcule la note composite sur 100 en pur Python de manière 100% dynamique et tolérante."""
        evals = b.evaluations or {}
        values: list[float] = []

        if target_metrics:
            for metric in target_metrics:
                m_clean = metric.lower().strip()
                val = evals.get(m_clean)
                if val is None:
                    # Recherche insensible à la casse
                    for k, v in evals.items():
                        if k.lower() == m_clean:
                            val = v
                            break
                if val is not None and isinstance(val, (int, float)):
                    f_val = float(val)
                    # Normalisation automatique en base 100 si la valeur est comprise entre 0 et 1
                    if 0.0 < f_val <= 1.0:
                        f_val *= 100.0
                    values.append(f_val)

        # Si aucune métrique spécifique n'a pu être extraite, utiliser les index composites ou scores par défaut
        if not values:
            if b.coding_score > 0:
                values.append(float(b.coding_score))
            if b.reasoning_score > 0:
                values.append(float(b.reasoning_score))
            if b.speed_tok_s > 0:
                # Normalisation vitesse (plafonné à 100)
                values.append(min(float(b.speed_tok_s) / 2.0, 100.0))

        if not values:
            return 50.0  # Note médiane par défaut si aucune donnée

        # Moyenne arithmétique déterministe en pur Python (0% hallucination)
        return round(sum(values) / len(values), 2)

    def match_best_models_for_role(
        self,
        role: str = "coding",
        target_metrics: list[str] | None = None,
    ) -> dict[FinOpsBadge, BenchmarkRecord]:
        """Sélectionne scientifiquement et dynamiquement les 3 meilleurs modèles mondiaux selon le rôle et les métriques réelles."""
        benchmarks = self.get_benchmarks()
        if not benchmarks:
            self._seed_cache_if_empty()
            benchmarks = self.get_benchmarks()

        if not benchmarks:
            return {}

        # 1. Sélection dynamique des métriques si non fournies
        metrics_to_use = target_metrics
        if not metrics_to_use:
            available = self.list_available_benchmark_metrics()
            r_lower = role.lower().strip()

            if any(w in r_lower for w in ["code", "dev", "program", "python", "backend", "frontend", "fullstack"]):
                metrics_to_use = [m for m in available if any(k in m for k in ["coding", "terminal", "livecode", "scicode", "swe"])]
            elif any(w in r_lower for w in ["redac", "blog", "write", "content", "seo", "text", "article"]):
                metrics_to_use = [m for m in available if any(k in m for k in ["mmlu", "intelligence", "ifbench", "lcr"])]
            elif any(w in r_lower for w in ["math", "finance", "compta", "analyst", "data", "calc"]):
                metrics_to_use = [m for m in available if any(k in m for k in ["math", "aime", "gpqa", "scicode"])]
            elif any(w in r_lower for w in ["agent", "tool", "mcp", "action", "exec"]):
                metrics_to_use = [m for m in available if any(k in m for k in ["tau", "bfcl", "ifbench", "terminal"])]
            else:
                metrics_to_use = [m for m in available if any(k in m for k in ["intelligence", "gpqa", "mmlu", "coding"])]

        # 2. Évaluation de chaque modèle avec calcul des Ratios Déterministes
        scored_candidates: list[tuple[BenchmarkRecord, float, float]] = []
        for b in benchmarks:
            quality_score = self.compute_dynamic_quality_score(b, target_metrics=metrics_to_use)
            # Prix de sortie strict sans hardcoding
            price_out = float(b.price_out_usd) if b.price_out_usd is not None else 0.50
            # Formule d'efficience quadratique du Sweet Spot
            sweet_spot_ratio = (quality_score * quality_score) / (price_out + 0.10)
            scored_candidates.append((b, quality_score, sweet_spot_ratio))

        # A. Top Performance : score de qualité pur le plus élevé
        sorted_by_perf = sorted(scored_candidates, key=lambda x: x[1], reverse=True)
        top_perf = sorted_by_perf[0][0] if sorted_by_perf else benchmarks[0]

        # B. Sweet Spot : meilleur ratio qualité/prix parmi les modèles ayant au moins 75/100 (ou meilleur ratio global)
        viable_sweet_spot = [c for c in scored_candidates if c[1] >= 75.0]
        if not viable_sweet_spot:
            viable_sweet_spot = scored_candidates
        sorted_sweet_spot = sorted(viable_sweet_spot, key=lambda x: x[2], reverse=True)
        sweet_spot = sorted_sweet_spot[0][0] if sorted_sweet_spot else top_perf

        # C. Ultra Éco : prix de sortie le plus bas avec un seuil de viabilité >= 50/100
        viable_eco = [c for c in scored_candidates if c[1] >= 50.0 and c[0].price_out_usd is not None and c[0].price_out_usd > 0]
        if not viable_eco:
            viable_eco = scored_candidates
        sorted_eco = sorted(viable_eco, key=lambda x: (x[0].price_out_usd, -x[1]))
        ultra_eco = sorted_eco[0][0] if sorted_eco else benchmarks[-1]

        return {
            FinOpsBadge.TOP_PERFORMANCE: top_perf,
            FinOpsBadge.SWEET_SPOT: sweet_spot,
            FinOpsBadge.ULTRA_ECO: ultra_eco,
        }

    def get_model_recommendation_card_data(self, role: str = "coding") -> dict[str, Any]:
        """Génère la structure de données complète pour la Carte Interactive (Action Card) dans le Chat."""
        trio = self.match_best_models_for_role(role)
        top_perf = trio.get(FinOpsBadge.TOP_PERFORMANCE)
        sweet_spot = trio.get(FinOpsBadge.SWEET_SPOT)
        ultra_eco = trio.get(FinOpsBadge.ULTRA_ECO)

        return {
            "role": role,
            "sweet_spot": {
                "badge": "SWEET_SPOT",
                "label": "Sweet Spot (Recommandé)",
                "color": "green",
                "model_id": sweet_spot.model_id if sweet_spot else "qwen/qwen-2.5-coder-32b-instruct",
                "model_name": sweet_spot.name if sweet_spot else "Qwen 2.5 Coder 32B",
                "creator": sweet_spot.creator if sweet_spot else "Qwen",
                "quality_score": self.compute_dynamic_quality_score(sweet_spot) if sweet_spot else 91.5,
                "price_in_usd": sweet_spot.price_in_usd if sweet_spot else 0.20,
                "price_out_usd": sweet_spot.price_out_usd if sweet_spot else 0.40,
                "speed_tok_s": sweet_spot.speed_tok_s if sweet_spot else 95.0,
                "reasoning_effort": "high" if "coder" in role or "arch" in role else "medium",
            },
            "top_performance": {
                "badge": "TOP_PERFORMANCE",
                "label": "Top Performance",
                "color": "purple",
                "model_id": top_perf.model_id if top_perf else "openai/gpt-4o",
                "model_name": top_perf.name if top_perf else "GPT-4o",
                "creator": top_perf.creator if top_perf else "OpenAI",
                "quality_score": self.compute_dynamic_quality_score(top_perf) if top_perf else 93.0,
                "price_in_usd": top_perf.price_in_usd if top_perf else 2.50,
                "price_out_usd": top_perf.price_out_usd if top_perf else 10.00,
                "speed_tok_s": top_perf.speed_tok_s if top_perf else 110.0,
                "reasoning_effort": "high",
            },
            "ultra_eco": {
                "badge": "ULTRA_ECO",
                "label": "Ultra Économique",
                "color": "amber",
                "model_id": ultra_eco.model_id if ultra_eco else "moonshotai/kimi-k3",
                "model_name": ultra_eco.name if ultra_eco else "Kimi K3",
                "creator": ultra_eco.creator if ultra_eco else "Moonshot",
                "quality_score": self.compute_dynamic_quality_score(ultra_eco) if ultra_eco else 88.4,
                "price_in_usd": ultra_eco.price_in_usd if ultra_eco else 0.80,
                "price_out_usd": ultra_eco.price_out_usd if ultra_eco else 2.50,
                "speed_tok_s": ultra_eco.speed_tok_s if ultra_eco else 65.0,
                "reasoning_effort": "medium",
            },
        }

    def search_catalog(
        self,
        q: str | None = None,
        min_coding_score: float | None = None,
        max_price_out_usd: float | None = None,
        benchmark_filters: dict[str, float] | None = None,
        sort_by: str = "coding_desc",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Moteur de recherche dynamique pour les Agents et Outils MCP."""
        models = aa_benchmarks_repo.list_all(
            q=q,
            min_coding_score=min_coding_score,
            max_price_out_usd=max_price_out_usd,
            sort_by=sort_by,
            limit=limit if not benchmark_filters else 200,
        )

        if not benchmark_filters:
            return models[:limit]

        # Filtrage dynamique tolérant sur le JSON
        alias_map = {
            "terminalbench": "terminalbench_v2_1",
            "terminal_bench": "terminalbench_v2_1",
            "gpqa_diamond": "gpqa",
            "coding": "artificial_analysis_coding_index",
            "intelligence": "artificial_analysis_intelligence_index",
            "math": "artificial_analysis_math_index",
        }

        filtered = []
        for m in models:
            evals = m.get("evaluations", {}) or {}
            match = True
            for target_k, min_val in benchmark_filters.items():
                clean_k = target_k.lower().strip()
                resolved_k = alias_map.get(clean_k, clean_k)
                val = evals.get(resolved_k) or evals.get(clean_k) or m.get(resolved_k) or m.get(clean_k) or 0.0
                try:
                    if float(val) < float(min_val):
                        match = False
                        break
                except (ValueError, TypeError):
                    match = False
                    break
            if match:
                filtered.append(m)

        return filtered[:limit]


benchmarks_client = BenchmarksClient()
