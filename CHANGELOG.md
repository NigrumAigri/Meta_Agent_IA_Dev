# Journal des Modifications (CHANGELOG) — Meta Developer Agent

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier, conformément aux principes de [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/) et du [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [5.0.1] - 2026-09-01

### 🚀 Améliorations & Nouvelles Fonctionnalités
- **Facturation FinOps 100% Réelle OpenRouter (`services/openrouter_client.py`)** :
  - Extraction directe du champ `usage["cost"]` renvoyé par OpenRouter au centième de centime près, éliminant tout décalage entre la plateforme locale et le tableau de bord OpenRouter.
  - Support de `stream_options: {"include_usage": True}` en streaming SSE pour capter les métriques réelles de tokens et de coût en direct.
  - Découpage visuel enrichi et déterministe des jetons : Total exact, <span style="color:#60A5FA">↓ In</span>, <span style="color:#A78BFA">↑ Out pur</span> (déduction des tokens de réflexion) et <span style="color:#F43F5E">🧠 Reasoning</span> (icône cerveau).
  - Élimination du double comptage des tokens de réflexion dans le calcul du total.
  - Épuration de la topbar : retrait du compteur flottant de dépenses (`#topbar-cost-display`) pour une interface plus épurée et sans redondance, avec accès direct conservé au Centre des Dépenses.
  - Correction du filtrage multi-projets dans le Centre des Dépenses avec réinjection de `project_id`.
  - Suppression de l'enregistrement de fausses transactions en cas de repli local hors-ligne.
- **Affichage Panoramique Plein Écran & Masquage Automatique de la Barre Droite sur le Budget (`static/index.html`)** :
  - Masquage contextuel automatique de la barre latérale droite (`.side-r.view-hidden`) lors de la navigation vers le Centre des Dépenses & Suivi Budgétaire (`view-finops-global`).
  - Élimination totale de la confusion visuelle entre les métriques du dernier projet actif et le grand livre multi-projets.
  - Attribution de 100% de la largeur de l'écran au tableau des transactions et aux cartes KPI (idéal pour le mode écran scindé en 2).
  - Restauration instantanée et transparente de la barre latérale droite dès le retour sur le Chat Projet, le Canvas Projet ou l'Explorateur de Code.
- **Audit & Alignement Télémétrique de la Barre Latérale Droite (`api/routes/finops.py`, `static/index.html`)** :
  - Élimination de la confusion historique entre Reasoning et Cache : `/finops/analytics` sépare désormais strictement `total_reasoning_tokens` et `total_cached_tokens`.
  - Intégration d'une ligne dédiée `Raisonnement (Thinking)` (`#tk-reasoning`) avec logo SVG cerveau vectoriel (`#F43F5E`).
  - Refonte du badge de cache en `Taux de cache (Prompt)` affichant les tokens et le pourcentage réel (`0 (0.0%)`), avec logo SVG éclair vectoriel (`#10B981`).
  - Correction du libellé `Latence TTFT` clarifié en `Latence moyenne` pour correspondre à la latence totale réelle de réponse.
  - Synchronisation du plafond budgétaire dans `projects_data` (`budget_limit_usd`), résolvant l'affichage `$ 0.0000` de la Carte 4 pour correspondre parfaitement au budget réel du projet.
  - Logos vectoriels SVG intégrés sur 100% des métriques de la barre latérale sans aucun emoji.
- **Télémétrie Cache Rate OpenRouter & Logos SVG 100% Sans Emoji (`services/openrouter_client.py`, `core/domain.py`, `storage/`, `api/routes/finops.py`, `static/index.html`)** :
  - Extraction native de `usage.prompt_tokens_details.cached_tokens` depuis les réponses OpenRouter et persistance dans `finops_ledger`.
  - Calcul et affichage dynamique du **Cache Rate à 3 niveaux** :
    - **Par Ligne** : Pourcentage exact de tokens en cache par inférence dans le Journal d'Audit (`Cache: XX.X%`).
    - **Par Projet** : Taux de cache consolidé propre au projet sélectionné (`p_cache_rate`).
    - **Global** : Taux d'optimisation global de toute l'infrastructure (`global_cache_rate`).
  - Éradication totale des emojis dans toute la vue FinOps/Budget, remplacés intégralement par des icônes vectorielles SVG (flèches In/Out, cerveau vectoriel pour Reasoning, éclair pour Cache).
  - Optimisation responsive spéciale **écran scindé en deux (Split Screen ~960px)** : `flex-wrap: wrap` sur les métriques de cartes KPI, `min-width: 820px` et défilement horizontal fluide sur le grand livre évitant tout chevauchement ou rupture visuelle.
- **Typologie FinOps & Séparation Stricte Meta-Concepteurs vs Agents Projet (`api/routes/finops.py`, `static/index.html`)** :
  - Ajout d'une colonne dédiée `Typologie` dans le Journal d'Audit des Inférences IA pour distinguer instantanément les inférences des 6 Méta-Agents (`Meta-Concepteur`) de celles des sous-agents du projet (`Agent Projet`), dans un design sobre et 100% sans emoji.
  - Simplification de l'intitulé de colonne `Projet / Studio` ramené proprement à `Projet`.
  - Retrait de `Studio & Inception Globale (Hors Projets)` du menu déroulant des projets pour ne conserver que la liste des vrais projets opérationnels.
  - Ajout du filtre multi-critères `Typologie` et affichage du sous-total en temps réel (`Meta: $ X.XXXX · Proj: $ Y.YYYY`).
- **Architecture à 4 Calques Stricts & Résolution Totale des Superpositions sur le Canvas 2D (`static/index.html`)** :
  - **Calque 1 (Fond, `z-index: 1`)** : Câbles et flux SVG (`#wires`) sur le plancher du canvas.
  - **Calque 2 (Liaisons, `z-index: 5`)** : Badges de liaisons (`#wire-badges`) et symboles de hiérarchie (`⇣`, `→`, molette, croix) placés strictement SOUS les cartes.
  - **Calque 3 (Cartes Agents, `z-index: 10 à 30`)** : Cartes (`#nodes`, `.node`) avec fond opaque `var(--panel)` et `isolation: isolate;`, recouvrant intégralement les câbles et badges d'arrière-plan sans aucun transpercement de points ou d'icônes.
  - **Calque 4 (Interaction & Tirage, `z-index: 70`)** : Câble interactif en cours de création (`#wires-draft-svg`) survolant les cartes lors du glisser-déposer.
  - Réordonnancement DOM temps réel (`appendChild`) et élévation dynamique (`state.canvasMaxZIndex`) de la carte manipulée au premier plan absolu.
- **Standard Universel de Conception d'Agents IA (`rules/standard_conception_agent_profile.md`)** :
  - Intégration de la synthèse exhaustive des **13 modules de la Base de Connaissances RAG** en un contrat d'exécution impératif et généraliste.
  - Typologie universelle des intentions cognitives (Déterministe stricte, Analyse critique, Cadrage stratégique, Conversation support, Créativité).
  - Grammaire XML en 5 blocs délimités (`<role_and_identity>`, `<operational_protocol>`, `<output_specifications>`, `<strict_guardrails>`, `<tooling_and_collaboration>`).
  - Grille de validation en 12 points de contrôle pour l'audit automatique des sous-agents.
  - Synchronisation et indexation automatique dans la table SQLite `rules_index`.

---

### 🐛 Corrections de Bugs & Résilience
- **Résolution Dynamique JIT des Clés API (`core/config.py`, `services/openrouter_client.py`, `api/routes/config.py`)** :
  - Élimination de la désynchronisation mémoire vive (RAM) vs SQLite : les clés API enregistrées en base sont détectées et utilisées instantanément sans redémarrage serveur.
  - Ajout des méthodes `get_llm_api_key()` et `get_aa_api_key()` pour une résolution dynamique transparente à la volée.
  - Correction de l'endpoint `POST /api/v1/config/test-connection` : teste automatiquement la clé enregistrée en base si le champ du formulaire est masqué (`••••••••`).
- **Ingestion Pure & Déterministe des Benchmarks AA (`services/benchmarks_client.py`)** :
  - Éradication totale du matching flou sur les slugs de modèles (`or_pricing_map`).
  - Extraction 100% directe des prix et métriques certifiées depuis le payload officiel d'Artificial Analysis.
  - Rétablissement des vrais prix constructeurs (`GLM-5.3 Max` à In: \$1.40 / Out: \$4.40 vs `GLM-5.3 Flash` à In: \$0.15 / Out: \$0.50).
- **Tolérance aux Métriques Optionnelles (`core/domain.py`)** :
  - Mise à jour du schéma Pydantic `BenchmarkRecord.evaluations` en `dict[str, float | None]` pour tolérer les scores `null` renvoyés par l'API externe.

---

### 🧪 Tests & Certification
- **Suite de Tests Complète** : **114 / 114 tests réussis (100% PASS)** en 4.5s.
- **Conformité Clean Architecture** : Zéro hardcoding, isolation hermétique multi-projets, respect des 7 Piliers Agentiques.

---

## [5.0.0] - 2026-08-31

### 🎉 Version Initiale v5.0.0 Enterprise Command Center
- Architecture Bi-Niveau (Méta-Agents v5 ➔ Sous-Agents de projets isolés).
- Command Center interactif avec Canvas 2D DAG, Chat SSE temps réel et Explorateur de code.
- Les 7 Piliers Agentiques (MCP Hub, Skills RAG JIT, Rules Directives, Hooks Sentinelles, Slash Commands, Mémoire Épisodique & Lessons, Checkpoints & Time Travel).
- Moteur FinOps avec disjoncteur budgétaire à 90% et isolation SQLite WAL.
