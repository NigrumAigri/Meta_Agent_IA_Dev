# Standard Universel de Conception des Hooks & Sentinelles (Pilier 5)

## 1. Cadre Général & Règle d'Or
Un Hook (Sentinelle du cycle de vie) est un intercepteur déterministe synchrone ou asynchrone qui s'exécute automatiquement avant ou après une action critique de l'agent (avant l'exécution d'un outil MCP, avant l'écriture disque d'un fichier de code, après une inférence LLM, ou lors d'un dépassement de budget). Son exécution s'opère en **0 coût token LLM** et peut **bloquer, modifier ou consigner** l'opération en cours.

## 2. Déclaration Physique & Zéro Hardcoding
Toute sentinelle doit être déclarée dans `data/hooks.json` (pour les sentinelles globales) ou `projects/<projet>/hooks.json` (pour les sentinelles locales d'un sous-projet) selon la structure JSON suivante :
```json
{
  "id": "hook_nom_unique",
  "name": "Nom Explicite de la Sentinelle",
  "event_type": "pre_tool_call | post_tool_call | pre_code_write | post_llm_inference | on_finops_breach",
  "action_type": "security_validator | ast_validator | finops_circuit_breaker | snapshot_creator | telemetry_logger",
  "target": "target_tool_ou_wildcard_*",
  "config": {
    "blocking": true,
    "max_retries": 3,
    "max_cost_usd": 5.0
  },
  "scope": "global",
  "is_active": true
}
```

## 3. Les 4 Règles Fondamentales des Sentinelles
1. **Déterminisme & Vitesse Maximale (< 5 ms)** :
   - Une sentinelle ne fait aucun appel LLM. Elle utilise des parseurs déterministes (ex: `ast.parse` pour valider du Python, expressions régulières pour bloquer des chemins `../../`, calcul arithmétique pour FinOps).
2. **Gestion du Verdict (Autoriser / Bloquer)** :
   - Si la sentinelle est configurée en `blocking: true` et qu'une violation est détectée, l'opération est immédiatement interrompue et un message explicite est retourné à l'agent pour qu'il corrige son tir.
3. **Piste d'Audit & Journalisation Immuable** :
   - Chaque exécution de sentinelle consigne une entrée dans la table `hooks_audit_log` (durée en millisecondes, statut, payload et erreur éventuelle).
4. **Héritage par les Sous-Projets** :
   - Les Méta-Agents peuvent équiper un sous-projet de ses propres sentinelles locales (ex: `pre_payment_validator` pour une application e-commerce).

## 4. Règle d'Or de Qualité
- Zéro effet de bord non capturé dans l'exécution des sentinelles.
- Zéro exception non gérée : le gestionnaire de hooks doit garantir la haute disponibilité de la plateforme.
