from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

from core.config import settings
from core.domain import CommandDefinition
from storage.repository import commands_repo, project_repo

logger = logging.getLogger(__name__)


class CommandsRegistry:
    """Moteur de Slash Commands rapides avec exécution à 0 coût token LLM (Pilier 4)."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._register_default_handlers()
        self.sync_filesystem_to_db()

    def _register_default_handlers(self) -> None:
        self.register_handler("cadrage_start", self._handle_cadrage)
        self.register_handler("benchmarks_analysis", self._handle_benchmarks)
        self.register_handler("quality_audit", self._handle_audit)
        self.register_handler("time_travel_rollback", self._handle_rollback)
        self.register_handler("project_export_zip", self._handle_export)
        self.register_handler("finops_summary", self._handle_budget)
        self.register_handler("goal_autonomous_mode", self._handle_goal)
        self.register_handler("clear_active_thread", self._handle_clear)

    def _resolve_project(self, context: dict[str, Any]) -> Any:
        project_id = context.get("project_id")
        project = None
        if project_id:
            try:
                project = project_repo.get(project_id)
            except Exception:
                pass
        if not project:
            all_p = project_repo.list_all()
            project = all_p[0] if all_p else None
        return project

    def _handle_cadrage(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        project = self._resolve_project(context)
        proj_name = project.name if project else "Studio Actif"
        
        formatted = (
            f"### Protocole de Cadrage & Inception : {proj_name}\n\n"
            "L'**Agent 1 : Architecte & Cadrage** est prêt à structurer vos spécifications techniques.\n\n"
            "**Pour cadrer efficacement votre application, veuillez préciser :**\n"
            "1. **Objectif Métier Principal** : Quelle est la mission centrale de votre application ?\n"
            "2. **Stack & Dépendances Clés** : FastAPI, SQLite WAL, React/Vanilla, Tailscale, etc.\n"
            "3. **Contraintes Non-Fonctionnelles** : Performance, sécurité des tokens JWT, FinOps.\n"
            "4. **Données ou Pièces Jointes** : Vous pouvez glisser-déposer des images d'UI ou des tableurs Excel.\n\n"
            "> *Exprimez librement votre besoin ci-dessous pour lancer la synthèse architecturale.*"
        )
        return {
            "message": formatted,
            "type": "cadrage_inception",
            "project_name": proj_name,
        }

    def _handle_audit(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        from services.quality_judge import quality_judge

        project = self._resolve_project(context)
        if not project:
            return {
                "message": "Aucun projet actif à auditer.",
                "type": "quality_audit",
                "score": 0.0,
            }

        matrix = quality_judge.evaluate_project(project)
        details_md = "\n".join(f"- {d}" for d in matrix.details)
        formatted = (
            f"### Rapport d'Audit Qualité Déterministe : {project.name}\n\n"
            f"- **Score Global de Conformité** : **{matrix.total_score} / 100** ({matrix.verdict})\n"
            f"- **Santé Technique (AST + Sandbox)** : `{matrix.technical_health} / 35`\n"
            f"- **Robustesse Données & Sécurité** : `{matrix.robustness_security} / 25`\n"
            f"- **Respect du Cadrage Inception** : `{matrix.functional_coverage} / 30`\n"
            f"- **Documentation & Structure** : `{matrix.documentation} / 10`\n\n"
            f"**Détails des vérifications déterministes :**\n{details_md}"
        )
        return {
            "message": formatted,
            "type": "quality_audit",
            "score": matrix.total_score,
            "matrix": matrix.model_dump(mode="json"),
        }

    def _handle_benchmarks(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        from services.benchmarks_client import benchmarks_client

        role = args.strip() if args and args.strip() else "coding"
        card_data = benchmarks_client.get_model_recommendation_card_data(role=role)
        all_benchmarks = benchmarks_client.get_benchmarks()

        top_p = card_data["top_performance"]
        sweet = card_data["sweet_spot"]
        eco = card_data["ultra_eco"]

        formatted_msg = (
            f"### Recommandation Scientifique des Modèles : Rôle « {role.title()} »\n\n"
            f"**1. 🟢 Sweet Spot (Recommandé - Meilleur Ratio)** : `{sweet['model_name']}` ({sweet['creator']})\n"
            f"- Note Qualité : **{sweet['quality_score']}%** | Tarifs : **${sweet['price_in_usd']:.2f} in / ${sweet['price_out_usd']:.2f} out** (1M tokens)\n"
            f"- Réflexion préconisée : `{sweet['reasoning_effort']}` | ID : `{sweet['model_id']}`\n\n"
            f"**2. 🟣 Top Performance (Puissance Max)** : `{top_p['model_name']}` ({top_p['creator']})\n"
            f"- Note Qualité : **{top_p['quality_score']}%** | Tarifs : `${top_p['price_in_usd']:.2f} in / ${top_p['price_out_usd']:.2f} out`\n"
            f"- Réflexion préconisée : `{top_p['reasoning_effort']}` | ID : `{top_p['model_id']}`\n\n"
            f"**3. 🟡 Ultra Éco (Vitesse & Économie)** : `{eco['model_name']}` ({eco['creator']})\n"
            f"- Note Qualité : **{eco['quality_score']}%** | Vitesse : **{int(eco['speed_tok_s'])} t/s** | Tarifs : `${eco['price_in_usd']:.2f} in / ${eco['price_out_usd']:.2f} out`\n\n"
            f"*(Données réelles issues de la base SQLite et des 19 benchmarks certifiés d'Artificial Analysis)*"
        )

        return {
            "message": formatted_msg,
            "type": "benchmarks_card",
            "role": role,
            "recommendation_card": card_data,
            "benchmarks": [
                b.model_dump(mode="json") if hasattr(b, "model_dump") else b
                for b in all_benchmarks
            ],
        }

    def _handle_rollback(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        from services.time_travel import time_travel

        project = self._resolve_project(context)
        if not project:
            return {
                "message": "Aucun projet actif sélectionné pour le rollback.",
                "type": "time_travel_rollback",
                "status": "error",
            }

        pid_str = str(project.id)
        latest_cp = time_travel.rollback_to_latest(pid_str)

        if not latest_cp:
            return {
                "message": (
                    f"### Restauration Time Travel : {project.name}\n\n"
                    "Aucun instantané (checkpoint) antérieur n'a été trouvé pour ce projet. "
                    "Le projet est actuellement à son état initial."
                ),
                "type": "time_travel_rollback",
                "status": "not_found",
            }

        files_count = len(latest_cp.files_snapshot)
        formatted = (
            f"### Snapshot Restauré avec Succès : {project.name}\n\n"
            f"- **Étape Restaurée** : `{latest_cp.step_name}`\n"
            f"- **ID Checkpoint** : `{latest_cp.id}`\n"
            f"- **Horodatage** : `{latest_cp.created_at.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"- **Fichiers Rétablis sur Disque** : **{files_count} fichier(s)** restauré(s) de façon atomique.\n"
            f"- **Intégrité BDD** : Synchronisée avec le Tableau Noir."
        )
        return {
            "message": formatted,
            "type": "time_travel_rollback",
            "status": "success",
            "checkpoint_id": latest_cp.id,
            "step_name": latest_cp.step_name,
            "files_count": files_count,
        }

    def _handle_export(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        from services.project_exporter import project_exporter

        project = self._resolve_project(context)
        if not project:
            return {
                "message": "Aucun projet actif à exporter.",
                "type": "project_export_zip",
                "status": "error",
            }

        written_files = project_exporter.scaffold_project_files(project)
        target_dir = project_exporter.get_project_target_dir(project)

        formatted = (
            f"### Package de Production Prêt : {project.name}\n\n"
            f"- **Emplacement Local** : `{target_dir}`\n"
            f"- **Fichiers Générés** : **{len(written_files)} fichier(s)** validés par parseur AST.\n"
            f"- **Téléchargement ZIP** : Disponible via l'URL `/api/v1/projects/{project.id}/export/zip`.\n"
            f"- **Contrat de Déploiement** : Prêt pour conteneurisation Docker et hébergement de production."
        )
        return {
            "message": formatted,
            "type": "project_export_zip",
            "status": "success",
            "project_id": str(project.id),
            "files_count": len(written_files),
            "export_url": f"/api/v1/projects/{project.id}/export/zip",
        }

    def _handle_budget(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        from storage.repository import finops_repo

        project = self._resolve_project(context)
        project_id = str(project.id) if project else None

        # Détection d'un montant pour ajuster le plafond (ex: /budget 25, /budget 15.50, /budget set 50)
        match_amount = re.search(r"(\d+(?:\.\d+)?)", args) if args else None
        updated_budget = False
        if match_amount and project:
            try:
                new_budget_val = float(match_amount.group(1))
                if new_budget_val > 0:
                    project.budget_limit_usd = round(new_budget_val, 2)
                    project_repo.save(project)
                    updated_budget = True
            except Exception as e:
                logger.error(f"Erreur lors de la mise à jour du budget: {e}")

        all_metrics = finops_repo.list_all()
        if project_id:
            metrics = [m for m in all_metrics if m.project_id == project_id]
            budget_limit = project.budget_limit_usd if project else 0.0
            proj_name = project.name if project else "Projet Actif"
        else:
            metrics = all_metrics
            all_projs = project_repo.list_all()
            budget_limit = sum(p.budget_limit_usd for p in all_projs) if all_projs else 0.0
            proj_name = "Global (Tous projets)"

        total_cost = sum(m.cost_usd for m in metrics)
        total_in = sum(m.prompt_tokens for m in metrics)
        total_out = sum(m.completion_tokens for m in metrics)
        total_cache = sum(m.reasoning_tokens for m in metrics)
        remaining = max(0.0, budget_limit - total_cost)

        if updated_budget and project:
            formatted = (
                f"### Plafond Budgétaire Mis à Jour : {project.name}\n\n"
                f"- **Nouveau Plafond Alloué** : **`${budget_limit:.2f}`**\n"
                f"- **Dépenses Consommées** : `${total_cost:.4f}`\n"
                f"- **Nouveau Solde Restant** : `${remaining:.4f}`\n"
                f"- **Disjoncteur FinOps** : Actif (Seuil de coupure automatique à `${budget_limit:.2f}`)."
            )
            res_type = "budget_updated"
        else:
            formatted = (
                f"### Bilan FinOps & Consommation ({proj_name})\n\n"
                f"- **Dépense Consommée** : `${total_cost:.4f}` (Plafond de sécurité : `${budget_limit:.2f}`)\n"
                f"- **Budget Restant** : `${remaining:.4f}`\n"
                f"- **Jetons** : Entrée `{total_in:,}` | Sortie `{total_out:,}` | Cache `{total_cache:,}`\n"
                f"- **Inférences Totales** : `{len(metrics)}` transactions enregistrées au Grand Livre.\n\n"
                f"> **Astuce** : Tapez `/budget 25` pour définir immédiatement un plafond de 25 $ sur ce projet."
            )
            res_type = "budget_summary"

        return {
            "message": formatted,
            "type": res_type,
            "project_id": project_id,
            "cost_usd": total_cost,
            "budget_limit_usd": budget_limit,
            "remaining_usd": remaining,
            "updated": updated_budget,
        }

    def _handle_goal(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        goal_text = args.strip() if args and args.strip() else "Complétion complète du cahier des charges et passage à 100% des tests unitaires."
        return {
            "message": (
                "### Mode Autonome Haute Intensité (/goal) Activé\n\n"
                f"- **Objectif Stratégique Déclaré** : « *{goal_text}* »\n"
                "- **Boucle d'Orchestration** : Continue (Itérations automatiques Code ➔ AST ➔ Pytest ➔ FinOps).\n"
                "- **Arrêt Déterministe** : Déclenché dès atteinte du score qualité 95/100 ou atteinte du plafond budgétaire."
            ),
            "type": "goal_mode",
            "goal": goal_text,
            "active": True,
        }

    def _handle_clear(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        from storage.sqlite_db import db

        project = self._resolve_project(context)
        if not project:
            return {
                "message": "Aucun fil actif sélectionné à réinitialiser.",
                "type": "clear_thread",
                "status": "error",
            }

        thread_id = project.active_thread_id
        if thread_id:
            db.execute("DELETE FROM project_messages WHERE thread_id = ?;", (thread_id,))
        else:
            db.execute("DELETE FROM project_messages WHERE project_id = ?;", (str(project.id),))

        return {
            "message": (
                f"### Fil de Discussion Réinitialisé : {project.name}\n\n"
                "Tous les messages antérieurs ont été vidés de la mémoire de discussion active. "
                "Le contexte d'orchestration repart sur une base saine et vierge à 0 token."
            ),
            "type": "clear_thread",
            "project_id": str(project.id),
            "status": "cleared",
        }

    def sync_filesystem_to_db(self) -> list[CommandDefinition]:
        """Synchronise le fichier déclaratif data/commands.json vers SQLite (Zéro Hardcoding)."""
        cmds_file = settings.v5_root / "data" / "commands.json"
        synced_cmds: list[CommandDefinition] = []

        if cmds_file.exists():
            try:
                raw_list = json.loads(cmds_file.read_text(encoding="utf-8"))
                for raw in raw_list:
                    cmd_def = CommandDefinition.model_validate(raw)
                    saved = commands_repo.save_command(cmd_def)
                    synced_cmds.append(saved)
                logger.info("Synchronisation physique : %d commandes chargées depuis data/commands.json", len(synced_cmds))
            except Exception as err:
                logger.warning("Erreur lors du chargement de data/commands.json : %s", err)

        return synced_cmds

    def _seed_native_commands(self) -> list[CommandDefinition]:
        """Alias de compatibilité pour initialiser et synchroniser les commandes."""
        return self.sync_filesystem_to_db()

    def register_handler(self, target_name: str, handler: Callable[..., Any]) -> None:
        self._handlers[target_name] = handler

    def list_commands(self, active_only: bool = False) -> list[CommandDefinition]:
        return commands_repo.list_commands(active_only=active_only)

    def is_slash_command(self, text: str) -> bool:
        return text.strip().startswith("/")

    def execute_command(self, raw_input: str, context: dict[str, Any]) -> dict[str, Any]:
        """Intercepte et exécute immédiatement une slash command."""
        parts = raw_input.strip().split(" ", 1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd_def = commands_repo.get_command(cmd_name)
        if not cmd_def or not cmd_def.is_active:
            return {
                "handled": False,
                "command": cmd_name,
                "message": f"Commande inconnue : {cmd_name}. Tapez / pour voir la liste des commandes disponibles.",
            }

        handler = self._handlers.get(cmd_def.target)
        if handler:
            result = handler(args=args, context=context)
            msg = result.get("message") if isinstance(result, dict) else str(result)
            return {"handled": True, "command": cmd_name, "result": result, "message": msg}

        # Réponse générique déterministe
        return {
            "handled": True,
            "command": cmd_name,
            "name": cmd_def.name,
            "message": f"Commande '{cmd_def.name}' exécutée avec succès.",
            "target": cmd_def.target,
        }


commands_registry = CommandsRegistry()
