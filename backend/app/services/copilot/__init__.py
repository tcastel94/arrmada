"""Copilote : assistant IA qui lit l'état réel de la stack avant de conseiller (ADR-017).

- ``redaction``     : masque les secrets avant qu'un résultat d'outil parte chez Anthropic ;
- ``knowledge``     : documents ArrMada (ADR, CHANGELOG, README) cherchables ;
- ``tools``         : outils en LECTURE SEULE branchés sur les services existants ;
- ``prompt``        : consigne système (stable, donc mise en cache) ;
- ``conversations`` : historique des échanges, en mémoire ;
- ``agent``         : boucle modèle ↔ outils, diffusée en événements.
"""
