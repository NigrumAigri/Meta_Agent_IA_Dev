# Règle FinOps : Disjoncteur Budgétaire & Calculs Déterministes
- Tous les coûts et consommations de tokens doivent être calculés en pur code Python via math_calculator.
- Interrompre immédiatement tout processus qui franchit le plafond budgétaire configuré pour le projet.
- Surveiller le seuil d'alerte à 80% du budget avant coupure définitive à 100%.
- Respecter les plafonds d'itérations d'outils par agent (max_iter).
