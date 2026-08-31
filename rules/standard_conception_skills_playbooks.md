# Standard Universel de Conception des Skills & Playbooks (Pilier 2)

## 1. Cadre Général & Règle d'Or
Tout Skill (compétence technique spécialisée) créé par les Méta-Agents, le Tool-Maker ou les agents de projets doit impérativement respecter le protocole de **Divulgation Progressive en 3 Niveaux** (Niveau 1: Résumé au repos, Niveau 2: Instructions JIT `SKILL.md`, Niveau 3: Ressources & Scripts).

## 2. Structure Physique Obligatoire
Chaque compétence réside dans un dossier dédié sous `skills/<nom_skill>/` :
```text
skills/<nom_skill>/
├── SKILL.md          # Requis : Frontmatter YAML + Playbook Markdown
├── examples/         # Optionnel : Fichiers d'exemples complets
└── scripts/          # Optionnel : Utilitaires de validation ou scaffolding
```

## 3. Spécification Strict du Frontmatter YAML
Le fichier `SKILL.md` doit débuter par un en-tête YAML délimité par `---` :
```yaml
---
name: nom_du_skill_en_snake_case
description: Résumé précis de la mission ET des déclencheurs concrets d'activation pour le Skill RAG.
version: 1.0.0
tags: [mot_cle1, mot_cle2, mot_cle3, tag_technique]
---
```

## 4. Les 4 Sections Obligatoires du Playbook Markdown
1. **## 1. Mission & Périmètre d'Application** : Rôle exact de la compétence et cas d'usage précis.
2. **## 2. Directives Fondamentales & Anti-Patterns Interdits** :
   - Règles d'or strictes (Clean Code, PEP8, immutabilité, sécurité).
   - Interdictions formelles (pas de code tronqué, pas de mot de passe en clair, pas d'injection SQL).
3. **## 3. Implémentation de Référence de Production** :
   - Code Python complet, 100% typé avec Pydantic v2, zéro raccourci (`// TODO`), zéro code tronqué.
4. **## 4. Checklist de Validation Déterministe** :
   - Grille de vérification en 3 à 5 points que l'agent audite avant de valider son travail.

## 5. Règle d'Or de Qualité
- Zéro emoji dans les fichiers de skills.
- Zéro dépendance cachée ou non déclarée.
- Zéro approximation ou code d'attente (`pass`, `...`).
