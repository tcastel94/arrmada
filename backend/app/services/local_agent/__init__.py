"""Agent local : piloter Sonarr / Radarr en langage naturel avec l'IA du NAS (Ollama).

@author : Jeff Pomponne <jpomponne@gmail.com>

À ne pas confondre avec l'Agent IA « Claude » (``services/copilot``) : celui-ci
tourne sur un petit modèle local (7 à 14 milliards de paramètres), donc avec
une liste d'outils courte et des garde-fous plus stricts.

Principe (analogie exploitation) : le modèle ne touche jamais aux *arr. Il
remplit un « bon de commande » (nom d'un outil + paramètres) ; ce code vérifie
le bon, l'exécute lui-même, et rend le résultat au modèle.

Rangement :

- ``ollama``        : appel à l'API ``/api/chat`` d'Ollama (``num_ctx``, ``keep_alive``) ;
- ``tools``         : la liste blanche d'outils et leur exécution validée ;
- ``prompt``        : la consigne système (c'est elle que le banc de test fait évoluer) ;
- ``agent``         : la boucle modèle ↔ outils d'un tour de conversation ;
- ``conversations`` : historique des échanges, en mémoire ;
- ``audit``         : journal d'audit (une ligne JSON par événement) ;
- ``__main__``      : essai en ligne de commande, sans passer par l'interface.
"""
