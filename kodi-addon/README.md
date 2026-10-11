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
- Alimente l'écran d'appoint du salon (heure de fin du film, voir § 15).
- Met à jour l'état *Vu* et les points de reprise pour le multi-écrans.

### 4. 📺 Notifications TV en temps réel
- Dès qu'un titre est importé sur le NAS (ou qu'un téléchargement démarre), une alerte discrète s'affiche en haut de l'écran Kodi, **en 5 secondes au plus** : le service relève les événements du serveur toutes les 5 s (§ 11).
- Un import déclenche aussi le scan de la médiathèque Kodi (au plus une fois par minute).
- **Bulles enrichies** (phase 3) : affiche du titre en icône, épisode (« Severance S02E10 · Cold Harbor »), qualité et taille ; *Mise à niveau sur le NAS* pour un remplacement, *Nouveau titre suivi* pour un simple ajout à Radarr/Sonarr, *Import bloqué* quand le *arr attend une intervention. Sans son. Au-delà de 2 nouveautés d'un coup, une seule bulle de résumé.
- **Pas de bulle pendant un film ou un épisode** : un résumé « Pendant ta séance » s'affiche à l'arrêt de la lecture. Réglage *Notifications pendant la lecture* pour les voir quand même.

### 5. 📥 Menu de l'add-on
Calqué sur la web app (§ 10) : Accueil, Découvrir, Manquants, Rechercher,
Calendrier, Téléchargements, Notifications, Salon, Appairage, Widgets pour
SiLVO. L'ancien menu (maintenance, gestion de la file…) reste disponible
sous **Outils (ancien menu)**.

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
- Depuis l'add-on : **ArrMada → Accueil**, ou **Salon : ampli et lecture en cours**.
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

### 7. 🔗 Appairage de la TV : pièce et ampli par appareil (phase 1 de l'ADR-003)
Chaque TV reçoit **son propre accès**, comme « connecter la TV » de Netflix :
plus de mot de passe admin dans Kodi, et un appareil se révoque d'un clic.

1. Sur la TV : **ArrMada → Appairer cette TV**. L'écran affiche un code à 6 caractères et un QR code.
2. Sur le téléphone : scanne le QR code (ou web app → **Réglages → Kodi → Appairer une TV** et saisis le code).
3. Choisis le **nom**, la **pièce** (Salon / Salle de cinéma) et l'**ampli** de cette TV. La TV se connecte toute seule en quelques secondes.

Ensuite :
- l'écran **Salon** et le préréglage appliqué par **Lire** visent **toujours l'ampli de la pièce de cette TV**. Le serveur l'impose : une TV ne peut pas piloter l'ampli d'une autre pièce ;
- la pièce choisie remplace le réglage « Profil de la pièce » de l'add-on ;
- la TV **n'utilise plus jamais le mot de passe admin** (depuis la 1.8) : une TV volée ou compromise ne donne pas les droits admin. Le serveur l'accepte toujours pour tes scripts et automatisations ;
- périmètre « TV » imposé par le serveur : lecture, recherche, ajout, sous-titres, file (lecture seule + pause/reprise), ampli. **Aucune suppression ni configuration** depuis une TV appairée (même dans les anciens menus) ;
- appairage et jeton acceptés **uniquement depuis le réseau local** ;
- Diagnostic (Accueil) : ligne « Appareil » ; web app : liste des TV, dernière activité, modifier, révoquer.

> Une TV révoquée (ou une base serveur remise à zéro) oublie son jeton à la
> première requête refusée : relance simplement l'appairage.

> **Passage automatique (1.8)** : une TV qui avait encore le mot de passe admin
> dans ses réglages s'appaire **toute seule** au démarrage. Elle demande un
> code, le valide elle-même avec le mot de passe (nom et pièce repris de ses
> réglages), récupère son jeton, puis **efface le mot de passe**. Une bulle
> « Cette TV est appairée » le confirme. Il reste à choisir son ampli dans la
> web app (Paramètres → Kodi → Appareils) ; en attendant, le serveur prend le
> premier ampli actif, comme avant. Serveur injoignable : nouvel essai toutes
> les 5 min. Mot de passe refusé : il est effacé, et la TV propose
> « Appairer cette TV ».

