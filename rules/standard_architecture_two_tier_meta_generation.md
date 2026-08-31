# Standard d'Architecture Bi-Niveau : Génération de Sous-Agents par les Méta-Agents

## 1. Cadre & Définition de l'Architecture Bi-Niveau (Two-Tier Architecture)
La plateforme **Meta Developer Agent** opère selon une hiérarchie modulaire et extensible à deux niveaux :
- **Niveau 1 : Le Collectif des Méta-Agents (La Forge Logicielle Évolutive)** :
  * Équipe dynamique d'agents système spécialisés (Architecte, Développeur Logiciel, Contrôleur Qualité, Gardien FinOps, Copilote, Stratège Modèles, et tout futur agent expert ajouté à chaud).
  * Leur mission est de dialoguer avec l'opérateur humain, de cadrer le besoin, de concevoir l'architecture, d'écrire le code et d'instancier des **projets clients complets**.
- **Niveau 2 : Les Projets Clients & Leurs Sous-Agents (Les Applications Générées)** :
  * Chaque projet client généré (ex: SaaS Médical, Plateforme E-Commerce, Bot de Trading, API temps réel) contient ses propres **sous-agents métier**.
  * Ces sous-agents sont conçus pour opérer de façon 100% autonome et sécurisée dans leur environnement dédié.

---

## 2. Protocole d'Équipement des Sous-Agents par les Méta-Agents

Lorsqu'un Méta-Agent conçoit un sous-agent pour un projet client, il lui alloue dynamiquement les briques des **7 Piliers Agentiques** adaptées à sa mission :

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│              ÉQUIPEMENT DES SOUS-AGENTS GÉNÉRÉS (GRAMMAIRE DES 7 PILIERS)              │
│                                                                                        │
│ 1. Outils MCP Locaux    ──► Équiper l'agent des connecteurs API du projet (ex: Stripe) │
│ 2. Skills JIT           ──► Rédiger les Playbooks métiers dans `projects/<p>/skills/`   │
│ 3. Règles de Projet     ──► Définir les directives strictes dans `projects/<p>/rules/` │
│ 4. Slash Commands       ──► Déclarer les commandes rapides du sous-projet             │
│ 5. Sentinelles Hooks    ──► Configurer les disjoncteurs et gardes-fous d'exécution     │
│ 6. Mémoire RAG Locale   ──► Indexer la documentation et les leçons apprises du projet  │
│ 7. Topologie & Liens    ──► Câbler les communications entre les sous-agents            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Les 4 Règles d'Or de la Méta-Génération

1. **Isolation Hermétique Absolue** :
   - Les sous-agents d'un projet `A` ne peuvent en aucun cas exécuter les outils, lire la mémoire ou consommer le budget d'un projet `B`.
2. **Autonomie d'Exécution sans le Système Parent** :
   - L'archive ZIP exportée via `/export` ou l'API de déploiement doit contenir tous les fichiers (`main.py`, `requirements.txt`, `skills/`, `rules/`) pour que l'application générée et ses agents tournent de façon 100% indépendante.
3. **Allocation FinOps & Disjoncteur Dédié** :
   - Chaque sous-agent généré se voit attribuer un budget plafond (`budget_limit_usd`) et un modèle issu de l'analyse dynamique des benchmarks certifiés (`aa_benchmarks_cache`).
4. **Zéro Hardcoding dans les Prompts Générés** :
   - Les prompts système des sous-agents doivent être compilés dynamiquement avec les balises XML normalisées (`<role>`, `<guidelines>`, `<context>`).

---

## 4. Checklist de Validation pour les Méta-Agents
Avant de valider la livraison d'un projet client et de ses sous-agents, le Méta-Agent Contrôleur Qualité vérifie :
- [ ] Tous les sous-agents ont un rôle, un modèle et un quota FinOps valides.
- [ ] Les outils MCP du sous-projet sont testés et validés par le sandbox.
- [ ] Les règles de sécurité (chiffrement, sanitization SQL) sont physiquement créées dans le dossier du projet.
- [ ] L'application générée compile sans aucune erreur de syntaxe AST.
