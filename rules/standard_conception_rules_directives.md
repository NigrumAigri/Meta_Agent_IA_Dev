# Standard Universel de Conception des Règles & Directives (Pilier 3)

## 1. Cadre Général & Règle d'Or
Une Règle (`Rule`) est une directive de gouvernance technique ou métier injectée dynamiquement dans le prompt système des agents (au niveau Méta ou au niveau des sous-agents de projet). Elle garantit l'alignement absolu sur les exigences de sécurité, de qualité, de syntaxe et de conformité légale (ex: RGPD, FinOps, Zéro Emoji, Clean Architecture).

## 2. Structure Physique & Emplacement
- **Règles Globales (Plateforme & Méta-Agents)** : Situées sous le dossier racine `rules/<nom_regle>.md`.
- **Règles Locales (Spécifiques à un Projet Client)** : Situées sous `projects/<nom_projet>/rules/<nom_regle>.md`.

Chaque fichier doit être au format Markdown pur (`.md`) sans superflu.

## 3. Les 4 Sections Obligatoires d'une Règle
Chaque fichier de règle doit comporter les sections suivantes :
1. **# Titre Explicite de la Règle** : Nom clair et objectif de la directive.
2. **## 1. Contexte & Périmètre d'Application** : Rôles ciblés (ex: Coder, Architecte, Agent de Facturation) et conditions d'application.
3. **## 2. Directives Strictes & Anti-Patterns Interdits** :
   - Liste des exigences impératives (ex: pas de clés API en clair, validation Pydantic v2 obligatoire).
   - Liste des comportements formellement proscrits.
4. **## 3. Exemple Conforme vs Exemple Non-Conforme** :
   - Illustration par des blocs de code comparatifs (`diff` ou blocs `python`/`json`).
5. **## 4. Pénalité ou Conséquence de Non-Respect** :
   - Impact sur l'évaluation du Juge Qualité (ex: rejet AST, pénalité de 20 points).

## 4. Règles d'Or de Qualité
- Zéro emoji dans les règles et directives techniques.
- Clarté chirurgicale et formulation impérative.
- Injection Just-In-Time (JIT) uniquement auprès des agents concernés pour préserver le budget de tokens.