### 8. 🔄 Mises à jour automatiques : le dépôt ArrMada
ArrMada sert un **dépôt Kodi** (`http://<serveur>:8420/kodi/repo/`). Installé une
fois sur chaque TV, il permet à Kodi de mettre l'appli à jour **tout seul**
(au démarrage, puis toutes les 24 h). Plus de zip à copier.

1. Kodi : Paramètres → Système → Extensions → active **Sources inconnues**.
2. Gestionnaire de fichiers → **Ajouter une source** → `http://<serveur>:8420/kodi/repo/` → nomme-la « ArrMada ».
3. Extensions → **Installer depuis un fichier zip** → ArrMada → `repository.arrmada.zip`.
4. Extensions → **Installer depuis un dépôt** → Dépôt ArrMada → ArrMada (si l'appli est déjà installée, rien à faire).

L'adresse exacte est affichée dans la web app (Réglages → Kodi → « Mises à
jour de l'appli Kodi »). Côté serveur, le conteneur lit le dossier
`kodi-addon/` du dépôt Git (`./kodi-addon:/app/kodi-addon:ro` dans
`docker-compose.yml`) : après un `git pull`, la nouvelle version est proposée
aux TV, **sans reconstruire l'image Docker**. Forcer la vérification : Extensions
→ Mes extensions → Dépôts d'extensions → Dépôt ArrMada → Mettre à jour.

> Kodi signale dans son journal que le dépôt est en HTTP (pas HTTPS) : c'est
> attendu, il n'est joignable que depuis le réseau local.

### 9. 🔊 Boutons volume de la télécommande → ampli de la pièce
Kodi pour Android **ne reçoit pas** les touches volume : il les laisse au
système Android (vérifié dans le code source de Kodi, `AndroidKey.cpp`).
Aucun add-on ne peut donc les intercepter. La bonne solution est **dans la
Shield**, et elle marche dans toutes les applis (Kodi, Netflix…) :

| Méthode | Réglage | Condition |
|---|---|---|
| **HDMI-CEC** (recommandée) | Shield : Paramètres → Préférences de l'appareil → Écran et son → **Contrôle du volume** → HDMI-CEC. Ampli Yamaha : Configuration → HDMI → **Contrôle HDMI : Activé** | La Shield est branchée en HDMI sur l'ampli (ou sur la TV reliée à l'ampli en ARC/eARC) |
| **Infrarouge** | Même menu → **IR**, puis « Configurer l'IR » et choisir l'ampli Yamaha | Télécommande Shield 2019 (émetteur IR) pointée vers l'ampli |

Les libellés exacts des menus varient selon la version du firmware (Shield
et Yamaha). Chaque Shield pilote ainsi **l'ampli de sa propre pièce**, sans
réseau et sans délai. Dans Kodi, l'écran **Salon** reste disponible pour le volume fin, le
muet, la mise en veille et les préréglages.

### 10. 🧭 Navigation native et widgets pour l'accueil de SiLVO
La racine de l'add-on reprend la navigation de la web app. Les listes
s'affichent dans les vues du skin (mur d'affiches, liste…), avec affiche,
fanart, synopsis, année, genres et note :

| Entrée | Contenu | OK / appui long |
|---|---|---|
| **Découvrir** | *Pour toi* (« parce que tu as … », sans ce que tu as déjà), *Films tendance*, *Séries tendance* | OK : fenêtre « Demander » (qualité, dossier, release) |
| **Manquants** | Titres surveillés sans fichier | OK : fiche · appui long : *Chercher une meilleure version* (lance la recherche) |
| **Calendrier (7 jours)** | Épisodes et films à venir, à l'heure locale (« Demain · 21:00 ») | OK : fiche |
| **Notifications** | Dernières notifications, nombre de non lues dans le menu | OK : texte complet, marquée lue |
| **Téléchargements**, **Accueil**, **Salon** | Écrans sur mesure (§ 6) | — |

Sur un titre de la médiathèque, l'**appui long** propose *Lire*, *Fiche
détaillée* et *Chercher une meilleure version*.

**Widgets** (Paramètres du skin → *Personnaliser le menu principal* → un
élément → *Widgets* → Extensions → ArrMada → **Widgets pour l'accueil de
SiLVO**) :

| Widget | Chemin |
|---|---|
| Ajouts récents | `plugin://script.arrmada/?action=widget&feed=recent` |
| À venir (7 jours) | `plugin://script.arrmada/?action=widget&feed=upcoming` |
| Téléchargements en cours | `plugin://script.arrmada/?action=widget&feed=downloads` |
| Pour toi | `plugin://script.arrmada/?action=widget&feed=foryou` |
| Manquants surveillés | `plugin://script.arrmada/?action=widget&feed=missing` |

> Rafraîchissement en direct : quand un flux change, le service publie
> `Window(Home).Property(arrmada.reload)`. Un widget dont le chemin se termine
> par `&reload=$INFO[Window(Home).Property(arrmada.reload)]` (chemin
> personnalisé dans Skin Shortcuts) se recharge alors tout seul.

### 10 bis. 🎬 Films et Séries : toute la bibliothèque (1.9.0)
Menu ArrMada → **Films** ou **Séries** : toute la bibliothèque de Radarr /
Sonarr, pas seulement les ajouts récents.

| Vue | Contenu |
|---|---|
| Tous, de A à Z | Toute la bibliothèque, sans tenir compte des majuscules ni des accents |
| Ajoutés récemment | Les derniers ajoutés à Radarr / Sonarr en premier |
| Par genre | Genres traduits, avec le nombre de titres (« Science-fiction (42) ») |
| En 4K | Films dont le fichier est en 2160p |
| Pas encore disponibles | Suivis, sans fichier sur le NAS pour l'instant |

- OK ouvre la **fiche ArrMada** ; appui long : *Lire*, *Fiche*, *Meilleure version*. Un titre sans fichier est marqué « pas encore disponible » (pas de *Lire*).
- Le **serveur** trie et filtre toute la bibliothèque, et la TV reçoit **100 titres à la fois**, avec une entrée **Page suivante** en bas. Les tris de Kodi (titre, année, note) restent disponibles, mais ne s'appliquent qu'à la page affichée.
- Widgets SiLVO en plus : *Films en 4K*, *Films ajoutés récemment*, *Séries ajoutées récemment* (Widgets pour l'accueil de SiLVO).
- Différence avec la médiathèque Kodi : ici, on voit aussi les titres suivis mais pas encore téléchargés, avec leur qualité. Pour reprendre un film là où on l'a arrêté, *Lire* passe par la médiathèque Kodi, comme ailleurs dans l'appli.

### 11. ⚡ Cache local et événements (service)
Le service de l'add-on (toujours actif) :
- **préchauffe un cache** sur la TV : ajouts récents (10 min), à venir (30 min), téléchargements (30 s), pour toi (6 h), manquants (30 min), notifications (2 min). Listes et widgets lisent ce cache : **affichage instantané, même serveur coupé**. Serveur injoignable : nouvel essai 2 min plus tard ;
- **relève les événements** du serveur toutes les 5 s (`/api/events/recent`, une toute petite requête) : un import ou un téléchargement lancé déclenche une notification à l'écran et le **rafraîchissement immédiat** des flux concernés. Serveur redémarré : détecté (`boot_id`), aucun événement perdu. Après une longue coupure : 3 notifications au plus, les plus récentes ;
- fait tout cela **dans sa boucle principale, sans fil de fond** (depuis la 1.7.1) : un petit morceau par seconde (au plus un relevé et un flux), comme un cron très rapproché plutôt qu'un démon qui garde une connexion ouverte ;
- s'arrête proprement avec Kodi (aucune trace d'erreur dans `kodi.log`).

L'ancienne surveillance par interrogation (`/api/kodi/addon-status`) ne sert plus qu'en secours, quand les événements du serveur ne répondent pas.

### 12. 🛟 Mode minimal et dépannage (Kodi qui se ferme)
**Disjoncteur de démarrage** (même principe que `StartLimitBurst` de systemd) :
si Kodi se ferme **deux fois de suite** dans les 2 minutes qui suivent son
démarrage, l'add-on passe tout seul en **mode minimal** au démarrage suivant
et l'annonce à l'écran. Il fait alors seulement ce que faisait la 1.4.2
(suivi de lecture, alertes de fin de téléchargement) : ni cache des listes,
ni relevé des événements. Les listes et l'accueil restent utilisables (ils
interrogent le serveur directement).

