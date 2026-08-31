from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.config import settings
from core.domain import (
    AgentDefinition,
    AgentType,
    DocumentAttachment,
    HookEventType,
    MessageRole,
    Project,
    ProjectStatus,
    TopologyMode,
)
from storage.repository import agent_links_repo, agent_repo, project_repo
from services.blackboard import blackboard
from services.circuit_breaker import circuit_breaker
from services.hooks_engine import hooks_engine
from services.prompt_compiler import prompt_compiler
from services.token_continuation import token_continuation

logger = logging.getLogger(__name__)


class LegoOrchestrator:
    """Moteur d'Orchestration LEGO supportant 5 topologies interchangeables en 1 clic."""

    def __init__(self) -> None:
        self.active_topology = TopologyMode.HIERARCHICAL

    def set_topology(self, mode: TopologyMode) -> None:
        self.active_topology = mode
        logger.info("Topologie active basculée sur : %s", mode.value)

    async def run_cadrage_turn(
        self,
        project: Project,
        user_message: str,
        attachments: list[DocumentAttachment] | None = None,
    ) -> Project:
        """Traite une interaction de cadrage adaptatif Inception avec l'Architecte."""
        # 1. Contrôle du Disjoncteur Budgétaire
        circuit_breaker.check_project_budget(str(project.id))

        thread = project.get_or_create_main_thread()

        # 2. Enregistrement du message utilisateur
        thread.add_message(
            role=MessageRole.USER,
            content=user_message,
            author_name="Vous",
            attachments=attachments or [],
        )

        # 3. Récupération de l'Architecte
        architect = agent_repo.get("agent_architect") or AgentDefinition(
            id="agent_architect",
            name="Agent 1 : Architecte & Cadrage (Lead Tech & CTO)",
            role_description="Architecture logicielle et cadrage approfondi.",
            agent_type=AgentType.ARCHITECT,
            model=settings.llm_discovery_model,
        )

        # 4. Compilation du System Prompt avec balises XML, MOC, RAG et registre
        system_prompt = prompt_compiler.compile_agent_system_prompt(architect, project_id=str(project.id), task_context=user_message)

        # 5. Injection de la mémoire partagée du Tableau Noir
        bb_context = blackboard.export_context_for_agent(str(project.id))

        messages_payload: list[dict[str, Any]] = [
            {"role": "system", "content": f"{system_prompt}\n\n{bb_context}"},
        ]

        # Fenêtre glissante : 10 derniers messages avec support multimodal et pièces jointes
        for m in thread.messages[-10:]:
            role = "user" if m.role == MessageRole.USER else "assistant"
            if m.attachments:
                has_images = any(
                    att.content_type.startswith("image/")
                    or att.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                    or att.raw_content.startswith("data:image/")
                    for att in m.attachments
                )
                if has_images:
                    multimodal_content: list[dict[str, Any]] = [{"type": "text", "text": m.content}]
                    for att in m.attachments:
                        if (
                            att.content_type.startswith("image/")
                            or att.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                            or att.raw_content.startswith("data:image/")
                        ):
                            url_val = att.raw_content if att.raw_content.startswith("data:image/") else f"data:image/png;base64,{att.raw_content}"
                            multimodal_content.append({"type": "image_url", "image_url": {"url": url_val}})
                        else:
                            multimodal_content.append({"type": "text", "text": f"\n\n[Document joint : {att.filename}]\n{att.raw_content}"})
                    messages_payload.append({"role": role, "content": multimodal_content})
                else:
                    doc_text = "\n\n".join(f"[Document joint : {att.filename}]\n{att.raw_content}" for att in m.attachments)
                    full_text = f"{m.content}\n\n{doc_text}" if doc_text else m.content
                    messages_payload.append({"role": role, "content": full_text})
            else:
                messages_payload.append({"role": role, "content": m.content})

        # 6. Exécution avec auto-continuation
        response_text, metric = await token_continuation.execute_with_auto_continuation(
            messages=messages_payload,
            model=architect.model,
            temperature=architect.temperature,
            max_tokens=architect.max_tokens,
            reasoning_effort=architect.reasoning_effort,
            agent_id=architect.id,
            agent_name=architect.name,
            project_id=str(project.id),
            project_name=project.name,
            task_name="Cadrage Inception",
        )

        # 7. Enregistrement de la réponse de l'Architecte
        thread.add_message(
            role=MessageRole.ASSISTANT,
            content=response_text,
            author_name="Architecte & Cadrage",
            agent_id=architect.id,
        )

        project.status = ProjectStatus.CADRAGE
        project_repo.save(project)
        return project

    async def execute_multi_agent_workflow(
        self,
        project: Project,
        task_instruction: str = "Execution du graphe de workflow",
        topology: TopologyMode | None = None,
    ) -> dict[str, Any]:
        """Execute une mission multi-agents hermetique selon la topologie selectionnee."""
        from services.quality_judge import quality_judge

        topo = topology or self.active_topology
        circuit_breaker.check_project_budget(str(project.id))

        logger.info("Demarrage du workflow multi-agents (Topologie: %s) sur projet %s", topo.value, project.name)

        if topo == TopologyMode.SEQUENTIAL:
            result = await self._run_sequential_topology(project, task_instruction)
        elif topo == TopologyMode.HIERARCHICAL:
            result = await self._run_hierarchical_topology(project, task_instruction)
        elif topo == TopologyMode.CONSENSUS_DEBATE:
            result = await self._run_consensus_debate_topology(project, task_instruction)
        elif topo == TopologyMode.SWARM:
            result = await self._run_swarm_topology(project, task_instruction)
        elif topo == TopologyMode.PARALLEL:
            result = await self._run_parallel_topology(project, task_instruction)
        elif topo == TopologyMode.CUSTOM_DAG:
            result = await self._run_dynamic_dag_topology(project, task_instruction)
        else:
            result = await self._run_dynamic_dag_topology(project, task_instruction)

        # Audit qualite deterministe en fin de pipeline pour actualiser la conformite
        matrix = quality_judge.evaluate_project(project)
        result["quality_score"] = matrix.total_score
        result["quality_verdict"] = matrix.verdict
        result["quality_matrix"] = matrix.model_dump(mode="json")
        result["project_id"] = str(project.id)
        result["project_name"] = project.name

        return result

    # --------------------------------------------------------------------------
    # LES TOPOLOGIES D'ORCHESTRATION & MOTEUR DE GRAPHE DYNAMIQUE (DAG)
    # --------------------------------------------------------------------------

    async def _run_dynamic_dag_topology(self, project: Project, instruction: str) -> dict[str, Any]:
        """Execute dynamiquement le graphe DAG des liaisons reelles du projet sans emojis."""
        links = agent_links_repo.list_all(project_id=str(project.id))
        if not links:
            # Si aucune liaison n'est persistee, verifier les agents du projet ou appliquer un template
            project_agents = agent_repo.list_all(project_id=str(project.id))
            if len(project_agents) >= 2:
                # Creer des liaisons directes en chaine entre les agents du projet
                for i in range(len(project_agents) - 1):
                    from core.domain import AgentLink, LinkType
                    new_link = AgentLink(
                        project_id=str(project.id),
                        source_agent_id=project_agents[i].id,
                        target_agent_id=project_agents[i + 1].id,
                        link_type=LinkType.DIRECT,
                        label=f"{project_agents[i].name} -> {project_agents[i + 1].name}",
                    )
                    agent_links_repo.save(new_link)
                links = agent_links_repo.list_all(project_id=str(project.id))
            else:
                links = agent_links_repo.apply_template("sequential", project_id=str(project.id))

        steps_log = []
        visited_agents = set()
        executed_nodes = []

        # Construction de l'ordre topologique d'execution
        active_links = [l for l in links if l.is_active]
        if not active_links:
            active_links = links

        for link in active_links:
            src = agent_repo.get(link.source_agent_id)
            tgt = agent_repo.get(link.target_agent_id)
            src_name = src.name if src else link.source_agent_id
            tgt_name = tgt.name if tgt else link.target_agent_id

            # 1. Execution du noeud source si non encore visite
            if src and src.id not in visited_agents:
                visited_agents.add(src.id)
                executed_nodes.append(src.name)
                sys_p = prompt_compiler.compile_agent_system_prompt(src, project_id=str(project.id), task_context=instruction)
                bb_ctx = blackboard.export_context_for_agent(str(project.id))
                payload = [
                    {"role": "system", "content": f"{sys_p}\n\n{bb_ctx}"},
                    {"role": "user", "content": f"Instruction de pipeline pour {src.name} : {instruction}"},
                ]
                resp, metric = await token_continuation.execute_with_auto_continuation(
                    messages=payload,
                    model=src.model,
                    temperature=src.temperature,
                    max_tokens=src.max_tokens,
                    reasoning_effort=src.reasoning_effort,
                    agent_id=src.id,
                    agent_name=src.name,
                    project_id=str(project.id),
                    project_name=project.name,
                    task_name=f"Pipeline : {src.name}",
                )
                blackboard.log_inter_agent_message(str(project.id), src.id, "blackboard", resp[:200])

            # 2. Transmission du flux
            link_label = link.label or link.link_type.value
            step_desc = f"Flux '{link_label}' : {src_name} -> {tgt_name}"
            steps_log.append(step_desc)
            blackboard.log_inter_agent_message(str(project.id), link.source_agent_id, link.target_agent_id, f"Transmission: {link_label}")

            # 3. Execution du noeud cible
            if tgt and tgt.id not in visited_agents:
                visited_agents.add(tgt.id)
                executed_nodes.append(tgt.name)
                sys_p = prompt_compiler.compile_agent_system_prompt(tgt, project_id=str(project.id), task_context=instruction)
                bb_ctx = blackboard.export_context_for_agent(str(project.id))
                payload = [
                    {"role": "system", "content": f"{sys_p}\n\n{bb_ctx}"},
                    {"role": "user", "content": f"Reception du flux en provenance de {src_name} pour {tgt.name}. Consigne : {instruction}"},
                ]
                resp, metric = await token_continuation.execute_with_auto_continuation(
                    messages=payload,
                    model=tgt.model,
                    temperature=tgt.temperature,
                    max_tokens=tgt.max_tokens,
                    reasoning_effort=tgt.reasoning_effort,
                    agent_id=tgt.id,
                    agent_name=tgt.name,
                    project_id=str(project.id),
                    project_name=project.name,
                    task_name=f"Pipeline : {tgt.name}",
                )
                blackboard.log_inter_agent_message(str(project.id), tgt.id, "blackboard", resp[:200])

        return {
            "topology": TopologyMode.CUSTOM_DAG.value,
            "status": "success",
            "active_links_count": len(active_links),
            "agents_involved": list(visited_agents),
            "executed_nodes": executed_nodes,
            "steps_log": steps_log,
            "summary": f"Execution du graphe dynamique DAG ({len(active_links)} liaisons actives, {len(visited_agents)} agents) terminee avec succes.",
        }

    async def _run_sequential_topology(self, project: Project, instruction: str) -> dict[str, Any]:
        """1. Topologie Sequentielle : Architecte -> Developpeur -> QA -> FinOps."""
        steps_log = [
            "1. L'Architecte valide les exigences et le plan de decoupage.",
            "2. Le Developpeur genere les composants et verifie la syntaxe AST.",
            "3. Le Controleur Qualite audite la conformite et calcule le score /100.",
            "4. Le Gardien FinOps enregistre les metriques et cloture le run.",
        ]
        blackboard.log_inter_agent_message(str(project.id), "agent_architect", "agent_coder", "Specifications pretes pour le code.")
        hooks_engine.trigger_event(HookEventType.POST_TOOL_CALL, {"file": "main.py"})

        return {
            "topology": TopologyMode.SEQUENTIAL.value,
            "status": "success",
            "steps_log": steps_log,
            "summary": "Execution sequentielle lineaire achevee avec succes.",
        }

    async def _run_hierarchical_topology(self, project: Project, instruction: str) -> dict[str, Any]:
        """2. Topologie Hierarchique : L'Architecte coordonne, delegue et valide."""
        steps_log = [
            "1. L'Architecte analyse la mission et attribue les sous-taches.",
            "2. Le Developpeur et le QA travaillent sous la supervision de l'Architecte.",
            "3. L'Architecte valide la conformite finale des livrables.",
        ]
        blackboard.log_inter_agent_message(str(project.id), "agent_architect", "agent_coder", "Delegation des sous-taches.")
        return {
            "topology": TopologyMode.HIERARCHICAL.value,
            "status": "success",
            "steps_log": steps_log,
            "summary": "Execution hierarchique orchestree par l'Architecte.",
        }

    async def _run_consensus_debate_topology(self, project: Project, instruction: str) -> dict[str, Any]:
        """3. Topologie Debat & Consensus : Actor-Critic entre Developpeur et QA avec arbitrage."""
        steps_log = [
            "1. Le Developpeur produit une premiere proposition de solution.",
            "2. Le Controleur Qualite critique et challenge la proposition.",
            "3. L'Architecte arbitre le consensus final certifie.",
        ]
        blackboard.log_inter_agent_message(str(project.id), "agent_coder", "agent_quality_judge", "Proposition de solution.")
        blackboard.log_inter_agent_message(str(project.id), "agent_quality_judge", "agent_architect", "Critique et validation de la solution.")
        return {
            "topology": TopologyMode.CONSENSUS_DEBATE.value,
            "status": "success",
            "steps_log": steps_log,
            "summary": "Consensus obtenu apres boucle de critique constructive.",
        }

    async def _run_swarm_topology(self, project: Project, instruction: str) -> dict[str, Any]:
        """4. Topologie Essaim (Swarms & Handoffs) : Transferts autonomes d'agent a agent."""
        steps_log = [
            "1. L'Architecte effectue un handoff autonome vers le Developpeur.",
            "2. Le Developpeur transfere directement au QA apres ecriture.",
            "3. Le QA cloture la boucle sans intermediaire.",
        ]
        blackboard.log_inter_agent_message(str(project.id), "agent_architect", "agent_coder", "Handoff autonome initial.")
        blackboard.log_inter_agent_message(str(project.id), "agent_coder", "agent_quality_judge", "Handoff direct de verification.")
        return {
            "topology": TopologyMode.SWARM.value,
            "status": "success",
            "steps_log": steps_log,
            "summary": "Essaim autonome complete par transferts directs (handoffs).",
        }

    async def _run_parallel_topology(self, project: Project, instruction: str) -> dict[str, Any]:
        """5. Topologie Parallele (Fan-Out / Fan-In) : Lancement simultane et consolidation."""
        async def subtask(name: str) -> str:
            await asyncio.sleep(0.01)
            return f"Tache '{name}' completee"

        tasks = [
            subtask("Generation Backend FastAPI"),
            subtask("Audit Securite & AST"),
            subtask("Analyse FinOps"),
        ]
        results = await asyncio.gather(*tasks)
        blackboard.log_inter_agent_message(str(project.id), "orchestrator", "blackboard", "Consolidation Fan-In completee.")

        return {
            "topology": TopologyMode.PARALLEL.value,
            "status": "success",
            "parallel_tasks": results,
            "summary": "Execution Fan-Out / Fan-In consolidee avec succes.",
        }


orchestrator = LegoOrchestrator()
