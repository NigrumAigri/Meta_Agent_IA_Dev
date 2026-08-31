# Standard Universel de Conception des Outils & Serveurs MCP (Pilier 1)

## 1. Cadre Général & Standard MCP
Tout outil (Tool) ou ressource (Resource) intégré à la plateforme ou créé dynamiquement par le moteur **Tool-Maker** doit respecter la spécification **Model Context Protocol (MCP)** et le Module 5 de la Knowledge Base.

## 2. Anatomie d'un Outil Déclaratif MCP
Chaque outil doit être déclaré avec les 5 attributs obligatoires suivants :
1. **`id`** : Identifiant unique strict en `snake_case` (ex: `document_extractor`, `math_calculator`).
2. **`name`** : Titre explicite et lisible pour l'humain et l'agent.
3. **`description`** : Rédaction obligatoire en **4 Clauses Structurées** :
   - `[Mission]` : Ce que fait l'outil de manière déterministe.
   - `[Déclencheur]` : Quand et dans quelle situation l'agent DOIT l'activer.
   - `[Interdiction]` : Ce que l'outil ne fait pas et les anti-patterns banni.
   - `[Résultat]` : La structure exacte des données renvoyées.
4. **`parameters_schema`** : Schéma JSON Schema strict avec typage exhaustif, descriptions des champs et liste `required`.
5. **`mcp_primitive`** : Déclaration de la primitive MCP (`tool`, `resource` ou `prompt`).

## 3. Gardes-Fous d'Exécution & Sécurité
- **Troncature Universelle des Sorties** : Tout retour d'outil dépassant 8 000 caractères doit être tronqué avec résumé structuré pour protéger la fenêtre de contexte.
- **Cache Idempotent** : Les outils en lecture seule ou purement mathématiques (`is_idempotent = True`) doivent être mis en cache (TTL 15 min).
- **Isolation Sandboxing Docker Obligatoire** : Tout outil exécutant du code Python/Shell non vérifié (`test_runner_sandbox`) doit être exécuté dans un conteneur Docker éphémère étanche (`--network none`, `--rm`, 512MB RAM).
- **Zéro Écriture Corrompue** : Toute écriture sur disque doit utiliser le pattern d'écriture atomique avec vérification préalable de la syntaxe AST.
- **Zéro Calcul Mental** : Tout calcul mathématique ou dimensionnement doit être délégué à `math_calculator` ou `finops_calculator`.

## 4. Protocole de Transport MCP
- **Serveurs Locaux** : Communication bidirectionnelle par flux standard `stdio` (JSON-RPC 2.0).
- **Serveurs Distants** : Communication par Server-Sent Events (`SSE`) et requêtes HTTP POST sécurisées.