Pour revenir au fonctionnement normal : ArrMada → **Paramètres** → **Avancé**
→ décocher **Mode minimal**. Pris en compte tout de suite, sans redémarrer.

**Kodi se ferme à chaque démarrage et on n'a pas la main ?** Depuis un PC du
réseau local, avec `adb` (Shield : Paramètres → Préférences de l'appareil →
À propos → cliquer 7 fois sur « Build », puis Options pour les développeurs
→ **Débogage réseau** activé) :

```bash
SHIELD=192.168.1.50                          # IP de la Shield
KODI=/sdcard/Android/data/org.xbmc.kodi/files/.kodi
adb connect "$SHIELD:5555"                   # accepter la demande sur la TV
adb shell am force-stop org.xbmc.kodi        # arrêter Kodi
# Récupérer les journaux : kodi.old.log = la session qui a planté
adb pull "$KODI/temp/kodi.log" . ; adb pull "$KODI/temp/kodi.old.log" .
# Neutraliser l'add-on sans rien supprimer (réversible : renommer en sens inverse)
adb shell mv "$KODI/addons/script.arrmada" "$KODI/addons/script.arrmada.off"
```

Kodi redémarre alors sans ArrMada. Le journal (`kodi.old.log`) indique la
cause : chercher `ArrMada`, `Fatal`, `Traceback` et les dernières lignes.

