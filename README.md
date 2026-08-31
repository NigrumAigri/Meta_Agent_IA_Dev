# 🚀 Meta Developer Agent v5.0.0 — Enterprise Edition

**Plateforme d'Ingénierie Multi-Agents, Command Center 3 Volets & Gouvernance FinOps**

---

## 🌟 Présentation
**Meta Developer Agent v5.0.0** est une plateforme logicielle d'élite permettant de cadrer, architecturer, développer et tester des applications logicielles complexes en s'appuyant sur des équipes de Méta-Agents autonomes (Architecte Lead, Développeur Senior Full-Stack, Contrôleur Qualité, Gardien FinOps et Copilote Système).

### 🛡️ Points Forts & Garanties Entreprise
- **Architecture Conteneurisée & Sécurisée** : Déploiement en 1-clic via Docker Compose avec utilisateur non-root (`appuser`), isolation hermétique et sandboxing des exécutions.
- **Persistance & Intégrité Transactionnelle** : Base de données SQLite en mode WAL (`meta_agent.db`) avec 31 tables/index relationnels et transactions atomiques `BEGIN IMMEDIATE`.
- **Les 7 Piliers Agentiques Complets** : Hub MCP Universel (14 outils), Compétences Skills JIT (YAML frontmatter), Règles Modulaires, Sentinelles Hooks de sécurité, 10 Commandes Slash déterministes à 0 token, Mémoire RAG FTS5 + BM25 et 5 Topologies Multi-Agents Lego.
- **Gouvernance FinOps & Benchmarks** : Télémétrie en temps réel ($), disjoncteur budgétaire anti-emballement, détection d'économies de prompt-caching (-90%) et 19 benchmarks certifiés Artificial Analysis.
- **Ergonomie Moderne & Multi-Plateforme** : Compatible Windows, macOS (Intel & Apple Silicon M1/M2/M3/M4 ARM64) et Linux.

---

## 🚀 Démarrage Rapide (Pour Vos Clients)

### Option 1 : Démarrage en 1-Clic via Docker (Recommandé)

Aucune installation de Python n'est requise. Seul **Docker Desktop** est nécessaire.

#### 🪟 Sur Windows :
Double-cliquez simplement sur **`start.bat`**.
*Le script vérifie Docker, démarre le conteneur sécurisé et ouvre automatiquement l'application dans votre navigateur web.*

#### 🍎 Sur macOS / 🐧 Sur Linux :
Exécutez dans un terminal :
```bash
./start.sh
```

L'application s'ouvre instantanément sur **`http://localhost:8000`**.

---

### Option 2 : Démarrage en Local avec Poetry (Développeurs)

#### Prérequis :
- Python `>=3.10` et `poetry` (`pip install poetry`).

#### Installation & Lancement :
```bash
# 1. Installation des dépendances avec verrouillage déterministe
poetry install

# 2. Lancement du serveur d'orchestration
poetry run python run.py
```

---

## ⚙️ Configuration & Personnalisation (.env)

L'application est prête à l'emploi sans configuration complexe. La clé API OpenRouter et le choix des modèles LLM se configurent **directement depuis l'interface web (Modale Paramètres ⚙️)**.

Si vous souhaitez ajuster les réglages d'infrastructure (port, mémoire), vous pouvez éditer le fichier `.env` :

```env
# Port d'écoute web (par défaut 8000 -> http://localhost:8000)
APP_PORT=8000

# Allocation dynamique des ressources Docker (s'adapte à votre PC)
DOCKER_MEM_LIMIT=4g
DOCKER_CPUS=4.0
```

---

## 🧪 Tests de Non-Régression & Certification

Pour exécuter l'intégralité de la suite de tests automatisés (114 tests validés à 100%) :

```bash
# En local avec Poetry :
poetry run pytest tests -v

# Ou avec Docker :
docker compose exec meta-agent-dev pytest tests -v
```

---

## 📂 Structure du Projet

```text
Meta_Agent_Dev_V5/
├── api/               # Routes FastAPI & Contrats Pydantic v2
├── core/              # Domaine métier, Clean Architecture & Configuration
├── data/              # Base SQLite WAL, Agents natifs et Index déclaratifs
├── hooks/             # Sentinelles de sécurité et cycle de vie
├── output_projects/   # Dossier hermétique des projets clients générés
├── rules/             # Règles modulaires dynamiques
├── services/          # Les 7 Piliers Agentiques & Orchestrateur Multi-Agents
├── skills/            # Compétences JIT (Playbooks SKILL.md)
├── static/            # Interface IHM SPA Command Center 3 Volets
├── storage/           # Repository SQLite transactionnel
├── tests/             # Suite complète de tests unitaires et E2E
├── docker-compose.yml # Orchestration Docker multi-plateforme
├── Dockerfile         # Image multi-stage légère et sécurisée non-root
├── pyproject.toml     # Définition Poetry standardisée
├── start.bat          # Lanceur 1-clic pour Windows
└── start.sh           # Lanceur 1-clic pour macOS et Linux
```

---

© 2026 Meta Developer Agent. Tous droits réservés. Version Entreprise 5.0.0.

