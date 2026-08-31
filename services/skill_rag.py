from __future__ import annotations

import logging

from core.domain import SkillDefinition
from storage.repository import skills_repo

logger = logging.getLogger(__name__)


class SkillRAGEngine:
    """Moteur de Routage et de Découverte Dynamique de Compétences (Skill RAG).
    
    Conforme au Pilier 2 (Skills JIT) & Module 2 de la Knowledge Base :
    - Recherche plein-texte ultra-rapide SQLite FTS5.
    - Analyse d'intention et extraction sémantique des mots-clés.
    - Ajustement contextuel selon le rôle de l'agent et le projet.
    - Divulgation progressive : n'injecte au repos que 2 à 3 compétences ciblées (~50-100 tokens).
    """

    INTENT_KEYWORDS_MAP: dict[str, list[str]] = {
        "fastapi_enterprise": [
            "api", "fastapi", "rest", "endpoint", "route", "routeur",
            "pydantic", "http", "crud", "payload", "backend", "webservice"
        ],
        "sqlite_wal_persistence": [
            "sqlite", "wal", "database", "bdd", "table", "sql",
            "migration", "persistance", "transaction", "db", "requete"
        ],
        "verification_architecture_hexagonale": [
            "hexagonal", "hexagonale", "ddd", "clean architecture", "ports",
            "adapters", "domaine", "decouplage", "separation", "architecture"
        ],
        "securite_tokens_jwt": [
            "jwt", "token", "auth", "authentification", "mot de passe",
            "hash", "argon2", "bcrypt", "securite", "access_token", "refresh_token", "connexion"
        ],
    }

    ROLE_DEFAULT_SKILLS: dict[str, list[str]] = {
        "architect": ["verification_architecture_hexagonale", "fastapi_enterprise"],
        "coder": ["fastapi_enterprise", "sqlite_wal_persistence"],
        "quality_judge": ["verification_architecture_hexagonale", "securite_tokens_jwt"],
        "finops_guardian": [],
        "copilot": ["fastapi_enterprise", "sqlite_wal_persistence"],
        "model_matcher": [],
    }

    def search_relevant_skills(
        self,
        query: str,
        agent_type: str | None = None,
        project_id: str | None = None,
        base_skill_names: list[str] | None = None,
        limit: int = 3,
    ) -> list[SkillDefinition]:
        """Sélectionne dynamiquement les compétences les plus pertinentes pour une requête donnée."""
        selected_skill_names: list[str] = list(base_skill_names or [])
        clean_query = query.lower().strip()

        # 1. Détection d'intention par mots-clés sémantiques (Intent Mapping prioritaire)
        for skill_name, keywords in self.INTENT_KEYWORDS_MAP.items():
            if any(kw in clean_query for kw in keywords):
                if skill_name not in selected_skill_names:
                    selected_skill_names.append(skill_name)

        # 2. Recherche FTS5 dans la base SQLite (skills globaux + projet)
        if clean_query:
            try:
                fts_skills = skills_repo.search_skills_fts(query_text=clean_query, project_id=project_id, limit=limit)
                for s in fts_skills:
                    if s.name not in selected_skill_names:
                        selected_skill_names.append(s.name)
            except Exception as e:
                logger.warning("Erreur recherche Skill RAG FTS5: %s", e)

        # 3. Complément par défaut selon le rôle de l'agent si peu de résultats trouvés
        if len(selected_skill_names) < limit and agent_type and agent_type.lower() in self.ROLE_DEFAULT_SKILLS:
            for s_name in self.ROLE_DEFAULT_SKILLS[agent_type.lower()]:
                if s_name not in selected_skill_names:
                    selected_skill_names.append(s_name)
                if len(selected_skill_names) >= limit:
                    break

        # 4. Récupération des objets SkillDefinition complets
        all_skills_map = {s.name: s for s in skills_repo.list_skills(project_id=project_id) if s.is_active}
        
        results: list[SkillDefinition] = []
        for name in selected_skill_names:
            if name in all_skills_map and all_skills_map[name] not in results:
                results.append(all_skills_map[name])
            if len(results) >= limit:
                break

        # Si aucun résultat spécifique n'a été sélectionné, renvoyer les premiers skills actifs dans la limite
        if not results:
            results = list(all_skills_map.values())[:limit]

        return results


# Singleton global Skill RAG
skill_rag = SkillRAGEngine()