---

### 13. 📱 Sur ton téléphone : QR codes vers la web app (phase 3)
Ce qui ne se fait pas sur la TV s'ouvre sur le téléphone : la TV affiche un
**QR code**, on le vise avec l'appareil photo, la bonne page s'ouvre.

| Où | QR code vers |
|---|---|
| Fiche média → bouton **Téléphone** | La fiche complète du titre dans la web app (historique, fichiers, profil, suppression) |
| Fiche média → **Bande-annonce**, sans l'add-on YouTube | La bande-annonce sur YouTube |
| Menu ArrMada → **Sur ton téléphone (QR code)** | Le tableau de bord de la web app |
| Outils (ancien menu) → **Maintenance du NAS** | La page Santé (nettoyage des orphelins) : aucune suppression depuis une TV |

Sur Android, un bouton **Ouvrir sur la TV** ouvre aussi l'adresse dans le
navigateur de la TV (s'il y en a un d'installé). L'adresse de la web app vient
du serveur : `PUBLIC_WEB_URL` si elle est réglée, sinon l'adresse du serveur
avec le port 3420.

### 14. ⭐ Raccourcis : favoris Kodi et menu de SiLVO (phase 3)
1. Menu ArrMada → **Raccourcis : ajouter aux favoris Kodi**. Quatre favoris
   apparaissent : *ArrMada · Accueil*, *· Téléchargements*, *· Salon*,
   *· Rechercher* (ceux déjà présents ne sont pas dupliqués).
2. Dans **SiLVO** : Paramètres du skin → *Personnaliser le menu principal* →
   ajouter un élément → *Favoris* → choisir le raccourci.

> Piège Kodi : un favori vers un écran d'add-on est lancé comme une **lecture**
> (`PlayMedia`). L'add-on le détecte, répond « rien à lire » à Kodi, puis
> ouvre l'écran normalement : pas de message d'erreur.

### 15. 🕰️ Écran d'appoint : heure de fin sur la tablette du salon (1.10.0)
Une tablette posée sous la TV (Pixel Tablet, ou n'importe quelle tablette
Android) affiche, sans éblouir pendant le film :

