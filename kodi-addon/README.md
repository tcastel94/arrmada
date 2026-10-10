# ArrMada — Plugin Officiel pour Kodi

Le plugin **ArrMada pour Kodi** permet de connecter directement votre médiathèque Kodi à votre stack `*arr` (Radarr, Sonarr, Bazarr, SABnzbd, Torrent) pour une gestion fluide depuis votre canapé.

---

## ✨ Fonctionnalités

### 1. 💬 Recherche de sous-titres en 1 clic (Bazarr)
- **Menu contextuel sur n'importe quel film ou épisode** : Clic droit / Touche Menu de la télécommande → **« ArrMada : Télécharger sous-titres (Bazarr) »**.
- Bazarr télécharge et applique automatiquement le meilleur sous-titre dans votre langue préférée (FR par défaut).
- Notification OSD instantanée sur votre écran TV confirmant le téléchargement.

### 2. 🔄 Re-recherche & Upgrade de Release (Radarr / Sonarr)
- **Menu contextuel sur un film, une saison ou un épisode** → **« ArrMada : Re-chercher / Upgrader release »**.
- Envoie l'ordre à Radarr ou Sonarr pour trouver et télécharger automatiquement une meilleure version (ex: passage à du 4K HDR ou correction d'un fichier corrompu).

### 3. ⚡ Scrobbling & Synchronisation en direct
- Remonte en temps réel l'état de lecture (*Play, Pause, Stop, Progression*) vers ArrMada.
- Met à jour l'état *Vu* et les points de reprise pour le multi-écrans.

### 4. 📺 Notifications TV des téléchargements terminés
- Dès qu'un téléchargement SABnzbd ou Torrent est terminé et importé par Radarr/Sonarr, une alerte discrète s'affiche en haut de l'écran Kodi.

### 5. 📥 Menu d'accueil ArrMada
- Consultez la liste et la progression des téléchargements actifs directement sur Kodi.
- Lancez un scan ou un nettoyage manuel de la médiathèque Kodi en un clic.

### 6. 📺 Nouvelle interface (ADR-003) : Accueil, Fiche, Téléchargements, Salon
Écrans « sur mesure » de la future appli ArrMada pour Kodi
([ADR-003](../docs/adr/003-kodi-app.md)), plein écran, pensés pour la
télécommande. Phase 0 : **Accueil**. Phase 2 : **Fiche média**,
**Téléchargements**, **Salon**.

**Accueil**
- Salutation et résumé de la flotte, 4 indicateurs (films, séries, stockage, téléchargements).
- Téléchargements en cours, rafraîchis toutes les 20 s.
- Rangée « Ajouts récents » avec zoom et halo au focus. Le fanart de l'affiche sélectionnée passe en fond, le ClearLogo et les badges 4K / DV / Atmos s'affichent.
- Bandeau du haut : *Rechercher*, *Téléchargements*, *Salon*, *Actualiser*, *Diagnostic*.
- Animations :
  - **ouverture** : apparition en cascade ;
  - **indicateurs** : compteurs qui défilent jusqu'à leur valeur, barres qui se remplissent ;
  - **fond** : lent zoom du fanart (effet « Ken Burns ») ;
  - **affiche sélectionnée** : elle se soulève et son halo « respire », son badge apparaît avec un léger rebond ;
  - **infos** : elles glissent dans le sens du déplacement.
- **Ouverture instantanée** : le dernier état connu est gardé en cache sur l'appareil, puis mis à jour en arrière-plan. Aucun appel réseau ne fige l'interface.
- **Hors ligne** : si le serveur ne répond pas, l'écran garde les dernières données, ou affiche l'adresse et l'erreur à vérifier. Il retente toutes les 20 s.
- Bouton **Diagnostic** : rendu des polices et des accents, version de Kodi et du skin, images/s, et temps mesurés (ouverture, réseau, rendu).
- **Intro** (environ 2,4 s, à la première ouverture de la session Kodi) : les deux jambes du « A » se rejoignent, le bouton lecture apparaît avec un rebond, deux ondes partent du logo, puis le nom et l'accroche montent. N'importe quelle touche la passe.

