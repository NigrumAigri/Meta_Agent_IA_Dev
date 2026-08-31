# Règle d'Or : Zéro Hardcoding, Zéro Fallback Dangereux, Scalable & Dynamique

1. **ZÉRO HARDCODING** :
   - Interdiction formelle d'écrire des valeurs statiques codées en dur (identifiants de modèles LLM, URLs fixes, credentials, chemins absolus locaux, constantes magiques, listes figées).
   - Toute donnée et paramètre doivent être résolus dynamiquement via la base de données SQLite, les variables d'environnement ou l'introspection en temps réel.

2. **ZÉRO FALLBACK DANGEREUX** :
   - Interdiction formelle des blocs d'exception silencieux (`except Exception: pass`, `except:` nu) et des valeurs de secours arbitraires masquant des bugs.
   - Toute défaillance doit lever une exception typée explicite, documentée et consignée pour permettre un débogage déterministe.

3. **100% SCALABLE & MODULAIRE** :
   - Conformité stricte aux principes de Clean Architecture, Domain-Driven Design et SOLID (schémas Pydantic v2 avec `extra='forbid'`, typage exhaustif, découplage total domaine/infrastructure).
   - Les modules doivent être dimensionnés pour supporter la montée en charge sans refactorisation lourde.

4. **100% DYNAMIQUE & AGNOSTIQUE** :
   - Découverte et introspection en direct des benchmarks certifiés, des serveurs MCP et des tables relationnelles.
   - L'allocation des modèles et des outils s'effectue à chaud en fonction des scores objectifs mesurés.

5. **ÉRADICATION SYSTÉMATIQUE DES VESTIGES & CODE MORT** :
   - Suppression obligatoire de tout code obsolète, écouteurs d'événements dupliqués ou orphelins, blocs HTML commentés inutiles, variables résiduelles et mocks historiques.
   - Aucun vestige d'anciennes architectures ne doit subsister lors d'une refonte ou d'une mise à jour.
