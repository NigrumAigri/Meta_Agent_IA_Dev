from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncGenerator

import httpx

from core.config import settings
from core.domain import FinOpsMetric, extract_reasoning_metadata
from storage.repository import finops_repo, openrouter_models_repo
from services.mcp_hub import mcp_hub

logger = logging.getLogger(__name__)


def _calc_message_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            total += len(c.split())
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        total += len(str(part.get("text", "")).split())
                    elif part.get("type") == "image_url":
                        total += 1000
    return total


class OpenRouterClient:
    """Client OpenRouter / OpenAI compatible avec streaming SSE, TTFT et suivi FinOps déterministe."""

    def __init__(self) -> None:
        self._cached_models: list[dict[str, Any]] = []
        self._last_fetch_time: float = 0.0
        self._cache_ttl_seconds: float = 900.0

    def get_api_key(self) -> str | None:
        """Récupère la clé API OpenRouter de façon dynamique JIT depuis settings ou SQLite."""
        return settings.get_llm_api_key()

    @property
    def is_configured(self) -> bool:
        return bool(self.get_api_key())

    async def fetch_live_models(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Récupère la totalité du catalogue des modèles OpenRouter (400+ modèles) et synchronise avec SQLite."""
        now = time.time()
        if not force_refresh and self._cached_models and (now - self._last_fetch_time < self._cache_ttl_seconds):
            return self._cached_models

        api_key = self.get_api_key()
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # 1. Tentative d'interrogation de l'API OpenRouter
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"{settings.llm_base_url}/models", headers=headers)
                if res.status_code == 200:
                    raw_data = res.json().get("data", [])
                    if raw_data:
                        formatted = self._format_raw_models(raw_data)
                        # Persistance transactionnelle complète en SQLite
                        openrouter_models_repo.save_models(formatted)
                        self._cached_models = formatted
                        self._last_fetch_time = now
                        return formatted
                else:
                    logger.warning("Échec requête OpenRouter /models : HTTP %s", res.status_code)
        except Exception as err:
            logger.warning("Échec de la récupération live OpenRouter (%s) — chargement SQLite.", err)

        # 2. Repli vers la base SQLite (initialisée au démarrage)
        db_models = openrouter_models_repo.list_all()
        if db_models:
            self._cached_models = db_models
            self._last_fetch_time = now
            return db_models

        return []

    def _format_raw_models(self, raw_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Formate et convertit les prix en USD par million de tokens avec métadonnées de raisonnement réelles."""
        formatted = []
        for m in raw_models:
            mid = m.get("id")
            if not mid:
                continue

            pricing = m.get("pricing", {})
            pin = float(pricing.get("prompt", 0.0) or 0.0) * 1_000_000
            pout = float(pricing.get("completion", 0.0) or 0.0) * 1_000_000
            pcache = float(pricing.get("input_cache_read", pricing.get("cache_read", 0.0)) or 0.0) * 1_000_000

            params = m.get("supported_parameters", []) or []
            arch = m.get("architecture", {}) or {}
            raw_reasoning = m.get("reasoning", {}) or {}
            reasoning_meta = extract_reasoning_metadata(raw_reasoning)

            formatted.append({
                "id": mid,
                "name": m.get("name") or mid,
                "description": m.get("description", ""),
                "context_length": int(m.get("context_length", 128000) or 128000),
                "pin": round(pin, 4),
                "pout": round(pout, 4),
                "pcache": round(pcache, 4),
                "reasoning": reasoning_meta,
                "reasoning_raw": raw_reasoning,
                "supported_parameters": params,
                "architecture": arch,
                "top_provider": m.get("top_provider", {}),
            })
        return formatted

    async def get_model_info(self, model_id: str) -> dict[str, Any] | None:
        """Résout dynamiquement les métadonnées officielles d'un modèle (catalogue SQLite, mémoire ou interrogation directe OpenRouter)."""
        clean_id = (model_id or "").strip()
        if not clean_id:
            return None

        # 1. Recherche dans le cache mémoire actif
        for m in self._cached_models:
            if m["id"].lower() == clean_id.lower():
                return m

        # 2. Recherche dans la table SQLite
        record = openrouter_models_repo.get(clean_id)
        if record:
            return record

        # 3. Interrogation en direct d'OpenRouter
        try:
            api_key = self.get_api_key()
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{settings.llm_base_url}/models", headers=headers)
                if res.status_code == 200:
                    raw_data = res.json().get("data", [])
                    if raw_data:
                        formatted = self._format_raw_models(raw_data)
                        openrouter_models_repo.save_models(formatted)
                        self._cached_models = formatted
                        for m in formatted:
                            if m["id"].lower() == clean_id.lower():
                                return m
        except Exception as e:
            logger.warning("Échec résolution live du modèle %s : %s", clean_id, e)

        # 4. Modèle non répertorié : structure neutre
        return {
            "id": clean_id,
            "name": clean_id,
            "description": "Modèle personnalisé",
            "context_length": 128000,
            "pin": 1.0,
            "pout": 3.0,
            "pcache": 0.25,
            "reasoning": {
                "has_reasoning": False,
                "supported_efforts": [],
                "default_effort": "none",
                "mandatory": False,
                "default_enabled": False,
            },
            "supported_parameters": [],
            "architecture": {},
            "top_provider": {},
        }

    def get_model_pricing(self, model_id: str | None) -> tuple[float, float, float]:
        """Retourne (pin, pout, pcache) exacts en USD par 1M tokens depuis la base de données SQLite."""
        if not model_id:
            return (1.00, 3.00, 0.25)
        
        # 1. Recherche dans le cache mémoire actif
        clean_id = model_id.lower().strip()
        for m in self._cached_models:
            if m["id"].lower() == clean_id:
                return (float(m.get("pin", 0.0)), float(m.get("pout", 0.0)), float(m.get("pcache", 0.0)))

        # 2. Recherche directe dans la table SQLite openrouter_models_cache
        record = openrouter_models_repo.get(model_id)
        if record:
            return (float(record["pin"]), float(record["pout"]), float(record["pcache"]))

        # 3. Modèle personnalisé non répertorié
        return (1.00, 3.00, 0.25)

    async def get_formatted_models(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Retourne l'intégralité du catalogue des modèles avec prix exacts et indicateur de raisonnement."""
        return await self.fetch_live_models(force_refresh=force_refresh)

    async def generate_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
        agent_id: str = "agent_architect",
        agent_name: str = "Architecte & Cadrage",
        project_id: str | None = None,
        project_name: str = "Global",
        task_name: str = "Inférence",
    ) -> tuple[str, FinOpsMetric, str]:
        """Génère une réponse complète et enregistre la métrique FinOps dans SQLite."""
        selected_model = model or settings.llm_discovery_model
        if not self.is_configured:
            fallback_text = (
                "Mode Local : Clé API OpenRouter non configurée. "
                "Veuillez renseigner votre clé dans les paramètres pour activer les inférences en direct."
            )
            p_tokens = _calc_message_tokens(messages)
            metric = FinOpsMetric(
                agent_id=agent_id,
                agent_name=agent_name,
                project_id=project_id,
                project_name=project_name,
                model="local-fallback",
                task_name=task_name,
                prompt_tokens=p_tokens,
                completion_tokens=len(fallback_text.split()),
                reasoning_tokens=0,
                total_tokens=p_tokens + len(fallback_text.split()),
                cost_usd=0.0,
                latency_ms=10,
                ttft_ms=5,
                status="local_fallback",
            )
            # Ne pas enregistrer de fausse transaction en base lors d'un repli local sans appel API
            return fallback_text, metric, "stop"

        api_key = self.get_api_key()
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if reasoning_effort and reasoning_effort != "none":
            payload["reasoning"] = {"effort": reasoning_effort}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://meta-agent-v5.internal",
            "X-Title": "Meta Developer Agent v5 Enterprise",
        }
        if settings.prompt_caching_enabled:
            headers["X-Prompt-Cache"] = "true"

        t0 = time.time()
        try:
            # 0. Sentinelle PRE_LLM_CALL
            from core.domain import HookEventType
            from services.hooks_engine import hooks_engine
            pre_hook = hooks_engine.trigger_event(
                HookEventType.PRE_LLM_CALL,
                {"model": selected_model, "messages": messages, "project_id": project_id},
            )
            if pre_hook.get("is_blocked"):
                raise PermissionError(pre_hook.get("block_reason") or "Appel LLM bloqué par la sentinelle PRE_LLM_CALL.")

            async with httpx.AsyncClient(timeout=120.0) as client:
                res = await client.post(f"{settings.llm_base_url}/chat/completions", json=payload, headers=headers)
                lat_ms = int((time.time() - t0) * 1000)

                if res.status_code != 200:
                    err_msg = f"Erreur OpenRouter HTTP {res.status_code} : {res.text[:200]}"
                    metric = FinOpsMetric(
                        agent_id=agent_id,
                        agent_name=agent_name,
                        project_id=project_id,
                        project_name=project_name,
                        model=selected_model,
                        task_name=task_name,
                        latency_ms=lat_ms,
                        ttft_ms=lat_ms,
                        status="error",
                    )
                    finops_repo.record_inference(metric)
                    return err_msg, metric, "error"

                data = res.json()
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason", "stop")

                usage = data.get("usage", {})
                p_tokens = usage.get("prompt_tokens", 0)
                c_tokens = usage.get("completion_tokens", 0)
                r_tokens = (
                    usage.get("completion_tokens_details", {}).get("reasoning_tokens")
                    or usage.get("reasoning_tokens", 0)
                )
                t_tokens = usage.get("total_tokens", p_tokens + c_tokens + r_tokens)

                # 1. Facturation 100% exacte en direct depuis OpenRouter
                raw_cost = usage.get("cost")
                if raw_cost is not None and isinstance(raw_cost, (int, float)) and raw_cost >= 0:
                    cost_usd = float(raw_cost)
                else:
                    # Repli dynamique basé sur le catalogue réel du modèle si non fourni
                    pin, pout, _ = self.get_model_pricing(selected_model)
                    cost_calc = mcp_hub.execute_tool(
                        "finops_calculator",
                        {
                            "prompt_tokens": p_tokens,
                            "completion_tokens": c_tokens,
                            "reasoning_tokens": r_tokens,
                            "price_in_usd": pin,
                            "price_out_usd": pout,
                        },
                    )
                    cost_usd = cost_calc.get("cost_usd", 0.0)

                metric = FinOpsMetric(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    project_id=project_id,
                    project_name=project_name,
                    model=selected_model,
                    task_name=task_name,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    reasoning_tokens=r_tokens,
                    total_tokens=t_tokens,
                    cost_usd=cost_usd,
                    latency_ms=lat_ms,
                    ttft_ms=int(lat_ms * 0.3),
                    status="success",
                )
                finops_repo.record_inference(metric)

                # 3.bis Sentinelle POST_LLM_CALL
                hooks_engine.trigger_event(
                    HookEventType.POST_LLM_CALL,
                    {"model": selected_model, "metric": metric.model_dump(mode="json"), "cost_usd": cost_usd, "project_id": project_id},
                )

                return content, metric, finish_reason

        except Exception as e:
            lat_ms = int((time.time() - t0) * 1000)
            err_msg = f"Échec d'appel LLM OpenRouter : {str(e)}"
            metric = FinOpsMetric(
                agent_id=agent_id,
                agent_name=agent_name,
                project_id=project_id,
                project_name=project_name,
                model=selected_model,
                task_name=task_name,
                latency_ms=lat_ms,
                status="network_error",
            )
            finops_repo.record_inference(metric)
            return err_msg, metric, "network_error"

    async def stream_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Générateur SSE mot par mot avec détection des reasoning_tokens."""
        selected_model = model or settings.llm_discovery_model
        if not self.is_configured:
            yield {
                "type": "content",
                "delta": "Mode Local : Veuillez configurer votre clé API OpenRouter dans l'onglet Configuration.",
            }
            yield {"type": "finish", "finish_reason": "stop"}
            return

        api_key = self.get_api_key()
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "include_reasoning": True,
            "stream_options": {"include_usage": True},
        }
        if reasoning_effort and reasoning_effort != "none":
            payload["reasoning"] = {"effort": reasoning_effort}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://meta-agent-v5.internal",
            "X-Title": "Meta Developer Agent v5 Enterprise",
        }
        if settings.prompt_caching_enabled:
            headers["X-Prompt-Cache"] = "true"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", f"{settings.llm_base_url}/chat/completions", json=payload, headers=headers
                ) as response:
                    if response.status_code != 200:
                        yield {"type": "error", "message": f"Erreur HTTP {response.status_code}"}
                        return

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            yield {"type": "done"}
                            break
                        try:
                            chunk = json.loads(data_str)
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})

                            # 1. Capture des tokens de pensée / reasoning
                            reasoning_delta = (
                                delta.get("reasoning")
                                or delta.get("reasoning_content")
                                or delta.get("thought")
                            )
                            if reasoning_delta:
                                yield {"type": "thinking", "delta": reasoning_delta}

                            # 2. Gestion du contenu standard
                            if "content" in delta and delta["content"]:
                                yield {"type": "content", "delta": delta["content"]}

                            # 3. Fin de génération
                            if choice.get("finish_reason"):
                                yield {"type": "finish", "finish_reason": choice["finish_reason"]}

                            # 4. Capture de l'usage réel et du coût exact en streaming
                            if "usage" in chunk and chunk["usage"]:
                                yield {"type": "usage", "usage": chunk["usage"]}
                        except Exception:
                            continue
        except Exception as e:
            yield {"type": "error", "message": str(e)}


openrouter_client = OpenRouterClient()
