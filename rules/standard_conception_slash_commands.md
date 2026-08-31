# Standard Universel de Conception des Slash Commands (Pilier 4)

## 1. Cadre Général & Règle d'Or
Toute Slash Command (commande rapide débutant par `/`) sert de court-circuit déterministe côté orchestrateur et interface utilisateur. Son exécution doit s'opérer en **Python pur à coût 0 token LLM** et répondre en moins de 10 millisecondes.

## 2. Déclaration Physique & Zéro Hardcoding
Toute commande doit être enregistrée dans le fichier déclaratif `data/commands.json` (ou `.commands/commands.json` pour un périmètre de projet local) selon la structure JSON suivante :
```json
{
  "id": "cmd_nom_unique",
  "command": "/nom_commande",
  "name": "Nom Explicite en Français",
  "description": "Description claire de l'action exécutée.",
  "usage": "/nom_commande [argument_optionnel] <argument_obligatoire>",
  "category": "Inception & Cadrage | Modèles & Benchmarks | Qualité & Audit | Mémoire & Checkpoints | Production & Déploiement | FinOps & Budget | Orchestration & Workflow",
  "handler_type": "native",
  "target": "nom_du_handler_python",
  "scope": "global",
  "is_active": true
}
```

## 3. Les 4 Règles Fondamentales d'Exécution Déterministe
1. **Économie Maximale (0 Token)** :
   - Une slash command ne doit jamais appeler un LLM inutilement pour une tâche réalisable algorithmiquement (ex: bilan FinOps, calculs, audits AST, rollback de snapshot, export ZIP).
2. **Support Robuste des Arguments** :
   - Le gestionnaire (`handler`) doit extraire et valider rigoureusement ses arguments (ex: `/budget 30`, `/match code`, `/rollback ck_1234`).
   - En cas d'argument absent ou invalide, un message d'aide pédagogique rappelant la syntaxe `usage` doit être renvoyé.
3. **Formatage Markdown Riche** :
   - La réponse doit être structurée avec titres, listes et blocs de code pour une lisibilité parfaite dans l'interface de discussion.
4. **Non-Régression & Isolation** :
   - Les commandes manipulant l'état du projet (ex: `/clear`, `/rollback`, `/budget`) doivent opérer de façon hermétique sur le `project_id` ciblé sans affecter les autres espaces de travail.

## 4. Règle d'Or de Qualité
- Zéro emoji dans les réponses système des commandes.
- Zéro dépendance bloquante ou appel réseau externe non supervisé.
- Traitement strict des exceptions pour garantir 100% de disponibilité de l'interface.
