# Standard Universel de Conception du RAG & des Leçons Apprises (Pilier 6)

## 1. Cadre Général & Règle d'Or
Le Pilier RAG & Mémoire Évolutive assure deux missions critiques :
1. **Base de Connaissances SOTA (BM25 / FTS5)** : Indexation et restitution lexicale ultrarapide des concepts d'architecture, des spécifications d'API et des playbooks.
2. **Capitalisation Déterministe d'Erreurs (Lessons Learned)** : Enregistrement de chaque erreur commise et corrigée par les agents, avec synthèse de la cause racine et méthode de prévention.

## 2. Structure d'une Leçon Apprise (Memory Feedback Loop)
Toute leçon apprise doit respecter le contrat de données suivant :
```json
{
  "id": "lesson_unique_id",
  "scope": "global | project",
  "project_id": null,
  "topic": "Sujet technique précis (ex: SQLite Concurrency Locks)",
  "error_pattern": "Signature exacte de l'erreur observée",
  "root_cause": "Explication technique de la cause racine",
  "prevention_guideline": "Directive claire pour empêcher la récidive",
  "status": "active",
  "promoted_to_rule_id": null
}
```

## 3. Protocole de Promotion vers une Règle Active
Lorsqu'une erreur réapparaît ou présente un risque critique de régression :
1. L'Agent Contrôleur Qualité ou l'opérateur humain déclenche la conversion de la leçon en **Règle Active (`rules/<nom_regle>.md`)**.
2. La nouvelle règle est immédiatement compilée dans la base SQLite et injectée dans le prompt des agents concernés via le Prompt Compiler.
3. La boucle d'apprentissage continu est ainsi bouclée sans réentraînement du modèle.

## 4. Règles d'Or de Qualité
- Zéro leçon vague ou anecdotique : seules les erreurs de logique, de concurrence, de sécurité ou de conformité d'architecture sont enregistrées.
- Zéro emoji dans les leçons apprises et la base de connaissances.
