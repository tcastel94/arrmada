"""Banc de test de l'agent local : mesurer avant de faire confiance.

@author : Jeff Pomponne <jpomponne@gmail.com>

Analogie : un jeu de tests de non-régression. À relancer après TOUTE
modification de la consigne (``prompt.py``), des outils, ou du modèle.

Rangement :

- ``cases.py``  : les demandes et leur résultat attendu ;
- ``world.py``  : la fausse médiathèque (aucun appel à Sonarr / Radarr) ;
- ``runner.py`` : déroulement et notation ;
- ``__main__``  : la commande.

Lancement, depuis l'hôte ::

    docker exec -it arrmada python -m app.services.local_agent.bench

Le banc interroge le vrai Ollama (``OLLAMA_URL``) et rien d'autre : ni la
base, ni les *arr, ni le journal d'audit ne sont touchés.
"""