**Fiche média** (OK sur une affiche, ou sur une ligne de Téléchargements)
- Fanart en fond (zoom lent), ClearLogo (ou le titre), année · durée · classification · genres, notes TMDB / IMDb / Rotten Tomatoes, badges 4K / HDR / Atmos / Remux, synopsis, réalisation et musique.
- Colonne de droite : affiche, statut (*Disponible*, *Manquant*, *15/19 épisodes*), fichier (qualité, taille, vidéo, audio, release) et sous-titres présents.
- **Film** : rangée *Casting* (photos rondes, initiales si pas de photo). **Série** : rangée *Saisons* avec la progression de chaque saison ; le bloc fichier décrit le dernier épisode téléchargé.
- Actions : **Lire** (médiathèque Kodi de l'appareil + préréglage Yamaha de la pièce), **Bande-annonce** (films, add-on YouTube requis), **Meilleure version** (recherche Radarr/Sonarr), **Sous-titres** (recherche Bazarr, films).
- L'écran s'affiche tout de suite avec ce que l'Accueil connaît déjà (titre, affiche, fanart), puis se complète en arrière-plan (environ 0,5 s).

**Téléchargements**
- Toute la file Radarr/Sonarr : barre de progression, pourcentage, temps restant, **débit estimé** (calculé entre deux rafraîchissements), taille, statut coloré (*En cours*, *En pause*, *En attente*, *Import en attente*, *Erreur*) et la raison d'une erreur d'import.
- Rafraîchi toutes les 5 s, sans clignotement : seules les valeurs changent, la sélection reste en place.
- OK sur une ligne : ouvre la fiche du titre (et affiche le détail d'une erreur).
- Boutons **Tout mettre en pause** / **Tout reprendre**.

> ⚠️ **La pause porte sur toute la file SABnzbd**, pas sur un seul titre :
> c'est ce que fait le serveur aujourd'hui (pause/reprise globales). Les
> lignes passent à « En pause » avec un délai d'environ une minute, le temps
> que Radarr/Sonarr relisent SABnzbd. Une pause titre par titre demandera
> une évolution du backend. Aucune suppression n'est possible depuis la TV
> (décision 1 de l'ADR-003).

**Salon** (bouton *Salon* de l'Accueil, ou en raccourci pendant un film)
- **Lecture en cours** sur cet appareil : affiche, titre, définition et audio, temps écoulé / durée, heure de fin, pastille *En pause*. Boutons *− 30 s*, *Lecture / Pause*, *+ 30 s*, *Stop*. Ces infos viennent de Kodi lui-même : elles restent à jour même serveur coupé.
- **Ampli Yamaha** : état, volume (% et dB), entrée, programme sonore. Boutons *Vol −*, *Vol +*, *Muet*, *Marche / Veille*. Rafraîchi toutes les 3 s, et tout de suite après chaque commande.
- **Préréglages audio** *Salon* / *Salle de cinéma* ; celui de la pièce de l'appareil est marqué (réglage de l'add-on *Profil de la pièce*).

**Télécommande** (Shield, et toute télécommande Android TV)

| Touche | Action |
|---|---|
| Flèches / OK | Naviguer / ouvrir la fiche du titre |
| **OK maintenu** (ou touche Menu) | Actions rapides : *Lire*, *Fiche détaillée*, *Chercher une meilleure version* |
| **Lecture/Pause** | Accueil et fiche : lit le film depuis la médiathèque Kodi de l'appareil (reprise incluse) ; pour une série, ouvre ses saisons |
| Retour | Passe l'intro, ferme l'écran en cours (fiche, téléchargements, salon, diagnostic), puis quitte |
| Bouton **Rechercher** | Ouvre le clavier de Kodi. Sur Android, il a un bouton **micro** pour dicter |

> Seul l'élément sous le focus est **bleu plein**. Le bouton principal
> d'un écran (*Lire*, *Vol +*…) est simplement teinté de bleu quand le focus
> est ailleurs.
>
> Le titre est retrouvé dans la médiathèque Kodi par son identifiant TMDB/TVDB,
> puis par son titre et son année. Kodi peut donc l'avoir en français et
> Radarr en anglais. Si le titre est introuvable, un message le dit, plutôt
> que de lancer le mauvais film.
>
> **Voix** : le bouton micro de la télécommande Shield appelle l'Assistant
> Google, qui ne parle pas à Kodi. Pour dicter une recherche, il faut le
> micro du clavier de Kodi (bouton « Rechercher »).

**L'ouvrir**
- Depuis l'add-on : **ArrMada → [NOUVEAU] Accueil ArrMada (apercu v2)**, ou **[NOUVEAU] Salon : ampli et lecture en cours**.
- Depuis le menu principal d'**Aeon Nox SiLVO** : Paramètres du skin → *Personnaliser le menu principal* → ajouter un élément → action personnalisée :

| Écran | Action personnalisée (ou favori Kodi) |
|---|---|
| Accueil | `RunPlugin(plugin://script.arrmada/?action=home)` |
| Téléchargements | `RunPlugin(plugin://script.arrmada/?action=queue)` |
| Salon | `RunPlugin(plugin://script.arrmada/?action=salon)` |

**Valider sur la Shield** : envoie une photo de chaque écran ci-dessous.
1. **Accueil**, 10 s après l'ouverture : mise en page, polices, affiches.
2. **Fiche d'un film** (OK sur son affiche), puis flèche bas : casting.
3. **Fiche d'une série**, puis flèche bas : saisons.
4. **Lire** depuis une fiche : le film démarre et l'ampli passe sur le préréglage de la pièce.
5. **Téléchargements**, pendant un vrai téléchargement : débit et temps restant.
6. **Salon** pendant un film : lecture en cours, volume, préréglages.
7. Ressenti : fluidité, animations, réactivité de la télécommande.

> Les temps mesurés sont aussi écrits dans `kodi.log` (lignes `[ArrMada] Accueil : …`,
> `[ArrMada] Fiche : …`).

---

## 🚀 Installation dans Kodi

### Méthode 1 : Fichier ZIP (Recommandé)
1. Copiez `kodi-addon/script.arrmada.zip` (toujours la dernière version) sur votre appareil Kodi ou un partage réseau.
2. Dans Kodi, allez dans **Extensions / Add-ons** > **Installer depuis un fichier ZIP**.
3. Sélectionnez `script.arrmada.zip` et validez. Pour une mise à jour, refaites la même manipulation : Kodi remplace l'ancienne version.

> Reconstruire le zip après une modification : augmentez `version="…"` dans
> `script.arrmada/addon.xml`, puis lancez `python3 kodi-addon/build_zip.py`.
> Le script produit aussi `script.arrmada-<version>.zip` (non suivi par Git),
> pratique pour revenir à une version précédente.

### Méthode 2 : Copie directe
Copiez le dossier `script.arrmada/` dans le dossier des extensions de Kodi :
- **LibreELEC / CoreELEC** : `/storage/.kodi/addons/`
- **Linux** : `~/.kodi/addons/`
- **Android** : `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/`
- **Windows** : `%APPDATA%\Kodi\addons\`

---

## ⚙️ Configuration

1. Ouvrez Kodi > **Extensions** > **Extensions Programmes** > **ArrMada** (ou faites Clic droit > **Paramètres**).
2. Renseignez :
   - **URL du serveur ArrMada** : `http://<IP_DE_VOTRE_SERVEUR>:8420` (port du backend ; le port 3420 de l'interface est converti automatiquement).
   - **Clé API / Mot de passe** : Votre mot de passe de connexion ArrMada (`ARRMADA_AUTH_SECRET`).
     Il n'y a **aucune valeur par défaut** : sans ce mot de passe, l'add-on est refusé (401).
     Le champ est masqué à la saisie.
   - **Nom de l'appareil** : Ex: `Kodi Salon`.
   - **Langue des sous-titres** : `fr` (ou selon votre choix).
3. Validez ! Le service démarre automatiquement en arrière-plan.

---

## 🛠️ Développement des écrans sur mesure

| Élément | Emplacement |
|---|---|
| Mise en page (XML Kodi, repère 1920 × 1080) | `script.arrmada/resources/skins/Default/1080i/script-arrmada-{home,detail,downloads,salon}.xml` |
| Remplissage des écrans, fils d'arrière-plan | `script.arrmada/lib/{home,detail,downloads,salon}_window.py` |
| Outils communs (lecture, préréglage ampli, notifications) | `script.arrmada/lib/ui_common.py` |
| Logique pure (mise en forme, cache) — sans Kodi | `script.arrmada/lib/home_data.py`, `script.arrmada/lib/screens_data.py` |
| Textures (coins arrondis, halo, dégradés, barres de progression) | générées par `python3 kodi-addon/tools/make_textures.py` |
| Tests (sans Kodi, lancés en CI) | `pytest kodi-addon/tests` |
| Banc de test visuel (vrai Kodi sous écran virtuel) | `kodi-addon/bench/run.sh` |

**Banc de test visuel** : sur une machine Linux (VM ou conteneur Ubuntu),
`sudo apt install kodi xvfb python3-pil curl`, puis `kodi-addon/bench/run.sh`.
Le script lance un faux backend et un Kodi sans écran (Xvfb) avec les polices
de SiLVO. Il rejoue un parcours à la télécommande (menu, intro, accueil,
fiche film et série, téléchargements, salon avec et sans lecture,
diagnostic, cache, panne serveur) et dépose 25 captures dans
`/tmp/arrmada-kodi-bench/shots/`. Le Kodi du système n'est pas modifié : tout
se passe dans un profil jetable. Le rendu final reste à valider sur la Shield.

Pour voir les animations : `RECORD=1 PACE=1.3 kodi-addon/bench/run.sh` filme
l'écran virtuel (`sudo apt install ffmpeg`) et produit
`/tmp/arrmada-kodi-bench/demo.mp4`. Rendu logiciel sans carte graphique : la
vidéo est moins fluide que sur la Shield.

Pièges connus, chacun couvert par un test :
- **Polices** : utiliser uniquement les noms présents dans **tous** les jeux de polices de SiLVO (liste dans `tests/test_windows_xml.py`). Une police inconnue retombe sans prévenir sur `font13`.
- **Glyphes** : la police de SiLVO (Roboto Condensed) n'a pas `→ ★ ✓ ▶`. Ils s'affichent en carré vide. Utiliser `·` et `•`.
- **Identifiants** : chaque `id` utilisé dans un `*_window.py` doit exister dans son XML, sinon le contrôle reste vide sans aucune erreur. Convention : toute constante en MAJUSCULES ≥ 100 est un identifiant de contrôle.
- **Focus** : un bouton non focalisé ne doit jamais être bleu plein (`texturenofocus` opaque en `4A9EFF`), sinon on ne sait plus où est le focus.
- **Retour d'un sous-écran** : `<defaultcontrol always="false">`, sinon Kodi remet le focus sur le contrôle par défaut à chaque retour (fiche → accueil).
- **Barres de progression dans une liste** : le contrôle `progress` de Kodi ne lit pas les propriétés d'un élément de liste. Les barres sont donc des images toutes prêtes (`media/arrmada/progress/bar-000.png` … `bar-100.png`, pas de 2 %).
- **Groupes de boutons** (`grouplist`) : Python ne peut pas changer leur navigation (`controlDown` lève « Unknown control type »). Rediriger la touche dans `onAction`.
- **Textures** : après une modification de `make_textures.py`, relancer le script et committer les PNG. Le test compare les PNG du dépôt à ceux que le script produit.
