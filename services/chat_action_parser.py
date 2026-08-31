from __future__ import annotations

import re
import logging
from typing import Any
from uuid import uuid4

from core.domain import (
    ActionProposal,
    AgentDefinition,
    AgentLink,
    LinkType,
    ProposalStatus,
    ProposalType,
    TopologyMode,
)
from storage.repository import (
    agent_links_repo,
    agent_repo,
    proposals_repo,
)
from services.orchestrator import orchestrator

logger = logging.getLogger(__name__)


class ChatActionParser:
    """Analyse les messages en langage naturel dans le Chat pour exécuter des actions directes sur le Canvas
    ou émettre des propositions proactives (Action Cards)."""

    def parse_and_execute_chat_actions(self, message: str, project_id: str | None = None) -> dict[str, Any]:
        """Détecte les intentions d'action Canvas dans le message et les applique instantanément."""
        text = message.strip().lower()
        actions_executed: list[dict[str, Any]] = []
        canvas_updated = False

        # 1. Détection de création d'agent (ex: "ajoute un agent testeur", "crée un agent de sécurité")
        create_match = re.search(r"(?:ajoute|crée|créer|rajoute|ajouter|instancie)\s+(?:un\s+|l\s*['’]|nouvel\s+)?agent\s+([a-zA-Z0-9_\séèêàç\-]+)", text, re.IGNORECASE)
        if create_match:
            agent_raw_name = create_match.group(1).strip()
            # Nettoyer les terminaisons courantes
            agent_name = re.sub(r"\s+(?:pour|avec|qui|sur|dans|de)\s+.*$", "", agent_raw_name, flags=re.IGNORECASE).strip()
            if agent_name and len(agent_name) >= 3:
                slug = re.sub(r"[^a-z0-9_]+", "_", agent_name.lower())[:24]
                agent_id = f"ag_{slug}_{str(uuid4())[:4]}"
                
                # Positionnement intelligent sur le Canvas
                existing_agents = agent_repo.list_all(project_id=project_id, is_core_only=False, include_core=False)
                new_x = 80.0 + (len(existing_agents) % 3) * 360.0
                new_y = 80.0 + (len(existing_agents) // 3) * 260.0

                # Détermination scientifique dynamique du modèle optimal (Sweet Spot par défaut)
                from services.benchmarks_client import benchmarks_client
                from core.domain import FinOpsBadge

                matched_trio = benchmarks_client.match_best_models_for_role(agent_name)
                sweet_spot_model = matched_trio.get(FinOpsBadge.SWEET_SPOT)
                selected_model_id = sweet_spot_model.model_id if sweet_spot_model else "qwen/qwen-2.5-coder-32b-instruct"
                rec_card = benchmarks_client.get_model_recommendation_card_data(agent_name)

                # Détermination du niveau de réflexion
                is_complex_role = any(k in agent_name.lower() for k in ["code", "dev", "arch", "secu", "math", "finance", "strat"])
                rec_reasoning = "high" if is_complex_role else "medium"

                new_agent = AgentDefinition(
                    id=agent_id,
                    name=f"Agent : {agent_name.title()}",
                    project_id=project_id,
                    role_description=f"Agent spécialisé : {agent_name}",
                    role=agent_name,
                    model=selected_model_id,
                    temperature=0.0 if is_complex_role else 0.2,
                    max_tokens=4096,
                    reasoning_effort=rec_reasoning,
                    budget_limit_usd=5.0,
                    canvas_x=new_x,
                    canvas_y=new_y,
                    icon="bot",
                    is_active=True,
                    is_core_meta_agent=False,
                )
                saved = agent_repo.save(new_agent)
                canvas_updated = True
                actions_executed.append({
                    "type": "create_agent",
                    "agent_id": saved.id,
                    "agent_name": saved.name,
                    "model_selected": selected_model_id,
                    "recommendation_card": rec_card,
                    "message": f"Agent « {saved.name} » créé avec le modèle optimal « {sweet_spot_model.name if sweet_spot_model else selected_model_id} » ({rec_card['sweet_spot']['quality_score']}% qualité)."
                })

        # 2. Détection de liaison de câbles (ex: "connecte l'agent A à l'agent B", "relie A avec B en mode débat")
        link_match = re.search(r"(?:connecte|relie|câble|lier|brancher)\s+(?:l\s*['’]agent\s+)?([a-zA-Z0-9_\-]+)\s+(?:à|avec|vers|sur)\s+(?:l\s*['’]agent\s+)?([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
        if link_match:
            src_str = link_match.group(1).strip()
            tgt_str = link_match.group(2).strip()
            
            # Recherche des agents par ID ou par nom partiel
            all_agents = agent_repo.list_all(project_id=project_id)
            src_agent = next((a for a in all_agents if src_str in a.id.lower() or src_str in a.name.lower()), None)
            tgt_agent = next((a for a in all_agents if tgt_str in a.id.lower() or tgt_str in a.name.lower()), None)

            if src_agent and tgt_agent and src_agent.id != tgt_agent.id:
                link_type = LinkType.DIRECT
                if "débat" in text or "debat" in text or "critic" in text:
                    link_type = LinkType.DEBATE
                elif "supervision" in text or "manager" in text or "ordre" in text:
                    link_type = LinkType.SUPERVISION
                elif "parallèle" in text or "parallele" in text or "fan" in text:
                    link_type = LinkType.PARALLEL

                src_short = src_agent.name.split(":")[0].strip()
                tgt_short = tgt_agent.name.split(":")[0].strip()
                new_link = AgentLink(
                    source_agent_id=src_agent.id,
                    target_agent_id=tgt_agent.id,
                    project_id=project_id,
                    link_type=link_type,
                    label=f"{src_short} ➔ {tgt_short}",
                    is_active=True,
                )
                saved_link = agent_links_repo.create(new_link)
                canvas_updated = True
                actions_executed.append({
                    "type": "create_link",
                    "link_id": saved_link.id,
                    "source": src_agent.name,
                    "target": tgt_agent.name,
                    "message": f"Câble branché entre « {src_agent.name} » et « {tgt_agent.name} » ({link_type.value})."
                })

        # 3. Détection de changement de topologie (ex: "passe en topologie parallèle", "mode débat")
        if "topologie parallèle" in text or "mode parallèle" in text:
            orchestrator.set_topology(TopologyMode.PARALLEL)
            actions_executed.append({"type": "set_topology", "topology": "parallel", "message": "Topologie basculée sur Parallèle (Fan-Out)."})
        elif "topologie débat" in text or "mode débat" in text or "consensus" in text:
            orchestrator.set_topology(TopologyMode.CONSENSUS_DEBATE)
            actions_executed.append({"type": "set_topology", "topology": "consensus_debate", "message": "Topologie basculée sur Débat Contradictoire."})
        elif "topologie hiérarchique" in text or "mode manager" in text:
            orchestrator.set_topology(TopologyMode.HIERARCHICAL)
            actions_executed.append({"type": "set_topology", "topology": "hierarchical", "message": "Topologie basculée sur Hiérarchique (Supervision)."})

        return {
            "canvas_updated": canvas_updated,
            "actions_executed": actions_executed,
        }

    def generate_proactive_proposal(
        self,
        project_id: str | None,
        proposal_type: ProposalType,
        title: str,
        description: str,
        benefit: str,
        payload: dict[str, Any],
    ) -> ActionProposal:
        """Génère et persiste une proposition proactive dans la base SQLite."""
        proposal = ActionProposal(
            project_id=project_id,
            proposal_type=proposal_type,
            title=title,
            description=description,
            benefit=benefit,
            payload=payload,
            status=ProposalStatus.PENDING,
        )
        return proposals_repo.create(proposal)


# Singleton
chat_action_parser = ChatActionParser()
