# ADR-021 : remplacer les remux trop lourds depuis ArrMada

- **Statut** : accepté
- **Date** : 2026-11-15
- **Assouplit** : « l'agent ne supprime aucun fichier » des
  [ADR-019](019-agent-ia.md) et [ADR-020](020-agent-ia-profils-qualite.md), pour
  ce seul cas

## Contexte

Les remux 2160p pèsent de 36 à 98 Go pour un gain visuel minime face à un
Bluray-2160p de 17 à 22 Go, et un remux 4K à 90 Mb/s saccade sur une TV
reliée en 100 Mb/s ([ADR-012](012-qualite-de-lecture.md)). Avec l'ADR-020,
l'agent a retiré Remux-2160p du profil principal et gardé un profil « films
d'exception » pour quelques titres.

Mais les fichiers déjà là n'ont pas bougé : Radarr ne descend jamais en
qualité. Mesuré sur l'installation : **150 films remplaçables, 8,6 To
occupés, environ 5,5 To à récupérer**. Il fallait passer dans Radarr film
par film, et l'agent n'avait ni outil de suppression ni inventaire complet
(sa recherche dans la médiathèque est plafonnée à 100 résultats).

## Décision

**Un écran et un outil d'agent, sur un même moteur**
(`services/remux_slim.py`) : Santé médiathèque › Remux (`/health?tab=remux`,
routes `/api/remux`), et les outils `list_heavy_remux` / `replace_remux`.

### Qui est dans la liste

Un film dont le fichier est un remux (2160p ; 1080p en option) **que son
profil qualité n'autorise plus**. Conséquences voulues :

- un film rangé dans un profil qui autorise le remux (« films d'exception »)
  n'apparaît jamais et ne peut pas être touché, même par un lot ;
- « Garder le remux » passe le film dans un tel profil : il sort de la liste ;
- la liste est lue en entier côté serveur (`GET /movie`), sans plafond.

Deux cas sont listés mais **non remplaçables**, avec la raison :

- film non surveillé (Radarr ne chercherait rien) ;
- fichier trop petit pour un remux (moins de 1,25 fois la taille attendue du
  remplaçant) : c'est une qualité mal détectée, il n'y a rien à gagner.
  Exemple réel : un « Remux-2160p » de 3,7 Go.

Le gain est une estimation : taille actuelle moins 10 Go par heure de film
en 2160p (5 Go en 1080p).

### Remplacer un film

Analogie exploitation : on ne purge pas un fichier de production avant
d'avoir la nouvelle livraison en main. Dans l'ordre :

1. **Relire le film** : il a pu changer de profil ou de fichier depuis
   l'affichage de la liste.
2. **Chercher un remplaçant** par la recherche interactive
   (`GET /release?movieId=`). Est retenue une release dont la qualité est
   autorisée par le profil, qui n'est pas un remux, de résolution au moins
   égale, et qui pèse **au plus 70 % du remux**. Tant que le remux est là,
   Radarr refuse tout (« Existing file meets cutoff ») : ces refus-là sont
   ignorés, car ils tombent avec le fichier ; tout autre refus (langue,
   format interdit, pas assez de sources) écarte la release. Classement :
   qualité la mieux placée du profil, puis score des formats personnalisés.
3. **Mettre ce remplaçant en téléchargement** (`POST /release`).
4. **Supprimer le fichier du remux** (`DELETE /moviefile/{id}`), jamais le
   film, qui reste surveillé.

Si l'étape 2 ou 3 échoue, rien n'est supprimé.

On télécharge la release vérifiée plutôt que de supprimer puis lancer une
recherche automatique (`MoviesSearch`), l'idée de départ. L'essai sur
l'installation a montré pourquoi : pour un remux de 98 Go, un des
« Bluray-2160p » proposés pesait 120 Go. Une recherche automatique aurait pu
le prendre ; ici, ce qui a été contrôlé est ce qui arrive.

### Lots

- **10 films au plus par lot**, un seul lot à la fois, 20 secondes de pause
  entre deux films : chaque film coûte une recherche sur tous les indexeurs
  et un téléchargement d'environ 20 Go.
- Le lot tourne en tâche de fond ; l'écran suit son avancement, et un bouton
  l'arrête après le film en cours. Ce qui est fait reste fait.
- Un film en erreur n'arrête pas le lot.

### Confirmation

Aucune suppression sans confirmation : la boîte de dialogue de l'écran, ou
la carte de validation de l'agent (ADR-019). Elle récapitule le nombre de
films, la place occupée, le gain estimé et ce que devient le fichier.

### Corbeille de Radarr

Le fichier supprimé part dans la corbeille de Radarr si elle est réglée
(ici `/media/downloads/complete/.recycle_bin`, vidée au bout de 30 jours).
**La place n'est donc libérée qu'au vidage** ; l'écran et la carte le disent.
Sans corbeille réglée, la suppression est définitive, et c'est dit aussi.

ArrMada ne vide pas la corbeille lui-même : la commande `CleanUpRecycleBin`
de Radarr ne retire que ce qui a dépassé le délai, et mettre le délai à 0
désactive le vidage au lieu de le déclencher. Pour libérer plus tôt : vider
le dossier à la main, ou baisser le délai dans Radarr › Paramètres › Gestion
des médias.

## Retour en arrière

- Un remux retiré reste dans la corbeille de Radarr jusqu'à son vidage : on
  peut le remettre dans le dossier du film et relancer un scan.
- Pour ne plus rien proposer : recocher Remux-2160p dans le profil et
  remettre le seuil dessus, ou passer les films dans le profil d'exception.

## Conséquences

- L'agent a maintenant **une** suppression de fichier, bornée : un remux,
  après mise en téléchargement d'un remplaçant plus léger. Il ne supprime
  toujours aucun titre.
- Si le téléchargement du remplaçant échoue ensuite, le film est
  « manquant » : la gestion des échecs de Radarr relance une recherche, cette
  fois selon son propre classement.
- Le profil garde les mises à niveau : Radarr peut plus tard remplacer le
  nouveau fichier par une release mieux notée, y compris plus lourde.
- Jellyfin et Bazarr ne sont pas pilotés ici : le nouveau fichier suit le
  chemin normal d'un import Radarr (synchronisation de Bazarr, gardien des
  sous-titres d'ArrMada). Sur l'installation, Radarr n'a pas de connexion
  vers Jellyfin : celui-ci voit le changement par sa propre surveillance des
  dossiers ou son scan planifié.
- Radarr notifie chaque fichier supprimé (Telegram, Trakt, webhook) : un lot
  de 10 films envoie 10 messages.
- L'état du lot est en mémoire : un redémarrage d'ArrMada en cours de lot
  l'interrompt entre deux films, sans demi-état (chaque film est traité en
  entier ou pas du tout, sauf erreur signalée à l'étape 4).
- Radarr seulement. Les séries (Sonarr) ne sont pas couvertes.
- Avec plusieurs Radarr, c'est le premier service activé qui est visé.
