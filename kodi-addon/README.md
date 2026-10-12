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

1. Sur la TV : **accueil ArrMada → Réglages → Appairer cette TV** (une TV pas encore appairée ouvre cet écran **toute seule** à l'arrivée sur l'accueil, 1.19.1). L'écran affiche un code à 6 caractères et un QR code.
2. Sur le téléphone : scanne le QR code (ou web app → **Réglages → Kodi → Appairer une TV** et saisis le code).
3. Choisis le **nom**, la **pièce** (Salon / Salle de cinéma / Bureau) et l'**ampli** de cette TV (pas d'ampli au Bureau). La TV se connecte toute seule en quelques secondes.

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
- Différence avec la médiathèque Kodi : ici, on voit aussi les titres suivis mais pas encore téléchargés, avec leur qualité. *Lire* passe par la médiathèque Kodi, comme ailleurs dans l'appli. Depuis la 1.11.0, les titres déjà vus portent la coche du skin et une série s'ouvre dans l'écran Série d'ArrMada (§ 16).

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

**Mode kiosk pendant un média (optionnel)** : la tablette passe au premier
plan sur `/ecran` et se **verrouille** quand la TV de sa pièce lance un film
ou un épisode, puis se **libère** et repasse en arrière-plan à l'arrêt
(20 s après, pour laisser l'épisode suivant démarrer sans va-et-vient). Le
reste du temps, c'est une tablette normale.

1. Dans Fully : *Settings → Remote Administration (PLUS)* → **Enable Remote
   Administration**, **Remote Admin from Local Network**, et un mot de passe.
   Configurer aussi *Kiosk Mode* (code PIN de sortie) : c'est ce mode que le
   serveur active et désactive.
2. Dans la web app : *Réglages → Kodi → Appareils* → modifier l'écran
   d'appoint → **Mode kiosk pendant un média** : activer, saisir le mot de
   passe Remote Admin (gardé chiffré sur le serveur, jamais réaffiché), puis
   **Tester**. L'adresse est celle de la tablette vue par le serveur ; la
   renseigner si elle change (bail DHCP fixe recommandé).
3. **Libérer** (même écran) déverrouille la tablette à la main : issue de
   secours si elle reste verrouillée.

Commandes envoyées (API Remote Admin, réseau local) : au lancement
`screenOn`, `toForeground`, `loadStartURL`, `lockKiosk` ; à l'arrêt
`unlockKiosk`, `toBackground`. Si la TV s'éteint sans prévenir, la tablette
est libérée quand la lecture n'est plus signalée (environ 2 min). Une
tablette injoignable n'est pas relancée en boucle : nouvel essai 5 min plus
tard.

> Pièges : si Fully est l'**appli d'accueil** d'Android (*Kiosk Mode → Launcher*),
> `toBackground` ramène… à Fully. Laisser le lanceur d'Android par défaut.
> L'adresse publique d'une tablette n'est jamais acceptée : réseau local
> uniquement (le serveur ne relaie pas un mot de passe vers Internet).

> Pièges : la page est en `http` sur le réseau local, donc l'API « Wake Lock »
> du navigateur (garder l'écran allumé) n'est pas disponible : c'est Fully
> (*Keep Screen On*) qui s'en charge. L'heure de fin est calculée par la
> tablette chaque seconde à partir du dernier relevé de la TV (toutes les
> 30 s) ; un saut dans le film est pris en compte au relevé suivant.

### 16. 📺 Séries, reprise et films vus : sans passer par SiLVO (1.11.0, ADR-004)
Première étape de l'[ADR-004](../docs/adr/004-arrmada-remplace-kodi.md) : à terme,
ArrMada remplace l'interface de Kodi, et Kodi ne sert plus que de **lecteur**,
caché dessous. Les vidéos passent toujours par le lecteur de Kodi : le son HD
vers l'ampli, le HDR et les sous-titres ne changent pas.

**Écran Série** (remplace l'écran Vidéos de SiLVO) : ouvert par *Lire* /
*Ouvrir la série* partout dans l'appli (Accueil, Fiche, listes, Reprendre).
- En haut : **« Reprendre S01E04 »** ou **« Lire S01E05 »**, c'est-à-dire
  l'épisode à suivre : celui qui est commencé, sinon le premier non vu après le
  dernier vu. Si tout est vu : « Revoir depuis le début ».
- Les **saisons** (« 3 / 9 vus »), puis les **épisodes** : vignette, pastille
  **Vu**, barre de progression si l'épisode est commencé. Le résumé, la date de
  diffusion et la durée s'affichent en bas.
- OK sur un épisode → le lire. Appui long → *Lire depuis le début*,
  *Marquer comme vu / non vu*, *Marquer toute la saison comme vue*.
- **Enchaînement** : les épisodes suivants (jusqu'à 30, d'une saison à
  l'autre) s'enchaînent tout seuls.
- Depuis la **Fiche** d'une série, OK sur une saison ouvre l'écran Série
  directement sur cette saison.

**Films** :
- Le bouton *Lire* de la Fiche affiche **« Reprendre à 42:10 »** si le film est
  commencé, et **« Revoir »** s'il est déjà vu.
- *Lire* demande **« Reprendre à … / Depuis le début »**. Kodi ne le demande pas
  quand une appli lance une vidéo : ArrMada le fait à sa place.
- Appui long sur *Lire* : *Lire depuis le début*, *Marquer comme vu / non vu*.
- Listes Films, Séries et Ajouts récents : la **coche « vu »** et la **barre de
  reprise** du skin apparaissent, avec *Marquer comme vu / non vu* dans
  l'appui long.

**Reprendre** (racine de l'appli, et widget SiLVO
`plugin://script.arrmada/?action=widget_continue`) :
- les films et épisodes commencés, plus **l'épisode suivant** de chaque série
  en cours, du plus récent au plus ancien (une seule entrée par série) ;
- OK lance la lecture avec la logique d'ArrMada (reprise, enchaînement,
  préréglage de l'ampli) ;
- appui long : *Lire depuis le début*, *Marquer comme vu*, *Ouvrir la série*.

> D'où viennent « vu » et « reprise » : de la **médiathèque Kodi de CET
> appareil** (c'est elle qui a le fichier et la position). Chaque Shield a
> donc les siens jusqu'à la phase 4.4 (partage par le serveur). Un épisode que
> Kodi n'a pas encore scanné n'apparaît pas : le scan automatique après
> chaque import (déjà en place) s'en charge.

> Piège Kodi, contourné : lancer une **liste de lecture** par l'API de Kodi
> ignore la position de reprise. ArrMada lance donc l'épisode **seul** (avec
> reprise), attend qu'il démarre, puis ajoute les suivants à la liste de lecture
> de Kodi. Comportement vérifié sur le banc (vrai Kodi, médiathèque de test).

### 17. 🏠 ArrMada à la place de l'accueil de Kodi (1.12.0, ADR-004)
Deuxième étape de l'[ADR-004](../docs/adr/004-arrmada-remplace-kodi.md) : la Shield
**démarre sur ArrMada**, et SiLVO ne s'affiche plus au quotidien.

**Accueil média** (ce qu'on voit en allumant) :
- en haut, le **menu** : Accueil, Films, Séries, Découvrir, Rechercher,
  Téléchargements, Salon, **Tableau de bord** (l'ancien Accueil : serveur,
  stockage, services) et Réglages ;
- l'**en-tête** décrit l'élément sélectionné : fond, titre ou logo, état
  (« Reprendre à 12:34 », « Épisode suivant »), résumé ;
- les **rangées** : *Reprendre* (médiathèque Kodi de la TV), *Ajouts
  récents*, *Pour toi*, *Bientôt*. Une rangée vide disparaît. Elles
  s'affichent tout de suite (cache du service) et se mettent à jour au
  retour d'une lecture.

**Films, Séries, Découvrir** : une **grille maison** remplace les vues de SiLVO.
- Onglets en haut (*Tous, de A à Z*, *Ajoutés récemment*, *Par genre*, *En 4K*,
  *Pas encore disponibles* ; pour Découvrir : *Pour toi*, *Films tendance*,
  *Séries tendance*). OK sur un onglet le choisit.
- 7 affiches par ligne, avec la pastille **Vu** et la barre de reprise. Les
  titres pas encore téléchargés sont atténués.
- Les pages de 100 titres se chargent **toutes seules**, deux lignes avant
  d'arriver au bout.
- OK : la Fiche (film), l'**écran Série** (série présente sur la TV), ou
  « Demander » (titre de Découvrir). Appui long : *Lire*, *Fiche*,
  *Meilleure version*, *Marquer comme vu / non vu*.

**Démarrage et retour automatique** : quand l'accueil **de Kodi** s'affiche
(au démarrage, en revenant de YouTube…), le service rouvre l'accueil ArrMada.
Jamais pendant une vidéo, ni par-dessus une fenêtre, ni en mode minimal.

**Retour** sur l'accueil ArrMada ouvre **« Quitter ? »** :

| Choix | Effet |
|---|---|
| Rester dans ArrMada | Rien (Retour par erreur) |
| Passer à l'interface Kodi | L'accueil de Kodi (SiLVO), sans retour automatique **jusqu'au prochain démarrage de Kodi** |
| Réglages de Kodi | Les réglages de Kodi, puis retour à ArrMada |
| Quitter Kodi | Ferme Kodi |

Pour garder l'accueil de Kodi au démarrage, décocher *Paramètres de l'add-on
→ Interface → Démarrer sur ArrMada et y revenir* (coché par défaut).

> **Jamais enfermé** : le menu « Quitter ? » mène toujours à l'interface
> Kodi. Le retour automatique s'arrête de lui-même dans trois cas :
> - si Kodi s'est fermé deux fois de suite au démarrage (mode minimal, § 12) ;
> - si l'accueil ArrMada se ferme 3 fois en une minute ;
> - si on a choisi « Interface Kodi » (jusqu'au prochain démarrage).

> Ce qui reste à Kodi : la barre de lecture, les réglages et le clavier.
> Depuis la 1.13.0 (§ 18), les add-ons, la TV en direct, les vidéos du NAS
> et les résultats de Rechercher s'affichent dans ArrMada.
>
> Le bouton Accueil de la télécommande Shield ramène au **lanceur Android**,
> pas à Kodi. En revenant dans Kodi, on retrouve ArrMada.

> La mise en page de l'accueil est **générée** par
> `kodi-addon/tools/make_shell_xml.py` : les 5 rangées et les 10 boutons du
> menu partagent le même modèle. Un test vérifie que le fichier versionné est
> à jour.

### 18. 🧩 Applis, TV en direct et vidéos du NAS (1.13.0, ADR-004)
Troisième étape de l'[ADR-004](../docs/adr/004-arrmada-remplace-kodi.md) :
YouTube, l'IPTV et les vidéos perso **sans passer par SiLVO**. Kodi fait
toujours tourner les add-ons et lit les vidéos ; ArrMada les affiche.

**Écran « Applis & sources »** (menu *Applis* de l'accueil) :

| Onglet | Contenu | OK |
|---|---|---|
| Vidéo | Add-ons vidéo de Kodi (YouTube, IPTV en add-on…) | Le contenu de l'add-on, dans ArrMada |
| TV en direct | Chaînes de la TV en direct de Kodi (IPTV Simple…), programme en cours, heure de fin, barre de progression, programme suivant | La chaîne |
| Musique | Add-ons audio et dossiers musicaux | Le contenu |
| Dossiers | Sources vidéo déclarées dans Kodi (partages SMB / NFS du NAS : vidéos perso, concerts) | Le dossier |
| Favoris | Favoris de Kodi (les raccourcis ArrMada eux-mêmes sont masqués) | Comme dans Kodi |
| Applis Android | Applis de la Shield (Netflix, Disney+…), sur Android seulement | L'appli |

- Dans un add-on ou un dossier : une **liste** avec un aperçu à droite
  (vignette, résumé, durée, « Reprendre à … », « Vu »). Le chemin s'affiche
  en haut (« YouTube › Abonnements »). **Retour** remonte d'un niveau, comme
  `cd ..`.
- Une vidéo **commencée** propose « Reprendre à … / Depuis le début ».
- **Appui long** : *Ouvrir dans Kodi*, issue de secours toujours présente
  pour un add-on qui a besoin de l'interface de Kodi ; *Réglages de
  l'add-on* ; *Guide TV de Kodi* sur une chaîne.
- Un add-on qui demande un texte (recherche YouTube) ouvre le **clavier de
  Kodi**, comme d'habitude.

**Rangée « Tes applis »** sur l'accueil (2e rangée) : tes **favoris Kodi**
d'abord, puis la tuile **TV en direct**, puis les add-ons vidéo. OK sur un
add-on l'ouvre directement ; Retour revient à l'accueil.
Pour choisir ce qui s'affiche en premier, ajoute l'add-on, le dossier ou
l'appli aux **favoris de Kodi** (appui long → *Ajouter aux favoris*). Pour une
appli Android : Kodi → *Programmes → Applications Android*.

**Rechercher** : les résultats s'affichent maintenant dans la **grille
ArrMada** (onglets *Tout*, *Films*, *Séries*, *Nouvelle recherche*). Un
titre déjà suivi ouvre sa Fiche (ou l'écran Série) ; un titre absent ouvre
« Demander ».

> Pièges connus :
> - **Un add-on qui ne s'ouvre pas ici** (il affiche une fenêtre à lui au
>   lieu d'une liste) : un message le dit. Appui long → *Ouvrir dans Kodi*.
> - **Pas d'onglet TV en direct** : aucun add-on de TV en direct n'est
>   activé dans Kodi (*Add-ons → Mes add-ons → Clients PVR*).
> - **Liste des chaînes vide juste après le démarrage** : la TV en direct de
>   Kodi se charge pendant quelques secondes. Ressortir et revenir.
> - Le **guide TV complet** (grille des programmes) reste celui de Kodi :
>   appui long sur une chaîne → *Guide TV de Kodi*.

### 19. 📷 Caméras Eufy : « Personne détectée » sur la TV pendant un film
Quand une caméra Eufy détecte une **personne** et qu'un film ou un épisode
passe, une **pop-up** compacte apparaît en haut à gauche de la TV : la
photo de la détection, le nom de la caméra et l'heure. Le film continue
dessous ; elle se ferme seule après 5 s, ou à la première touche. Hors lecture : une
simple bulle de notification, avec la photo en vignette. Ces alertes ne sont
jamais retenues pour le résumé « Pendant ta séance ».

```
caméras ─► cloud Eufy ─► eufy-security-ws (Unraid) ─► ArrMada ─► TV
```

Eufy n'a pas d'API locale : le conteneur **eufy-security-ws**
(`bropat/eufy-security-ws`) se connecte au cloud Eufy et publie les
événements sur le réseau local ; ArrMada s'y abonne (WebSocket).

1. Dans l'appli Eufy, **inviter un compte secondaire** (une autre adresse
   mail) avec les droits d'administration, **sans 2FA**. Ne pas utiliser le
   compte principal : Eufy déconnecte l'appli quand le même compte se
   connecte ailleurs.
2. Dans `.env` sur l'Unraid :
   ```bash
   EUFY_USERNAME=compte-secondaire@exemple.fr
   EUFY_PASSWORD=…
   EUFY_COUNTRY=FR
   EUFY_WS_PORT=8424                # port d'écoute du pont SUR LE NAS
   EUFY_WS_URL=ws://<IP-Unraid>:8424
   EUFY_DETECTIONS=person          # ou : person,ring
   ```
   Le pont tourne en réseau « host » : il prend directement un port du NAS.
   Le défaut du conteneur (3000) est souvent déjà pris (Grafana, AdGuard…),
   d'où 8424. Vérifier qu'il est libre **avant** de démarrer (aucune ligne =
   libre) :
   ```bash
   ss -ltn | grep -w 8424
   ```
3. Démarrer le pont puis redémarrer le backend :
   ```bash
   docker compose --profile eufy up -d eufy-security-ws
   docker logs -f eufy-security-ws        # attendre la connexion au cloud
   ./deploy.sh --backend
   ```
4. Vérifier : `curl -s http://<IP-Unraid>:8420/api/cameras/status` (avec un
   jeton admin) liste les caméras, et `POST /api/cameras/test` envoie une
   fausse détection : lance un film sur la TV pour voir la pop-up.

Réglage côté TV : *Paramètres de l'add-on → Service → Alertes des caméras*
(coché par défaut).

> Pièges :
> - **Code de vérification** au premier démarrage du pont (mail d'Eufy) :
>   le compte secondaire sans 2FA l'évite le plus souvent ; sinon, suivre la
>   documentation de eufy-security-ws (commande `driver.set_verify_code`).
> - La **photo** vient du cloud Eufy quelques secondes après la détection :
>   ArrMada l'attend au plus 6 s, puis affiche la pop-up sans photo.
> - Une même caméra ne déclenche pas plus d'**une alerte par minute**.
> - Les photos restent **en mémoire** sur le serveur (les 20 dernières,
>   1 h) et dans le cache de la TV (les 5 dernières) : rien n'est archivé.
> - La TV relève les événements toutes les 5 s : compter 5 à 10 s entre la
>   détection et la pop-up.

### 20. 🔁 Vu partagé entre les TV, épisode suivant, épisodes manquants (1.15.0, ADR-004)

**Vu et reprise partagés entre les TV.** Tu t'arrêtes à 42:10 sur la Shield
du salon : la Shield du cinéma propose « Reprendre à 42:10 ». Tu finis un
épisode, ou tu coches « vu » : l'autre TV le sait quelques secondes après.

```
Shield salon ──(dépose l'état)──► ArrMada (table watch_states) ──(événement)──► Shield cinéma
```

- Chaque Kodi garde sa médiathèque (vu, reprise) ; le serveur sert de point
  de rendez-vous. Un titre est repéré par ses identifiants publics (TMDB pour
  les films, TVDB de la série + saison + épisode) : les numéros internes de
  Kodi diffèrent d'une TV à l'autre.
- Ce qui part : la fin ou l'arrêt d'une lecture (3 s après, ce que Kodi a
  vraiment enregistré), et tout « marqué vu / non vu » (dans ArrMada, dans
  Kodi ou dans un autre add-on).
- Ce qui arrive : les changements faits ailleurs depuis le dernier passage
  de la TV (un curseur, comme `tail -f`), au démarrage, à chaque événement et
  après une coupure du serveur.
- **Premier passage** d'une TV : prudence. Elle n'ajoute que des « vu » et
  des reprises là où elle n'en a pas, puis dépose ce qu'elle a déjà vu (sans
  rien défaire chez les autres). Ensuite, **le geste le plus récent gagne**
  (« non vu » sur une TV → non vu partout).
- Réglage : *Paramètres de l'add-on → Lecture → Partager vu et reprise entre
  les TV* (coché par défaut).

**Épisode suivant.** 20 s avant la fin d'un épisode de la médiathèque, un
encart s'affiche en bas à droite : vignette, « S01E05 · Titre », compte à
rebours.

| Touche | Effet |
|---|---|
| OK sur **Lancer maintenant** | marque l'épisode en cours comme vu et passe tout de suite au suivant |
| OK sur **Annuler** | la lecture s'arrête à la fin de cet épisode |
| Retour, ou rien | l'encart disparaît, la suite démarre à la fin comme d'habitude |

Si rien n'était en file (épisode lancé depuis l'interface de Kodi), ArrMada
y ajoute l'épisode suivant de la série. Réglage : *Lecture → Encart
« Épisode suivant »* (0, 10, 20, 30, 45 ou 60 s avant la fin ; 0 : jamais).

**Épisodes manquants dans l'écran Série.** Les épisodes que Sonarr connaît et
que Kodi n'a pas s'intercalent à leur place, vignette vide et badge :

| Badge | Signification | OK |
|---|---|---|
| **Manquant** | diffusé, pas de fichier | « Lancer une recherche dans Sonarr ? » |
| **Sur le NAS** | téléchargé, Kodi ne l'a pas encore scanné | scan de la médiathèque Kodi |
| **À venir** | pas encore diffusé | date de diffusion |

Une saison entièrement absente apparaît aussi (« À venir », « Manquante »).
Les épisodes non suivis dans Sonarr (vieilles saisons qu'on ne veut pas) et
les épisodes spéciaux ne sont pas affichés.

> Pièges :
> - Les deux TV doivent avoir la **même série identifiée de la même façon**
>   (scraper TMDB / TVDB de Kodi) : une série sans identifiant TVDB ni TMDB
>   n'est pas partagée.
> - Un titre absent d'une TV (pas encore scanné) y sera rattrapé au
>   prochain changement le concernant, pas rétroactivement.
> - L'encart n'apparaît que pour une lecture **en file** (liste de lecture
>   vidéo de Kodi) : un lien direct d'un autre add-on n'enchaîne rien.
> - Serveur plus ancien que l'add-on : la synchro attend 1 min entre deux
>   essais, sans gêner le reste.

### 21. 🎛️ Panneau pendant le film : pistes, sous-titres Bazarr, ampli (1.16.0, ADR-004)

Pendant la lecture, **appui long sur OK** : un panneau ArrMada s'ouvre en bas
de l'écran, le film continue au-dessus. Un appui court garde son rôle (barre
de lecture de Kodi pour avancer / reculer).

| Section | Ce qu'on y fait |
|---|---|
| **Audio** | Choisir la piste : « Français · Dolby Digital Plus 5.1 · VFF », « Anglais · Dolby TrueHD 7.1 · VO »… (point bleu : piste en cours) |
| **Sous-titres** | Désactivés, pistes du fichier (forcés, malentendants), **Chercher en français avec Bazarr**, **Synchroniser avec l'audio** |
| **Ampli** | Volume − / +, couper le son, préréglages des pièces (l'ampli de la pièce de la TV) |
| **Lecture** | Épisode suivant, s'arrêter après celui-ci, chapitre suivant / précédent, reprendre depuis le début |

En haut : titre, épisode, position, **heure de fin** et temps restant (ceux
du lecteur de Kodi, à jour en direct). Retour referme le panneau.

**Sous-titres Bazarr sans relancer le film** : le panneau se ferme tout de
suite, Bazarr cherche (ou recale) les sous-titres. Dès que le fichier apparaît
à côté de la vidéo (« Dune.fr.srt »), Kodi le charge et l'affiche ; une bulle
le dit. Rien au bout d'1 min 30 : « Rien de nouveau pour l'instant ».

Le raccourci est un **fichier de touches** de Kodi posé par l'add-on :
`userdata/keymaps/arrmada.xml` (comme un fichier d'override dans
`/etc/*.d/` : il ajoute une règle sans toucher aux fichiers de Kodi). Réglage
*Lecture → Panneau ArrMada : appui long sur OK pendant la lecture* (coché par
défaut) ; décoché, ou en mode minimal, le fichier est retiré et Kodi relit
ses touches aussitôt. Ouvrable aussi par `plugin://script.arrmada/?action=player`.

> Pièges :
> - **Désinstaller l'add-on** : décocher d'abord le réglage, sinon le fichier
>   de touches reste et l'appui long affiche une erreur. Rattrapage :
>   supprimer `userdata/keymaps/arrmada.xml` (Shield :
>   `Android/data/org.xbmc.kodi/files/.kodi/userdata/keymaps/`).
> - Les sous-titres de Bazarr se chargent si Kodi **voit le dossier** de la
>   vidéo (partage SMB/NFS déclaré comme source) : c'est déjà le cas pour la
>   médiathèque.
> - Une télécommande qui n'envoie pas d'appui long (certaines télécommandes
>   CEC) : ajouter un favori vers `?action=player`, ou passer par l'écran Salon.

### 22. ⏭️ Passer l'intro, générique de fin, sous-titres automatiques (1.17.0)

**« Passer l'intro » / « Passer le récap »** : quand le chapitre en cours du
fichier s'appelle *Intro*, *Opening*, *Générique*, *Previously on*,
*Récap*…, un bouton s'affiche en bas à droite pendant 10 s, déjà
sélectionné : **OK** saute au début du chapitre suivant ; Retour ou rien,
il disparaît. Une fois par chapitre.

**Générique de fin** : dans un épisode, dès que le chapitre *End Credits*,
*Ending*, *Générique de fin*… commence, l'encart « Épisode suivant » s'ouvre
sans attendre les 20 dernières secondes.

> Ça dépend de tes fichiers : beaucoup de WEB-DL et d'animés nomment leurs
> chapitres, la plupart des Blu-ray non (« Chapitre 01 ») ; sans chapitres
> nommés, rien ne s'affiche (aucune devinette sur la position de l'intro).
> Pour voir les chapitres d'un fichier sur le NAS :
> `ffprobe -v error -show_chapters -of compact "Episode.mkv"`.

> Pourquoi l'add-on lit lui-même le fichier : sous Kodi 20, l'information
> « chapitre en cours » du lecteur ne bouge pas pendant une lecture normale
> (elle n'est mise à jour qu'après un saut), et l'API de Kodi ne donne pas la
> liste des chapitres. Pour un **MKV** (local, `smb://` ou `nfs://`),
> l'add-on lit donc la table des chapitres dans l'en-tête du fichier (64 Ko,
> une fois au début de la lecture) et la compare à la position : comme un
> `grep` sur l'index du fichier plutôt que d'attendre que Kodi le dise. Les
> autres formats (MP4…) gardent l'information de Kodi : le bouton n'y
> apparaît qu'après un saut dans le fichier.

**Sous-titres automatiques** : 8 s après le début d'un film ou d'un épisode
de la médiathèque, si l'audio est dans une autre langue que la tienne
(réglage *Langue des sous-titres*, `fr` par défaut) **et** qu'aucune piste
complète de sous-titres dans ta langue n'existe (des « forcés » ne suffisent
pas), Bazarr cherche tout seul. Le fichier trouvé est chargé et affiché sans
relancer le film ; une bulle le dit. Rien du tout pour un film en VF, ou si
la langue de l'audio est inconnue.

Réglages (*Paramètres de l'add-on → Lecture*) : *Bouton « Passer l'intro »*
et *Sous-titres automatiques*, cochés par défaut.

> Pièges :
> - Bazarr absent ou titre inconnu de Radarr/Sonarr : la recherche
>   automatique échoue **en silence** (une ligne dans `kodi.log`), pour ne
>   pas afficher une erreur à chaque lecture.
> - Bazarr cherche selon **ses** profils de langues : une langue absente du
>   profil de la série ne sera pas trouvée.

### 23. 🌙 « Ce soir » : ce qui sera fini avant l'heure choisie (1.18.0)

Menu de l'accueil → **Ce soir** (ou `plugin://script.arrmada/?action=tonight`,
à mettre en favori). La grille ArrMada s'ouvre avec, en onglets, des heures
de fin : **Avant 22:00**, **Avant 22:30**… cinq horaires toutes les 30 min,
le premier au moins 45 min après maintenant, puis **Sans limite**. L'onglet
ouvert d'office est le premier qui laisse 2 h (la durée d'un film).

Chaque onglet ne montre que ce qui sera **fini** avant l'heure dite, en
partant de maintenant, dans cet ordre :

1. ce qui est commencé (film ou épisode) : il reste durée − reprise ;
2. l'épisode suivant de chaque série en cours ;
3. les films jamais vus de la médiathèque, du plus récent au plus ancien.

Chaque affiche dit « Reprise à 42:10 · reste 1 h 53 · fini vers 22:40 » ou
« 1 h 25 · fini vers 22:12 ». **OK** lance la lecture comme la rangée
Reprendre (reprise proposée, épisodes enchaînés, préréglage de l'ampli) ;
l'appui long propose Depuis le début, Marquer comme vu, Ouvrir la série.

> Pourquoi c'est la TV qui calcule : la médiathèque Kodi de la TV sait ce
> qui est commencé et vu **ici** ; l'heure vient de l'horloge de la TV
> (celle de l'écran), pas de Python (sur Android, son fuseau n'est pas
> toujours le bon). Kodi la donne en 12 h ou 24 h selon la région, quel que
> soit le format demandé : « 05:43 PM » est converti en 17:43. Analogie : un `at` à l'envers, on ne demande pas
> « lance à 22 h » mais « qu'est-ce qui tient avant 22 h ».

> Pièges :
> - un titre sans durée connue (fiche sans *runtime*, jamais lu) n'apparaît
>   que dans **Sans limite** (« durée inconnue ») : on ne promet pas une
>   heure de fin qu'on ne connaît pas ;
> - l'heure de fin ne compte ni les pauses ni les publicités d'une chaîne :
>   c'est la durée du fichier ;
> - les onglets bouclent (Gauche sur « Avant 22:00 » mène à « Sans
>   limite »), comme toutes les listes de Kodi.

### 24. 📺 Vu partagé dans la web app, « Lire sur la TV » (1.19.0)

Ce que les TV partagent déjà (vu / reprise, § 20) s'affiche aussi dans la
**web app** :

- **Médiathèque** : badge « Vu », « ⏵ 27 % » (film commencé) ou « 8 ép. »
  (épisodes vus d'une série), filtres *Vus / Non vus / En cours* ; mis à
  jour en direct quand une TV s'arrête (événement `watch_state`) ;
- **Reprendre** (menu *Bibliothèque*, raccourci `g e`) : films et épisodes
  commencés sur les TV, le plus récent d'abord, avec l'heure d'arrêt, le
  temps restant et la TV ;
- **« Sur la TV »** (fiche d'un film présent sur le disque, fiche d'une série
  → « S02E05 sur la TV », bouton TV de chaque affiche de *Reprendre*) :
  choisis une TV appairée, *Reprendre à 42:10* ou *Depuis le début*. La TV
  retrouve le titre dans **sa** médiathèque Kodi et le lance par la logique
  d'ArrMada (reprise, épisodes suivants en file, préréglage de l'ampli de sa
  pièce). Pour une série, l'épisode proposé est celui en cours, sinon le
  suivant du dernier vu.

> Comment ça marche : la web app ne parle jamais à Kodi. Le serveur publie
> une demande `play_request` qui porte le numéro de la TV visée ; toutes les
> TV relèvent les événements toutes les 5 s et seule la bonne la prend.
> Analogie : un message sur un bus avec l'adresse du destinataire, plutôt
> qu'une connexion entrante vers la TV (aucun port à ouvrir, rien à exposer).
> Routes : `GET /api/kodi/watch-summary` (web app seulement, pas les TV) et
> `POST /api/kodi/play-on-device` (admin seulement).

> Pièges :
> - une TV **éteinte ou en veille** ne reçoit rien : le menu la marque
>   « absente », et la demande **expire au bout de 2 min** — jamais de film
>   qui démarre tout seul au rallumage (ni après un redémarrage du serveur,
>   qui rejoue son historique d'événements) ;
> - le titre doit être dans la médiathèque Kodi de **cette** TV (scannée) :
>   sinon une bulle « n'est pas dans la médiathèque de cette TV » ;
> - la TV doit être en 1.19.0 ou plus : une plus ancienne ignore la demande.

### 25. 🗂️ Pièce « Bureau » sans ampli, appairer depuis l'accueil (1.19.1)

**Appairer depuis l'appli ArrMada.** Avant, l'appairage n'était accessible
que par l'interface de Kodi (Extensions → ArrMada → « Appairer cette TV ») :
introuvable quand Kodi démarre directement sur l'accueil ArrMada. Désormais :

- une TV **pas encore appairée** ouvre l'écran d'appairage **toute seule** en
  arrivant sur l'accueil ArrMada (une fois par démarrage de Kodi : *Retour*
  le ferme et il ne revient pas en boucle) ;
- à tout moment : **Réglages** (dernier bouton du menu de gauche) →
  *Appairer cette TV* — ou *Refaire l'appairage (TV Sony · Bureau)* si elle
  l'est déjà —, *Paramètres de l'add-on*, *Réglages de Kodi* ;
- juste après l'appairage, la TV relève événements et flux **tout de suite**
  et l'accueil se remplit dans la foulée (avant : jusqu'à 2 min de rangées
  vides, le temps que les essais espacés reprennent).

**Pièce « Bureau ».** Une troisième pièce, **sans ampli** : le son passe par
la TV. Le serveur l'impose (comme le reste du périmètre TV) :

- à l'appairage ou en déplaçant une TV au bureau dans la web app, l'ampli est
  retiré (la liste « Ampli » est grisée : « Pas d'ampli dans cette pièce ») ;
- une TV du bureau qui demande l'état de l'ampli, une commande ou un
  préréglage reçoit `no_amp` : **jamais l'ampli du salon** (avant, une TV
  sans ampli choisi retombait sur le premier ampli actif, celui du salon) ;
- côté TV : aucun préréglage au lancement d'un film, pas de section *Ampli*
  dans le panneau pendant le film, et l'écran *Salon* masque volume, muet,
  marche / veille et préréglages : « Pas d'ampli dans cette pièce : le son
  passe par la TV. » ;
- l'écran d'appoint (tablette Fully Kiosk) d'une autre pièce ne suit pas la
  TV du bureau : elle n'a pas de tablette.

> Analogie : la pièce est un groupe d'hôtes dans un inventaire Ansible. Le
> groupe « bureau » n'a simplement pas de variable `avr` : les tâches « ampli »
> sont sautées, au lieu d'aller taper l'hôte d'un autre groupe.

> Pièges :
> - la TV relit son nom, sa pièce et son ampli à chaque reconnexion au
>   serveur : après un changement dans la web app, elle suit au plus tard au
>   redémarrage de Kodi (le serveur, lui, applique la nouvelle pièce
>   **immédiatement**, quelle que soit la version de la TV) ;
> - une TV en 1.19.0 ou moins déplacée au bureau ne pilote plus l'ampli (le
>   serveur refuse), mais affiche encore une section *Ampli* vide : passe-la
>   en 1.19.1 ;
> - une **instance** Kodi (adresse JSON-RPC déclarée dans la web app) et un
>   **appareil appairé** (Paramètres → Kodi → Appareils) sont deux choses :
>   l'instance sert au serveur à interroger Kodi, l'appairage donne son accès
>   à l'add-on de la TV. Ajouter l'instance ne lie pas la TV : il faut aussi
>   l'appairer.

### 26. 💿 Boîtier et disque dans la fiche, logos, artworks (1.20.0, boîtier réaliste en 1.20.1)

**La fiche montre le film dans un vrai boîtier, façon Aeon Nox.** L'affiche est
glissée sous le film plastique comme une jaquette ; le boîtier suit le fichier :

| Fichier | Boîtier | Bandeau |
|---|---|---|
| 4K (2160p) | noir | « 4K ULTRA HD » + « Blu-ray Disc » |
| 720p / 1080p | bleu translucide | « Blu-ray Disc » |
| SD (480p / 576p) | noir, plus haut (format DVD) | aucun |
| pas de fichier | transparent, vide | aucun |

Ce qui le rend crédible : les proportions d'un vrai boîtier, la charnière à
gauche (la jaquette s'enroule autour du dos), le liseré du plastique, le film
transparent avec son reflet en diagonale et l'ombre là où il plaque la
jaquette. Un vrai Blu-ray est plus large qu'une affiche : l'affiche est
recadrée au centre (le boîtier est un poil plus haut qu'un vrai pour en
couper moins), jamais déformée.

> Comment c'est fait : Kodi ne sait dessiner ni dégradé ni reflet, tout passe
> par des images. Chaque boîtier est UNE image générée par
> `tools/make_textures.py` (couleurs comprises, comme un calque PNG posé
> par-dessus l'affiche) ; seul le texte du bandeau est un label. La web app
> refait les mêmes calques en CSS. Pour retoucher un boîtier : modifier
> `CASES` / `case_pixel` dans le générateur, relancer
> `python3 kodi-addon/tools/make_textures.py`, puis les tests (ils vérifient
> que l'affiche remplit exactement la fenêtre de la jaquette).

**Le disque sort de la boîte.** À l'ouverture de la fiche, le disque glisse
hors du boîtier (léger rebond) et tourne lentement. Il **rentre** quand tu
lances la lecture, **ressort** au retour de la lecture, et rentre à la
fermeture de la fiche. Le reflet de lumière, lui, reste fixe pendant que le
disque tourne : c'est ce qui le rend crédible.

- **Rond imprimé** du vrai Blu-ray quand fanart.tv en a un (films) ;
- sinon, **disque dessiné à partir de l'affiche** : zone imprimée, moyeu en
  plastique transparent, trou central, tranche (séries comprises).

**Le logo du titre** (titre détouré) remplace le texte en haut à gauche de la
fiche, comme avant, mais il est maintenant trouvé bien plus souvent, et **en
français d'abord** : le serveur ne se contente plus du logo de Radarr/Sonarr.

**D'où viennent les images ?** Du serveur ArrMada, qui les récupère sur
fanart.tv (logos HD, disques, clearart, bannières) et TMDB (logos) :

- **web app → Médiathèque → bouton « Artworks »** : *Récupérer les
  manquants* (toute la médiathèque, en arrière-plan sur le serveur, avec la
  progression) ou *Tout redemander* ;
- **tâche quotidienne** : les nouveaux titres ont leurs artworks sans clic
  (`ARTWORK_AUTO_ENABLED`, `ARTWORK_AUTO_INTERVAL_HOURS`) ;
- **web app → fiche d'un titre → onglet « Artworks »** : le même boîtier et
  son disque, toutes les images du titre et *Actualiser les artworks*.

La TV ne parle jamais à fanart.tv ou TMDB pour savoir quoi afficher : elle
reçoit les adresses des images avec la médiathèque et la fiche, comme
l'affiche. Les rangées et les listes du plugin portent aussi l'image
`discart` : les vues de SiLVO qui savent afficher un disque en profitent.

> Analogie : c'est un cache de métadonnées en amont, comme un dépôt miroir
> (Satellite / Pulp) : le serveur va chercher une fois chez les fournisseurs,
> les TV ne lisent que le miroir local.

> Pièges :
> - **sans `FANART_API_KEY`** (clé personnelle gratuite sur fanart.tv, à
>   mettre dans le `.env` du serveur puis redémarrer), pas de rond imprimé :
>   le disque est dessiné avec l'affiche, et les logos viennent de TMDB
>   seulement. Le bouton « Artworks » le signale ;
> - les logos SVG de TMDB sont ignorés : Kodi ne sait pas les afficher ;
> - un titre déjà interrogé n'est redemandé qu'au bout de 30 jours (7 si rien
>   n'avait été trouvé) : pour un titre précis, utilise *Actualiser les
>   artworks* dans sa fiche web, ou *Tout redemander* ;
> - l'affiche et le fond choisis dans Radarr/Sonarr restent prioritaires : les
>   artworks ne font que combler ce qui manque (sauf le logo, français d'abord).

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
4. Appairez la TV (§ 7) : l'accueil ArrMada ouvre l'écran d'appairage tout seul (sinon **Réglages → Appairer cette TV**), sauf passage automatique depuis l'ancien mot de passe.

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
| Vu / reprise partagés entre les TV : règles pures / travail du service | `script.arrmada/lib/sync_data.py` / `script.arrmada/lib/watch_sync.py` (serveur : `backend/app/services/watch_sync.py`) |
| Encart « Épisode suivant » : logique pure / fenêtre | `script.arrmada/lib/upnext_data.py` / `script.arrmada/lib/upnext_window.py` |
| Panneau pendant le film (pistes, Bazarr, ampli, fichier de touches) : logique pure / fenêtre | `script.arrmada/lib/player_data.py` / `script.arrmada/lib/player_window.py` |
| « Passer l'intro » (chapitres nommés) : logique pure / bouton | `script.arrmada/lib/chapter_data.py` / `script.arrmada/lib/skip_window.py` |
| Dépôt Kodi servi par le backend | `backend/app/services/kodi_repo.py`, `backend/app/api/kodi_repo.py` |
| Textures (coins arrondis, halo, dégradés, barres de progression) | générées par `python3 kodi-addon/tools/make_textures.py` |
| Tests (sans Kodi, lancés en CI) | `pytest kodi-addon/tests` |
| Banc de test visuel (vrai Kodi sous écran virtuel) | `kodi-addon/bench/run.sh` |

**Banc de test visuel** : sur une machine Linux (VM ou conteneur Ubuntu),
`sudo apt install kodi kodi-pvr-iptvsimple xvfb python3-pil curl ffmpeg`, puis
`kodi-addon/bench/run.sh`.
Le script lance un faux backend et un Kodi sans écran (Xvfb) avec les polices
de SiLVO, et une **médiathèque Kodi de test** (`bench/make_media.py` : une série
en 2 saisons et un film, fiches `.nfo`, scraper « Informations locales »). Il
rejoue un parcours à la télécommande (menu, intro, accueil, fiche film et
série, téléchargements, salon avec et sans lecture, diagnostic, appairage,
listes natives, widgets, événement serveur, cache, panne serveur, TV refusée,
QR codes, favoris, bulle pendant un film, Films et Séries, puis la phase 4.1 :
« Reprendre à … » sur la Fiche, écran Série, saison 2, appui long, reprise de
lecture avec épisodes enchaînés, rangée Reprendre ; enfin la phase 4.2 :
démarrage sur ArrMada, accueil média, grille Films (page 2 chargée d'avance,
onglets), grille Séries vers l'écran Série, menu « Quitter ? », retour
automatique ; puis la phase 4.3 avec un faux add-on vidéo
(`bench/harness/plugin.video.arrmadabanc`), IPTV Simple (3 chaînes locales
et leur guide, `bench/make_apps.py`), un dossier « vidéos perso » et des
favoris : rangée Tes applis, écran Applis & sources, lecture depuis l'add-on,
TV en direct, dossiers, favoris, recherche dans la grille ; enfin une
détection de caméra pendant le film (pop-up) puis hors lecture (bulle) ;
et la phase 4.4 : état vu / reprise déposé par la TV, épisode vu et reprise
de film venus d'une « autre TV » appliqués à la médiathèque, épisodes
manquants et à venir dans l'écran Série, encart « Épisode suivant » (Lancer
maintenant, puis Annuler) ; enfin la phase 4.5 sur une vidéo à 2 pistes
audio, 2 pistes de sous-titres et 3 chapitres : appui long sur OK, panneau,
changement de piste audio et de sous-titres, sous-titres « Bazarr » chargés
sans relancer, ampli, chapitre suivant ; puis la 1.17 sur un épisode à
piste anglaise et chapitres nommés : « Passer le récap », « Passer
l'intro », sous-titres français trouvés tout seuls, encart dès le générique
de fin) et dépose les captures dans
`/tmp/arrmada-kodi-bench/shots/`. Le Kodi du système n'est pas modifié : tout
se passe dans un profil jetable. Le rendu final reste à valider sur la Shield.

Pour voir les animations : `RECORD=1 PACE=1.3 kodi-addon/bench/run.sh` filme
l'écran virtuel (`sudo apt install ffmpeg`) et produit
`/tmp/arrmada-kodi-bench/demo.mp4`. Rendu logiciel sans carte graphique : la
vidéo est moins fluide que sur la Shield.

> Le banc a révélé un plantage de Kodi **à la fin de l'appairage** (2 passages
> sur 3) : le fil qui ferme l'écran vivait encore quand le script se
> terminait (« waiting on thread » dans le journal, puis erreur de
> segmentation). Depuis la 1.11.0, le script attend la fin de ses fils avant
> de rendre la main (`ui_common.join_threads`). Le plantage restant quand
> le harnais quitte Kodi est propre au Kodi 20 du banc (déjà présent avant).

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
