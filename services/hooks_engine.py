from __future__ import annotations

import ast
from datetime import datetime
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable

from core.config import settings
from core.domain import HookAuditLog, HookDefinition, HookEventType, RuleScope
from storage.repository import hooks_repo

logger = logging.getLogger(__name__)


class HooksEngine:
    """Moteur Déterministe d'Écouteurs d'Événements & Sentinelles de Sécurité (Pilier 5)."""

    def __init__(self) -> None:
        self._listeners: dict[HookEventType, list[Callable[..., Any]]] = {
            e: [] for e in HookEventType
        }
        self._action_handlers: dict[str, Callable[[HookDefinition, dict[str, Any]], dict[str, Any]]] = {}
        self._register_native_action_handlers()
        self.sync_filesystem_to_db()

    # --------------------------------------------------------------------------
    # 1. Enregistrement des Handlers d'Actions Déterministes Intégrés
    # --------------------------------------------------------------------------

    def _register_native_action_handlers(self) -> None:
        """Enregistre les 6 moteurs d'actions de sentinelles natives du système."""
        self._action_handlers["security_validator"] = self._handle_security_validator
        self._action_handlers["ast_validator"] = self._handle_ast_validator
        self._action_handlers["finops_circuit_breaker"] = self._handle_finops_circuit_breaker
        self._action_handlers["retry_manager"] = self._handle_retry_manager
        self._action_handlers["snapshot_creator"] = self._handle_snapshot_creator
        self._action_handlers["telemetry_logger"] = self._handle_telemetry_logger

    def register_action_handler(
        self, action_type: str, handler: Callable[[HookDefinition, dict[str, Any]], dict[str, Any]]
    ) -> None:
        """Permet l'extension dynamique de nouveaux types d'actions."""
        self._action_handlers[action_type] = handler

    # --------------------------------------------------------------------------
    # 2. Implémentation des Handlers Natifs
    # --------------------------------------------------------------------------

    def _handle_security_validator(self, hook: HookDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        """Sentinelle de Sécurité : Bloque toute traversée de chemin, fichier sensible ou élévation suspecte."""
        config = hook.config or {}
        blocked_patterns = config.get("blocked_path_patterns", ["..", "/etc/", "C:\\Windows", ".env", "id_rsa"])
        
        args = payload.get("arguments", {})
        # Inspection récursive des chaînes transmises dans les arguments
        def check_val(val: Any) -> str | None:
            if isinstance(val, str):
                for pat in blocked_patterns:
                    if pat.lower() in val.lower():
                        return pat
            elif isinstance(val, dict):
                for v in val.values():
                    res = check_val(v)
                    if res:
                        return res
            elif isinstance(val, list):
                for item in val:
                    res = check_val(item)
                    if res:
                        return res
            return None

        matched_pat = check_val(args)
        if matched_pat:
            logger.warning("Sentinelle de sécurité activée : motif interdit '%s' bloqué dans l'outil %s", matched_pat, payload.get("tool_id"))
            return {
                "status": "blocked",
                "is_allowed": False,
                "reason": f"Violation de sécurité : le motif interdit '{matched_pat}' est formellement bloqué.",
            }

        return {"status": "success", "is_allowed": True}

    def _handle_ast_validator(self, hook: HookDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        """Sentinelle AST : Valide instantanément en mémoire la syntaxe Python du code généré ou modifié."""
        args = payload.get("arguments", {})
        result = payload.get("result", {})
        
        # Récupération du code depuis les arguments ou les résultats
        code_candidate = args.get("code_content") or args.get("content") or result.get("code") or result.get("content")
        
        if not code_candidate or not isinstance(code_candidate, str) or not code_candidate.strip():
            return {"status": "success", "skipped": True, "reason": "Aucun bloc de code Python à inspecter."}

        try:
            ast.parse(code_candidate)
            return {"status": "success", "is_valid": True, "syntax": "valid_python_ast"}
        except SyntaxError as syn_err:
            logger.warning("Sentinelle AST : Erreur syntaxique détectée ligne %s : %s", syn_err.lineno, syn_err.msg)
            return {
                "status": "error",
                "is_valid": False,
                "line": syn_err.lineno,
                "offset": syn_err.offset,
                "error": f"Erreur de syntaxe Python ligne {syn_err.lineno} : {syn_err.msg}",
            }

    def _handle_finops_circuit_breaker(self, hook: HookDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        """Sentinelle FinOps : Surveille le plafond budgétaire et déclenche alertes et coupures d'urgence."""
        config = hook.config or {}
        alert_pct = float(config.get("alert_at_percent", 80.0))
        hard_stop_pct = float(config.get("hard_stop_at_percent", 100.0))
        
        project_id = payload.get("project_id")
        current_spent = float(payload.get("current_spent_usd", payload.get("cost_usd", 0.0)))
        budget_limit = float(payload.get("budget_limit_usd", 5.0))

        if budget_limit > 0:
            spent_pct = (current_spent / budget_limit) * 100.0
            if spent_pct >= hard_stop_pct:
                logger.error("CIRCUIT BREAKER ACTIVÉ : Budget consommé à %.1f%% (Plafond $%.2f)", spent_pct, budget_limit)
                return {
                    "status": "blocked",
                    "action": "hard_stop",
                    "spent_pct": round(spent_pct, 1),
                    "message": f"Coupure d'urgence : Budget projet ({project_id}) épuisé à {spent_pct:.1f}%.",
                }
            elif spent_pct >= alert_pct:
                logger.warning("ALERTE BUDGET : Consommation à %.1f%% du plafond $%.2f", spent_pct, budget_limit)
                return {
                    "status": "warning",
                    "action": "alert",
                    "spent_pct": round(spent_pct, 1),
                    "message": f"Avertissement : Consommation à {spent_pct:.1f}% du budget alloué.",
                }

        return {"status": "success", "action": "allow", "spent_usd": current_spent}

    def _handle_retry_manager(self, hook: HookDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        """Sentinelle Résilience : Calcule et orchestre les retries exponentiels déterministes."""
        config = hook.config or {}
        max_retries = int(config.get("max_retries", 3))
        backoff = float(config.get("backoff_seconds", 2.0))
        attempt = int(payload.get("attempt", 1))

        if attempt <= max_retries:
            delay = backoff * (2 ** (attempt - 1))
            return {
                "status": "retry_scheduled",
                "attempt": attempt,
                "max_retries": max_retries,
                "delay_seconds": delay,
            }
        return {
            "status": "exhausted",
            "attempt": attempt,
            "max_retries": max_retries,
            "message": "Nombre maximal de tentatives atteint sans succès.",
        }

    def _handle_snapshot_creator(self, hook: HookDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        """Sentinelle Time Travel : Notifie et sauvegarde les instantanés d'états atomiques."""
        step_name = payload.get("step_name", "checkpoint_auto")
        project_id = payload.get("project_id", "studio")
        return {
            "status": "success",
            "snapshot_type": "sqlite_wal_state",
            "step": step_name,
            "project_id": project_id,
        }

    def _handle_telemetry_logger(self, hook: HookDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        """Sentinelle Télémétrie : Structure et enregistre les métriques d'inférence."""
        return {
            "status": "success",
            "model": payload.get("model", "unknown"),
            "tokens": payload.get("tokens", {}),
            "cost_usd": payload.get("cost_usd", 0.0),
        }

    # --------------------------------------------------------------------------
    # 3. Synchronisation Déclarative (Zéro Hardcoding)
    # --------------------------------------------------------------------------

    def sync_filesystem_to_db(self) -> list[HookDefinition]:
        """Synchronise le fichier déclaratif data/hooks.json vers SQLite."""
        hooks_file = settings.v5_root / "data" / "hooks.json"
        synced_hooks: list[HookDefinition] = []

        if hooks_file.exists():
            try:
                raw_list = json.loads(hooks_file.read_text(encoding="utf-8"))
                for raw in raw_list:
                    hook_def = HookDefinition.model_validate(raw)
                    saved = hooks_repo.save_hook(hook_def)
                    synced_hooks.append(saved)
                logger.info("Synchronisation physique : %d hooks chargés depuis data/hooks.json", len(synced_hooks))
            except Exception as err:
                logger.warning("Erreur lors du chargement de data/hooks.json : %s", err)

        return synced_hooks

    def _seed_default_hooks(self) -> list[HookDefinition]:
        """Alias de compatibilité pour initialiser et synchroniser les hooks."""
        return self.sync_filesystem_to_db()

    # --------------------------------------------------------------------------
    # 4. Bus d'Événements & Déclenchement Déterministe
    # --------------------------------------------------------------------------

    def register_listener(self, event_type: HookEventType, listener: Callable[..., Any]) -> None:
        """Enregistre un écouteur personnalisé pour un type d'événement donné."""
        self._listeners[event_type].append(listener)

    def trigger_event(self, event_type: HookEventType, payload: dict[str, Any]) -> dict[str, Any]:
        """Déclenche tous les hooks et écouteurs actifs pour un événement de cycle de vie."""
        active_hooks = hooks_repo.list_hooks(
            event_type=event_type,
            active_only=True,
            project_id=payload.get("project_id"),
        )

        results: list[dict[str, Any]] = []
        is_blocked = False
        block_reason = None

        for hook in active_hooks:
            t0 = time.perf_counter()
            hook_status = "success"
            hook_res: dict[str, Any] = {}
            error_msg: str | None = None

            try:
                # 1. Exécution du handler d'action natif associé
                handler = self._action_handlers.get(hook.action_type)
                if handler:
                    hook_res = handler(hook, payload)
                    if hook_res.get("status") == "blocked":
                        is_blocked = True
                        hook_status = "blocked"
                        block_reason = hook_res.get("reason") or hook_res.get("message")
                    elif hook_res.get("status") == "error":
                        hook_status = "error"

                # 2. Exécution des listeners personnalisés enregistrés
                for listener in self._listeners.get(event_type, []):
                    try:
                        custom_res = listener(hook=hook, payload=payload)
                        if custom_res is not None:
                            hook_res["custom_listener_result"] = custom_res
                    except Exception as le:
                        logger.warning("Erreur listener personnalisé hook %s : %s", hook.name, le)

            except Exception as err:
                hook_status = "error"
                error_msg = str(err)
                logger.warning("Échec d'exécution du hook '%s' : %s", hook.name, err)
                hook_res = {"status": "error", "error": str(err)}

            duration_ms = (time.perf_counter() - t0) * 1000.0

            # Enregistrement dans le journal d'audit
            audit_log = HookAuditLog(
                hook_id=hook.id,
                hook_name=hook.name,
                event_type=event_type,
                action_type=hook.action_type,
                status=hook_status,
                duration_ms=duration_ms,
                payload_summary=json.dumps(payload, default=str)[:300],
                result_summary=json.dumps(hook_res, default=str)[:300],
                error=error_msg,
                project_id=payload.get("project_id"),
            )
            hooks_repo.log_execution(audit_log)

            results.append({
                "hook_id": hook.id,
                "hook_name": hook.name,
                "status": hook_status,
                "duration_ms": round(duration_ms, 2),
                "result": hook_res,
            })

        return {
            "event": event_type.value,
            "executed_hooks_count": len(results),
            "is_blocked": is_blocked,
            "block_reason": block_reason,
            "results": results,
        }

    def test_hook(self, hook_id: str, test_payload: dict[str, Any]) -> dict[str, Any]:
        """Exécute unitaire un hook pour test interactif dans l'Inspecteur UI."""
        hook = hooks_repo.get_hook_by_id(hook_id) or hooks_repo.get_hook_by_name(hook_id)
        if not hook:
            raise ValueError(f"Hook '{hook_id}' introuvable.")

        handler = self._action_handlers.get(hook.action_type)
        if not handler:
            return {"status": "error", "message": f"Aucun handler d'action trouvé pour '{hook.action_type}'."}

        t0 = time.perf_counter()
        res = handler(hook, test_payload)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "hook_id": hook.id,
            "hook_name": hook.name,
            "event_type": hook.event_type.value,
            "action_type": hook.action_type,
            "duration_ms": round(duration_ms, 2),
            "result": res,
        }


# Singleton global de gestion des sentinelles
hooks_engine = HooksEngine()