- **pendant une lecture**, en grand pour être lu depuis le canapé :
  l'affiche sur presque toute la hauteur, l'**heure de fin prévue** en très
  gros, l'**heure de début**, le temps restant, la barre de progression, le
  titre (et l'épisode), l'heure et le volume de l'ampli ;
- en pause : « Fin si reprise maintenant » en jaune (l'heure de fin recule
  tant que dure la pause) ;
- **au repos** : une grande horloge, les **sorties** de ce soir et demain, les
  **téléchargements** en cours et l'**ampli** de la pièce (volume, entrée,
  programme sonore).

Les tailles suivent l'écran (unité CSS `--u`, une fraction de la hauteur ou
de la largeur) : la page remplit la Pixel Tablet en paysage comme en portrait,
un écran de PC (aperçu admin) ou un téléphone, sans défilement.

**Rien à régler dans Kodi** : l'écran se sert du suivi de lecture que
l'add-on envoie déjà au serveur (case *Scrobbling* active dans les paramètres
de l'add-on). Depuis la 1.10.0, ce suivi lit les infos **du lecteur** (l'épisode
enchaîné tout seul est bien reconnu), envoie l'affiche et dit quand la vidéo
est **en pause**. Avec une 1.9 ou plus ancienne, l'écran marche aussi, mais
sans affiche venue de Kodi (le serveur prend alors celle de Radarr / Sonarr).

**Mise en place (Fully Kiosk Browser, recommandé)**

1. Sur la tablette, installer **Fully Kiosk Browser** (Play Store). La
   **licence PLUS** (achat unique, par appareil) est nécessaire pour régler
   la luminosité depuis la page.
2. *Settings → Web Content Settings → Start URL* :
   `http://<IP-du-serveur>:3420/ecran?seance=6&repos=40`
   - `seance` : luminosité **pendant un film** (0 à 255, défaut 6) ;
   - `repos` : luminosité **sans lecture** (0 à 255, défaut 40) ;
