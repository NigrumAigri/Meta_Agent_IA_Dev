from __future__ import annotations

import logging

from core.domain import McpToolDefinition
from storage.repository import mcp_repo

logger = logging.getLogger(__name__)


class ToolRAGEngine:
    """Moteur de Routage et de Découverte Dynamique d'Outils (Tool RAG).
    
    Conforme au Module 5 §1.3.4 & §2.4.2 de la Knowledge Base :
    - Recherche plein-texte ultra-rapide SQLite FTS5.
    - Analyse d'intention et extraction sémantique des mots-clés.
    - Ajustement contextuel selon le rôle de l'agent et le projet.
    - Évite la surcharge cognitive du LLM en ne chargeant que 2 à 4 outils clés.
    """

    INTENT_KEYWORDS_MAP: dict[str, list[str]] = {
        "document_extractor": ["excel", "xlsx", "xls", "tableur", "csv", "cahier", "spec", "pdf", "feuille", "cellule", "slicing"],
        "math_calculator": ["calcul", "calculatrice", "calculette", "addition", "pourcentage", "tva", "formule", "somme", "arithmetique", "math", "multiplier", "diviser"],
        "finops_calculator": ["finops", "tokens", "prix", "cout", "depense", "facture", "tarif", "budget", "million"],
        "web_search_and_docs": ["recherche", "web", "internet", "google", "documentation", "docs", "en ligne", "api", "tutoriel", "derniere version"],
        "ast_validator": ["syntaxe", "ast", "erreur python", "valider code", "parse", "compilation"],
        "file_writer_atomic": ["ecrire fichier", "creer fichier", "sauvegarder", "enregistrer", "modifier code", "atomique"],
        "test_runner_sandbox": ["test", "pytest", "unitaire", "integration", "couverture", "sandbox", "docker"],
        "code_formatter": ["pep8", "formatter", "nettoyer code", "formatage", "black", "flake8"],
        "search_models_catalog": ["modele", "llm", "benchmark", "artificial analysis", "comparer modeles", "meilleur modele", "sweet spot", "top perf", "terminalbench", "gpqa"],
        "get_catalog_capabilities": ["metriques disponibles", "capacites catalogue", "liste benchmarks", "status sync"],
        "search_knowledge_base": ["knowledge base", "cours", "masterclass", "guide", "architecture", "bonnes pratiques", "normes"],
        "discover_tools": ["decouvrir outils", "chercher outils", "trouver outil", "trouver outils"],
        "read_skill": ["skill", "competence", "playbook", "charger playbook", "lire skill", "directives", "guide"],
        "discover_skills": ["trouver competence", "chercher skill", "decouvrir competence", "recherche playbook"],
    }

    ROLE_DEFAULT_TOOLS: dict[str, list[str]] = {
        "architect": ["search_knowledge_base", "document_extractor", "read_skill", "discover_tools"],
        "coder": ["ast_validator", "file_writer_atomic", "test_runner_sandbox", "read_skill", "discover_tools"],
        "quality_judge": ["ast_validator", "test_runner_sandbox", "math_calculator", "read_skill", "discover_tools"],
        "finops_guardian": ["finops_calculator", "math_calculator", "search_models_catalog", "discover_tools"],
        "model_matcher": ["search_models_catalog", "get_catalog_capabilities", "math_calculator", "discover_tools"],
        "copilot": ["search_knowledge_base", "web_search_and_docs", "read_skill", "discover_tools"],
    }

    def search_relevant_tools(
        self,
        query: str,
        agent_type: str | None = None,
        project_id: str | None = None,
        base_tool_ids: list[str] | None = None,
        limit: int = 5,
    ) -> list[McpToolDefinition]:
        """Sélectionne dynamiquement les outils les plus pertinents pour une requête donnée."""
        selected_tool_ids: list[str] = list(base_tool_ids or [])
        clean_query = query.lower().strip()

        # 1. Ajout des outils du rôle par défaut (ordre prioritaire)
        if agent_type and agent_type.lower() in self.ROLE_DEFAULT_TOOLS:
            for tid in self.ROLE_DEFAULT_TOOLS[agent_type.lower()]:
                if tid not in selected_tool_ids:
                    selected_tool_ids.append(tid)

        # 2. Détection d'intention par mots-clés sémantiques (Intent Mapping)
        for tool_id, keywords in self.INTENT_KEYWORDS_MAP.items():
            if any(kw in clean_query for kw in keywords):
                if tool_id not in selected_tool_ids:
                    selected_tool_ids.append(tool_id)

        # 3. Recherche FTS5 dans la base SQLite (outils globaux + projet)
        if clean_query:
            try:
                fts_tools = mcp_repo.search_tools_fts(query_text=clean_query, project_id=project_id, limit=limit)
                for t in fts_tools:
                    if t.id not in selected_tool_ids:
                        selected_tool_ids.append(t.id)
            except Exception as e:
                logger.warning("Erreur recherche Tool RAG FTS5: %s", e)

        # 4. Récupération des objets McpToolDefinition complets
        all_active_tools = {t.id: t for t in mcp_repo.list_tools(project_id=project_id, active_only=True)}
        
        results: list[McpToolDefinition] = []
        for tid in selected_tool_ids:
            if tid in all_active_tools:
                results.append(all_active_tools[tid])

        # Garantie universelle : tout agent (même nouvellement créé) dispose de discover_tools
        if "discover_tools" in all_active_tools and not any(t.id == "discover_tools" for t in results):
            results.append(all_active_tools["discover_tools"])

        # Si aucun outil n'a été détecté et qu'aucun outil de base n'existe, fournir la recherche knowledge base
        if not results and "search_knowledge_base" in all_active_tools:
            results.append(all_active_tools["search_knowledge_base"])

        return results


tool_rag = ToolRAGEngine()
