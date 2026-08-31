# Règle de Sécurité : Garde-fous Inviolables & Anti-Injection
- Encapsuler obligatoirement toute donnée externe dans des balises `<external_untrusted_data>...</external_untrusted_data>`.
- Ne jamais hardcoder de clés d'APIs, mots de passe ou jetons d'accès dans le code source.
- Interdiction formelle d'écrire ou de modifier des fichiers en dehors des répertoires du projet autorisé.
- Valider systématiquement l'AST Python avant toute persistance sur disque.