3. *Settings → Advanced Web Settings → **Enable JavaScript Interface*** :
   cocher (sinon la page ne peut pas baisser le rétroéclairage ; elle
   s'assombrit seulement elle-même).
4. *Settings → Device Management → **Keep Screen On*** : cocher (l'écran ne
   se met jamais en veille). Optionnel : *Screen Brightness* au même niveau
   que `repos`, et *Kiosk Mode* pour bloquer la sortie de l'appli.
5. Au premier affichage, la page montre un **code** et un **QR code** :
   le viser avec le téléphone (connecté à la web app), choisir la pièce
   **Salon**, valider. L'écran apparaît dans *Réglages → Kodi → Appareils*
   avec l'étiquette *Écran d'appoint* ; on le révoque d'un clic.

Toucher l'écran pendant un film le rallume 20 s. Sans Fully (Chrome) la page
marche aussi, mais Android garde sa luminosité et sa mise en veille : activer
*Options pour les développeurs → Rester activé* pendant la charge.

**Sécurité** : le jeton de l'écran ne permet qu'**une** chose, lire
`GET /api/ambient` (et « qui suis-je ? »). Pas de file de téléchargement,
pas de pilotage de l'ampli, pas de recherche : une tablette volée ne peut rien
faire d'autre qu'afficher l'heure de fin. Réseau local uniquement, comme les TV.

> Pièges : la page est en `http` sur le réseau local, donc l'API « Wake Lock »
> du navigateur (garder l'écran allumé) n'est pas disponible : c'est Fully
> (*Keep Screen On*) qui s'en charge. L'heure de fin est calculée par la
> tablette chaque seconde à partir du dernier relevé de la TV (toutes les
> 30 s) ; un saut dans le film est pris en compte au relevé suivant.

## 🚀 Installation dans Kodi

> ⚠️ **NVIDIA Shield (Kodi 21, Android)** : l'installation **par le dépôt** ferme
> Kodi (incident 1.7.0, cause en cours d'analyse), alors que le même zip
> installé depuis un partage réseau fonctionne. Sur la Shield, utiliser la
> **méthode 2** et désinstaller le Dépôt ArrMada (sinon Kodi peut proposer la
> mise à jour par le dépôt).

### Méthode 1 : Dépôt ArrMada (mises à jour automatiques ; pas sur la Shield pour l'instant)
Voir § 8 ci-dessus : une source `http://<serveur>:8420/kodi/repo/`, puis
`repository.arrmada.zip`, puis « Installer depuis un dépôt ».

### Méthode 2 : Fichier ZIP
1. Copiez `kodi-addon/script.arrmada.zip` (toujours la dernière version) sur votre appareil Kodi ou un partage réseau (SMB/NFS) déjà déclaré comme source dans Kodi, **avec la version dans le nom du fichier** :
   ```bash
   cd /chemin/vers/arrmada
   # Version lue dans addon.xml (ex. 1.10.0)
   V=$(sed -n 's/.*<addon [^>]*version="\([^"]*\)".*/\1/p' kodi-addon/script.arrmada/addon.xml)
   cp kodi-addon/script.arrmada.zip "/mnt/user/<partage-vu-par-kodi>/script.arrmada-$V.zip"
   ```
2. Dans Kodi, allez dans **Extensions / Add-ons** > **Installer depuis un fichier ZIP**.
3. Sélectionnez `script.arrmada-<version>.zip` et validez. Pour une mise à jour, refaites la même manipulation (nouveau fichier, nouveau nom) : Kodi remplace l'ancienne version, les réglages et l'appairage sont conservés.

> ⚠️ **Ne jamais écraser un zip sous le même nom pendant que Kodi tourne.**
> Kodi garde en mémoire la liste des fichiers de chaque zip déjà ouvert,
> jusqu'à sa fermeture (`DIR_CACHE_ALWAYS` dans `ZipDirectory.h`). Avec un
> zip écrasé, il lit le **nouvel** `addon.xml` (la nouvelle version
> s'affiche) mais copie l'**ancienne** liste de fichiers : les fichiers
> ajoutés manquent. En 1.10.0, c'est `lib/playback_data.py` : le service
> plante à son démarrage (« Erreur — consultez le journal », et dans
> `kodi.log` : `No module named 'playback_data'`). Reproduit dans un vrai
> Kodi. Sur la Shield, Kodi reste ouvert en arrière-plan : revenir à
> l'accueil Android ne le ferme pas.
>
> **Rattrapage** : fermer complètement Kodi (Shield : Paramètres Android →
> Applications → Kodi → **Forcer l'arrêt**), le relancer, puis réinstaller
> depuis un fichier au nom neuf (`script.arrmada-<version>.zip`). Réinstaller
> la même version par zip est permis.

> Reconstruire le zip après une modification : augmentez `version="…"` dans
> `script.arrmada/addon.xml`, puis lancez `python3 kodi-addon/build_zip.py`.
> Le script produit aussi `script.arrmada-<version>.zip` (non suivi par Git),
> pratique pour revenir à une version précédente.

### Méthode 3 : Copie directe
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
   - Plus de mot de passe à saisir depuis la 1.8 : la TV s'**appaire** (§ 7). Une TV
     qui avait l'ancien mot de passe s'appaire toute seule, puis l'efface.
   - **Nom de l'appareil** : Ex: `Kodi Salon`.
   - **Langue des sous-titres** : `fr` (ou selon votre choix).
3. Validez ! Le service démarre automatiquement en arrière-plan.
4. Appairez la TV (§ 7) : ArrMada → **Appairer cette TV** (sauf passage automatique depuis l'ancien mot de passe).

---

## 🛠️ Développement des écrans sur mesure

| Élément | Emplacement |
|---|---|
| Mise en page (XML Kodi, repère 1920 × 1080) | `script.arrmada/resources/skins/Default/1080i/script-arrmada-{home,detail,downloads,salon,pair}.xml` |
| Remplissage des écrans, fils d'arrière-plan | `script.arrmada/lib/{home,detail,downloads,salon,pair}_window.py` |
| Appairage : jeton de la TV, logique pure | `script.arrmada/lib/device.py`, `script.arrmada/lib/pairing_data.py` |
| Navigation native, widgets (Kodi) | `script.arrmada/lib/navigation.py`, `script.arrmada/lib/listing.py` |
| Films / Séries : vues, pages, genres (logique pure) | `script.arrmada/lib/library_data.py` |
| Flux en cache, événements, conversion en listes — sans Kodi | `script.arrmada/lib/feeds.py`, `script.arrmada/lib/catalog_data.py` |
| Travail de fond du service (cache + événements, sans fil) | `script.arrmada/lib/background.py` |
| Disjoncteur de démarrage (mode minimal) — sans Kodi | `script.arrmada/lib/startup_guard.py` |
| QR codes, raccourcis (logique pure) / fenêtre QR | `script.arrmada/lib/links_data.py` / `script.arrmada/lib/qr_window.py` |
| Passage automatique du mot de passe à l'appairage | `script.arrmada/lib/migration.py` |
| Outils communs (lecture, préréglage ampli, notifications) | `script.arrmada/lib/ui_common.py` |
| Logique pure (mise en forme, cache) — sans Kodi | `script.arrmada/lib/home_data.py`, `script.arrmada/lib/screens_data.py` |
| Dépôt Kodi servi par le backend | `backend/app/services/kodi_repo.py`, `backend/app/api/kodi_repo.py` |
| Textures (coins arrondis, halo, dégradés, barres de progression) | générées par `python3 kodi-addon/tools/make_textures.py` |
| Tests (sans Kodi, lancés en CI) | `pytest kodi-addon/tests` |
| Banc de test visuel (vrai Kodi sous écran virtuel) | `kodi-addon/bench/run.sh` |

**Banc de test visuel** : sur une machine Linux (VM ou conteneur Ubuntu),
`sudo apt install kodi xvfb python3-pil curl`, puis `kodi-addon/bench/run.sh`.
Le script lance un faux backend et un Kodi sans écran (Xvfb) avec les polices
de SiLVO. Il rejoue un parcours à la télécommande (menu, intro, accueil,
fiche film et série, téléchargements, salon avec et sans lecture,
diagnostic, appairage, listes natives, widgets, événement serveur, cache, panne
serveur, TV refusée, QR codes, favoris, bulle pendant un film, Films et Séries) et dépose 45 captures dans
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
- **Réglages modifiés pendant que Kodi tourne** : à l'enregistrement, Kodi ne recharge que la *première* copie `xbmcaddon.Addon(...)` de l'add-on en mémoire (`CAddonMgr::ReloadSettings`), alors que chaque module a la sienne. Un service qui doit voir un changement écoute `Monitor.onSettingsChanged()` et recrée sa copie (`service.py`, `ServiceMonitor`).
- **Service** : pas de fil de fond permanent ni de connexion réseau longue (incident 1.7.0) ; des délais réseau courts (≤ 4 s), car Kodi coupe un service qui met plus de 5 s à s'arrêter.
- **Barres de progression dans une liste** : le contrôle `progress` de Kodi ne lit pas les propriétés d'un élément de liste. Les barres sont donc des images toutes prêtes (`media/arrmada/progress/bar-000.png` … `bar-100.png`, pas de 2 %).
- **Groupes de boutons** (`grouplist`) : Python ne peut pas changer leur navigation (`controlDown` lève « Unknown control type »). Rediriger la touche dans `onAction`.
- **Libellé numérique** : `<label>1</label>` est lu comme l'identifiant d'un texte traduit de Kodi, pas comme « 1 ». Écrire `$NUMBER[1]`.
- **Fil de fond d'un service** : à l'arrêt, Kodi tue le script s'il ne s'arrête pas en 5 s. Un fil bloqué sur une lecture réseau doit être débloqué (fermeture du socket) puis attendu (`join`).
- **Image servie par une URL** : Kodi l'interroge d'abord en `HEAD` et se fie à l'extension. Servir `…/qr/K7P4QX.png` (pas `…/qr.png?code=…`) et accepter `HEAD`, sinon l'image reste vide.
- **Textures** : après une modification de `make_textures.py`, relancer le script et committer les PNG. Le test compare les PNG du dépôt à ceux que le script produit.
