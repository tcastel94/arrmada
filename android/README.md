# ArrMada Android (TV, tablette, téléphone)

Appli native ArrMada pour **Android TV** (Shield en tête), les **tablettes**
et les **téléphones**, avec son propre lecteur vidéo. L'interface garde la police condensée, l'accent bleu et le fond qui
zoome lentement de l'add-on Kodi, avec le style « verre » du lecteur partout :
focus blanc (pastille ou contour), bleu réservé à ce qui est « en cours »
(`ui/components/GlassStyle.kt`). Les choix
sont expliqués dans l'[ADR-007](../docs/adr/007-appli-android-native.md).

> Une seule APK : elle reconnaît l'écran au lancement (TV, tablette ou
> téléphone) et adapte la navigation. Voir [Téléphone et tablette](#téléphone-et-tablette).

## Ce que fait la version 2.10 (phases 1 à 4 de l'ADR-007)

| Écran | Contenu |
|---|---|
| **Mise en route** | Adresse du serveur (celle de l'add-on Kodi, port **8420**), testée sur `/api/health`. Puis appairage par **code + QR code**, validé dans la web app (*Réglages › Appareils*), exactement comme une TV sous Kodi |
| **Accueil** | Barre du haut (sections en onglets texte à gauche ; Rechercher, Téléchargements, Applis, Tableau de bord, Réglages en pictogrammes à droite, nommés au focus, pastille bleue = téléchargements en cours ; profil), héros (logo ou titre, méta, résumé, « Reprendre à… ») sur le fond de l'élément sélectionné, rangées **Reprendre** (états vu / reprise partagés avec les TV sous Kodi), **Ajouts récents**, **Pour toi**, **Bientôt** |
| **Films / Séries** | Murs d'affiches de 7 colonnes : *Récents*, *A à Z*, *Année*, *4K* (films) ou *Mieux notés* (séries) |
| **Série** | Saisons en pastilles (« 3/10 vus », « 4/10 sur le NAS »), épisodes en vignettes Jellyfin : **vu**, barre de reprise, **MANQUANT**, **À VENIR** ; sous la rangée, le résumé de l'épisode au focus et la **carte technique** de son fichier. Bouton **Lire la suite** (reprend l'épisode commencé, sinon la suite du dernier vu). Appui long sur un épisode : *Lire depuis le début*, *Marquer comme vu / non vu*. OK sur un manquant : Sonarr le cherche |
| **Découvrir** | Tendances TMDB (films, séries) et « Parce que tu as… » : OK ouvre la fiche si le titre est déjà là, sinon la feuille *Télécharger* |
| **Rechercher** | Au clavier ou **à la voix** (bouton *Dicter*, ou touche recherche / micro de la télécommande quand elle arrive jusqu'à l'appli) : *Dans la médiathèque*, *Aussi dans Radarr / Sonarr*, *À demander* |
| **Télécharger** | La feuille de l'add-on : un film en un bouton ; une série en entier, une saison ou des épisodes cochés ; **Pour ce soir** (passe devant les autres téléchargements). Le bouton dit ce qui part (« Télécharger S02E05 », « Télécharger 3 épisodes ») |
| **Fiche film** | Logo, notes TMDB / IMDb / Rotten Tomatoes, **carte technique** (Vidéo : 2160p · Dolby Vision · HEVC ; Audio : TrueHD Atmos · 7.1 · langues ; Sous-titres), résumé (en français, TMDB), *Reprendre à…* / *Depuis le début*, **bande-annonce** (fichier du NAS en plein écran, sinon YouTube, en français d'abord), **distribution : OK sur un acteur ouvre sa filmographie** (films de la médiathèque, films à télécharger). À droite, le **boîtier de l'add-on** (Blu-ray bleu, 4K ULTRA HD noir, DVD, transparent si le fichier n'est pas là) et son **disque qui sort en roulant** puis tourne (rond imprimé fanart.tv, sinon l'affiche en anneau) |
| **Lecteur** | Fichier d'origine **sans transcodage**, son HD envoyé tel quel à l'ampli (passthrough). **Langues d'office** : titre étranger avec sous-titres FR → VO + sous-titres français ; film français → VF + sous-titres « forcés » (dialogues étrangers). Gauche / droite : −10 s / +30 s. Position enregistrée toutes les 30 s, en pause et en quittant ; « vu » à 90 %. Préréglage Yamaha de la pièce au lancement. Formats qu'ExoPlayer n'ouvre pas (**.m2ts** de Blu-ray, **.iso**…) : Jellyfin change le conteneur à la volée (**remux**, image intacte), automatiquement **Passer l'intro / le récap** (chapitres nommés du fichier, sinon marqueurs Jellyfin), carte **Épisode suivant dans 10 s** au générique de fin (ou 30 s avant la fin) puis enchaînement |
| **Menu pause** (façon Apple TV) | Image figée visible, logo, barre de lecture fine avec repères de chapitres, **heure de fin** et temps restant, onglets **Chapitres** (vignettes : image du chapitre, sinon aperçu trickplay ; saut direct), **Infos**, **Distribution**, **Sous-titres** (pistes nommées : langue, forcés, format), et un bouton **Audio** qui ouvre les **Réglages audio** : **son conseillé** selon le film et les enceintes de la pièce (salon 5.1, salle de cinéma 7.2.2, TV sans ampli) avec **décodage auto**, piste audio (Dolby TrueHD, DTS-HD, 7.1, « non lisible ici »), ampli : programme sonore, volume, **voix plus claires**, **mode nuit**, **basses** (Extra Bass, niveau du caisson) |
| **Téléchargements** | Cartes **Pour ce soir** (« Prêt vers 21:02 », étapes jusqu'à *Prêt à regarder*) et file Radarr / Sonarr (état, %, reste, débit). OK : **Débloquer**, Passer en tête, Pause / Reprendre, Relancer la recherche, Fiche, Annuler ma demande. *Pause sauf ce soir*, *Tout reprendre* |
| **Bulles et annonces** | Bulles en bas à droite (importé sur le NAS, téléchargement lancé, import bloqué), retenues pendant un film puis résumées (« Pendant ta séance »). Pop-up **Prêt à regarder** (Regarder / Plus tard), alerte **caméra** avec photo, **Lire sur la TV** depuis la web app |
| **Tableau de bord** | Salutation, compteurs animés (films, séries, stockage, téléchargements), téléchargements en cours, services, ajouts récents ; **intro animée** de l'add-on au lancement |
| **Ce soir** | Ce qui sera fini avant 22:00, 22:30… (« fini vers 22:14 ») |
| **Applis** | Applis Android installées sur la TV, lancées avec OK |
| **Profils famille** (ADR-008) | **Qui regarde ?** au lancement, avatar dans le menu pour changer : chacun sa rangée Reprendre, ses vus, son « Pour toi », ses demandes (« Prêt à regarder » le suit sur n'importe quelle TV). Gestion dans la web app (*Réglages › Profils famille*) |
| **Bande-annonce en fond** | Sur la fiche film, la bande-annonce rangée sur le NAS se lance sans le son après 2,5 s |
| **Vidéos** | Explorateur des dossiers du NAS déclarés dans la web app (*Réglages › Dossiers vidéo*) : ce qui n'a pas de fiche officielle (mangas **Kai**, montages, vidéos perso). Tri naturel (Ep 2 avant Ep 10), Retour remonte d'un dossier. Lecture du fichier d'origine avec le lecteur habituel, **vu / reprise** par profil, **sous-titres posés à côté** (`Ep 01.fr.srt`, `.ass`, `.vtt`) dans l'onglet Sous-titres. Appui long : reprendre, depuis le début, vu / pas vu |
| **Séries maison** | Un dossier de montage de fans (**Naruto Kai**, **One Pace**…) déclaré comme série apparaît dans la grille **Séries** et s'ouvre dans le **même écran Série** : arcs en pastilles, vu / reprise, « Lire la suite », épisode suivant automatique, rangée **Reprendre**. Affiche de la série officielle (TMDB) ou `poster.jpg` du dossier ; NFO repris s'il y en a. Voir [Séries maison](#séries-maison-naruto-kai-one-pace) |
| **Appui long** | Sur les cartes *Reprendre*, *Ma liste*, *Ajouts récents* et les grilles *Films / Séries* : lire ou reprendre, ouvrir la fiche, bande-annonce, ajouter à / retirer de *Ma liste*, marquer vu / non vu |
| **Volume de l'ampli** (ADR-013) | Vol + / Vol − / Muet de la télécommande règlent l'ampli Yamaha de la pièce, dans toutes les applis, une fois activé « ArrMada : volume de l'ampli » dans Paramètres › Accessibilité (bouton dans *Réglages*) |
| **Accueil de la Shield** | Rangée **À suivre** d'Android TV : les films et épisodes commencés, un clic reprend la lecture dans ArrMada. Chaîne **ArrMada · Ajouts récents** : un clic ouvre la fiche. Mises à jour en quittant l'appli et toutes les 30 min ; à couper dans *Réglages* |


## Téléphone et tablette

Même APK, même appairage (code validé dans la web app, *Réglages › Kodi ›
Appareils*). Le nom envoyé à l'appairage dit « (téléphone) » ou
« (tablette) » : ces appareils n'apparaissent pas dans les TV où envoyer un film.

| | Téléphone | Tablette |
|---|---|---|
| Navigation | Barre en bas : Accueil, Films, Séries, Rechercher, Téléch., **Plus** (Ce soir, Découvrir, Tableau de bord, Changer de profil, Réglages) | Même chose en colonne à gauche |
| Écrans | Affiches en grille adaptée à la largeur, blocs empilés, fiche film sans boîtier | Comme la TV, marges plus fines |
| Lecteur | Paysage plein écran. Tap : menu pause ; double tap à gauche / à droite : −10 s / +30 s ; tap sur la barre pour aller à un moment ; bouton **Quitter** | Idem |
| Son | Celui de l'appareil (pas de préréglage d'ampli ni de programme Yamaha depuis un téléphone) | Idem |
| **Sur la TV** | Bouton 📺 de la fiche film, ou appui long sur un épisode › *Lire sur une TV* : la TV choisie lance le titre dans les 5 s (TV sous l'appli comme sous Kodi) | Idem |

### Depuis l'extérieur : par ton VPN

Les jetons d'appareil ne marchent que depuis le réseau local (ADR-002). Pour
utiliser le téléphone hors de la maison, passe par ton VPN et déclare ses
adresses au serveur, dans `.env` :

```bash
# Tailscale installé sur le NAS (adresses 100.x, IPv6 fd7a:…)
DEVICE_TRUSTED_NETWORKS=100.64.0.0/10,fd7a:115c:a1e0::/48
# WireGuard : le sous-réseau du tunnel, ex. 10.8.0.0/24 (déjà accepté : 10.x est privé)
```

puis `git pull && ./deploy.sh`. Un VPN qui fait du NAT vers le LAN (routeur de
sous-réseau Tailscale, WireGuard sur la box) marche sans rien déclarer : le
serveur voit une adresse locale. Dans l'appli, l'adresse du serveur reste
celle du LAN (ex. `http://192.168.1.10:8420`) si le VPN route le LAN, sinon
l'adresse VPN du NAS (ex. `http://100.101.102.103:8420`).

> Piège : la lecture hors de la maison passe par l'upload de ta box. Un film
> 4K remux (60 à 80 Mbit/s) ne tiendra pas en 4G ; c'est le fichier d'origine,
> sans transcodage.

### Télécommande

| Touche | Pendant la lecture | Dans le menu pause |
|---|---|---|
| OK, Lecture/Pause | Pause + menu | Choisir (onglet, chapitre, piste) |
| OK, bouton « Passer l'intro » affiché | Saute le passage | — |
| OK, carte « Épisode suivant » affichée | Lance l'épisode tout de suite | — |
| Gauche / droite | −10 s / +30 s | Se déplacer |
| Retour | Pause + menu (ou écarte la carte « Épisode suivant ») | **Quitter la lecture** (position enregistrée) |
| Suivant (⏭) | Épisode suivant | — |
| *Reprendre* | — | Relance la lecture |

## Séries maison (Naruto Kai, One Pace…)

Les montages de fans n'ont pas de fiche TVDB / TMDB : Sonarr ne peut pas les
gérer. ArrMada les affiche quand même comme des séries :

1. web app › *Réglages › Dossiers vidéo* : déclarer le dossier parent (ex.
   `/mnt/user/medias/mangas`) ;
2. même page › **Séries maison › Déclarer une série** : choisir le dossier de
   la série, la série officielle pour l'affiche (Naruto pour Naruto Kai), le
   nom et la pastille (« Kai »).

Rangement conseillé (le numéro et le titre sont lus dans le nom) :

```text
Naruto Kai/
├── poster.jpg                         # facultatif : sinon l'affiche TMDB
├── Arc 01 - Pays des Vagues/          # un sous-dossier = une saison (un arc)
│   ├── Naruto Kai - 001 - Uzumaki Naruto.mkv
│   ├── Naruto Kai - 001 - Uzumaki Naruto.fr.srt
│   └── Naruto Kai - 002 - Le ninja copieur.mkv
└── Arc 02 - Examen Chunin/
    └── Naruto Kai - 015.mkv           # sans titre : « Épisode 15 »
```

- Saisons : numéro tiré du nom (« Saison 2 », « Arc 03 », « S04 », « 05 - … »),
  sinon l'ordre des dossiers. Sans sous-dossier : tout en saison 1.
- Épisodes : numéro tiré du nom (`- 015`, `Ep 12`, `S02E07`), sinon l'ordre ;
  titre = dernier morceau de `Série - 015 - Titre`.
- **NFO** (`tvshow.nfo`, `<épisode>.nfo`, `season.nfo`) et images locales
  (`poster.jpg`, `fanart.jpg`, `<épisode>-thumb.jpg`) l'emportent : c'est ce
  qu'écrivent Jellyfin, Kodi ou OnePacerr pour One Pace.

> Pièges : le vu suit le chemin du fichier, renommer un épisode remet sa
> reprise à zéro (fixe ton nommage avant de regarder) ; pas de téléchargement
> automatique (Sonarr ne connaît pas ces séries ; pour One Pace, OnePacerr).

## Prérequis côté serveur

- **Jellyfin** déclaré dans ArrMada (*Réglages › Cast & Jellyfin*) : c'est lui
  qui sert les fichiers vidéo. Un titre absent de Jellyfin affiche « Film absent
  de Jellyfin ».
- Le serveur ArrMada relaie la vidéo : la clé Jellyfin (administrateur) ne
  quitte jamais le serveur.
- Pour les vignettes de chapitres : dans Jellyfin, bibliothèque Films ›
  *Gérer la bibliothèque* › cocher **Extraire les images des chapitres**.
- Pour « Passer l'intro » sans chapitres nommés : plugin Jellyfin **Intro
  Skipper** (Jellyfin 10.10 ou plus), comme pour l'add-on Kodi.
- Pour Découvrir : clé TMDB dans les réglages du serveur.

## Réglages conseillés sur la Shield

Les intitulés exacts varient selon la version d'Android TV ; les deux
réglages sont dans *Paramètres › Préférences de l'appareil › Écran et son*
(réglages avancés du son et de l'affichage).

| Réglage (Shield en anglais) | Valeur | Pourquoi |
|---|---|---|
| Son surround / formats audio (*Surround sound*, *Select formats*) | Automatique, ou Dolby TrueHD / DTS-HD cochés à la main | Sans ça, Android décode le son en PCM : l'ampli ne reçoit ni l'Atmos ni le DTS:X |
| Adapter la fréquence d'image (*Match content frame rate*) | Activé | Films en 24p sans saccades |

### Rangées ArrMada sur l'accueil de la Shield

- **À suivre** apparaît tout seul dans la rangée du système (en haut de
  l'accueil) dès qu'un film ou un épisode est commencé dans ArrMada.
- La chaîne **ArrMada · Ajouts récents** est ajoutée d'office (première chaîne
  de l'appli). Pour la déplacer ou la masquer : *Paramètres › Préférences de
  l'appareil › Écran d'accueil › Personnaliser les chaînes* (ou flèche gauche
  sur la chaîne, puis le bouton de déplacement).
- Les cartes suivent le **profil en cours** dans ArrMada (le dernier choisi
  dans « Qui regarde ? ») ; un clic ouvre ArrMada directement sur ce profil.
- Limite : sur **Google TV** (Chromecast, TV Sony / TCL récentes), les chaînes
  d'applis ne sont plus affichées ; seule « À suivre » peut l'être. La Shield
  est sous Android TV : les deux rangées s'affichent.

## Installer l'APK

1. **Récupérer l'APK** : onglet **Actions** du dépôt > workflow **ArrMada
   Android** > dernier run vert > **Artifacts** > `arrmada-android-release` (ou
   `-debug`). Le zip contient l'APK et son empreinte SHA-256.
2. **Sur la Shield**, depuis un PC (`adb` : paquet `android-tools` sur AlmaLinux 9,
   `adb` sur Ubuntu 24.04) :

   ```bash
   # Options développeur : Paramètres › Préférences de l'appareil › À propos ›
   # cliquer 7 fois sur « Build » ; puis activer « Débogage réseau »
   adb connect 192.168.1.50:5555            # accepter la demande sur la TV
   adb install -r arrmada-2.0.0-150-debug.apk
   ```

   Ou, en compilant soi-même : `./build-apk.sh --debug --install 192.168.1.50`.

3. **Premier lancement** : adresse du serveur (taper une adresse à la
   télécommande est pénible ; l'écran affiché, envoie-la depuis le PC avec
   `adb shell input text 'http://192.168.1.10:8420'`), puis appairage depuis
   ton téléphone.

> **APK de test (debug)** : la CI le signe avec une clé jetable, différente à
> chaque build. Pour installer une nouvelle version, désinstalle d'abord
> l'ancienne (`adb uninstall fr.arrmada.app.debug`) ; il faudra refaire
> l'appairage. Une clé release (ci-dessous) supprime cette contrainte.

### Mises à jour (sans adb, ADR-009)

Une fois la **version release** installée (clé release dans les secrets
GitHub, voir [Signature](#signature)), plus besoin d'adb :

1. chaque push sur `android/apk` ou `main` publie l'APK signée dans la release
   GitHub **`android-latest`** ;
2. le serveur ArrMada la rapatrie dans l'heure (`data/apk/`, empreinte
   SHA-256 vérifiée) ;
3. au lancement suivant, chaque TV et téléphone affiche **« ArrMada X est
   disponible »** : *Mettre à jour*, puis confirmer dans l'écran d'Android.

La première fois, Android demande d'autoriser ArrMada à installer des applis
(« sources inconnues ») : l'appli ouvre l'écran qui le permet. *Réglages ›
Rechercher une mise à jour* vérifie tout de suite.

```bash
# Côté serveur : voir ce qui est en miroir, forcer la vérification GitHub
# (clé = ARRMADA_AUTH_SECRET du .env, comme pour les scripts)
KEY="$(grep '^ARRMADA_AUTH_SECRET=' .env | cut -d= -f2-)"
curl -s -H "X-Api-Key: $KEY" http://NAS:8420/api/android/status | jq
curl -s -X POST -H "X-Api-Key: $KEY" http://NAS:8420/api/android/refresh
# APK compilée à la main : la déposer telle quelle (le nom porte la version)
scp android/dist/arrmada-2.8.0-170-release.apk nas:/chemin/arrmada/data/apk/
```

> Piège : une APK **debug** (clé jetable de la CI) ne met jamais à jour une
> appli **release**, et inversement : Android refuse une signature différente.
> L'appli ne se voit proposer que des APK de son type.

## Captures d'écran (sans appareil)

Chaque build dessine les écrans principaux avec des données factices
(Robolectric + Roborazzi, en 1920×1080) et les publie :

- en artifact `arrmada-android-captures` du run ;
- sur la branche **`ci/android-screenshots`** (écrasée à chaque build) :
  `git fetch origin ci/android-screenshots && git archive origin/ci/android-screenshots | tar -x -C /tmp/captures`.

Les images y sont des aplats de couleur : il n'y a pas de réseau pendant les
tests. C'est la mise en page qui est vérifiée.

## Compiler sur ta machine

```bash
# JDK 17+
sudo dnf install -y java-17-openjdk-devel        # AlmaLinux 9
sudo apt install -y openjdk-17-jdk               # Ubuntu 24.04

# SDK Android en ligne de commande (sans Android Studio)
# https://developer.android.com/studio#command-line-tools-only
mkdir -p ~/android-sdk/cmdline-tools
unzip commandlinetools-linux-*_latest.zip -d ~/android-sdk/cmdline-tools
mv ~/android-sdk/cmdline-tools/cmdline-tools ~/android-sdk/cmdline-tools/latest
export ANDROID_HOME=~/android-sdk                # à mettre dans ~/.bashrc
yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "platforms;android-35" "build-tools;35.0.0" "platform-tools"

cd android
./build-apk.sh --debug                         # tests + APK de test
./build-apk.sh --init-keystore                 # une seule fois : clé de release
./build-apk.sh                                 # tests + APK release signé, dans dist/
./build-apk.sh --debug --install 192.168.1.50  # build + installation sur la Shield
```

`./gradlew` télécharge seul la bonne version de Gradle (principe du
« wrapper »). Codes retour de `build-apk.sh` : en tête du script.

## Signature

Android **refuse un APK non signé**, et **refuse une mise à jour signée par une
autre clé**.

- `./build-apk.sh --init-keystore` crée la clé dans `~/.arrmada/` (droits 600).
  **Sauvegarde-la** (NAS, gestionnaire de mots de passe) : perdue, plus aucune
  mise à jour possible sans désinstaller l'appli partout.
- **Jamais dans le dépôt** (`*.jks` est ignoré).
- Pour que la CI signe en release, crée ces secrets du dépôt (*Settings ›
  Secrets and variables › Actions*) :

  | Secret | Valeur |
  |---|---|
  | `ARRMADA_KEYSTORE_BASE64` | `base64 -w0 ~/.arrmada/arrmada-release.jks` |
  | `ARRMADA_KEYSTORE_PASSWORD` | Le mot de passe de la clé |
  | `ARRMADA_KEY_ALIAS` | `arrmada` |

- Numéro de version interne = nombre de commits git (toujours croissant,
  sinon `INSTALL_FAILED_VERSION_DOWNGRADE`). Version affichée :
  `arrmada.versionName` dans `gradle.properties`.

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| *Ce serveur répond, mais ce n'est pas l'API ArrMada* | Port de la web app (3000) au lieu de l'API (8420) | Mettre le port 8420 (celui de l'add-on) |
| *Pas de réponse en 5 secondes* | Mauvaise IP / port, TV sur un autre réseau | Tester `curl http://IP:8420/api/health` depuis le PC |
| *Accès refusé par le serveur (réseau local uniquement)* | Jeton d'appareil utilisé hors du réseau local | Normal hors de la maison (ADR-002). Téléphone : passer par le VPN et déclarer ses adresses dans `DEVICE_TRUSTED_NETWORKS` (voir [Téléphone et tablette](#téléphone-et-tablette)) |
| Jamais de « mise à jour disponible » | Appli de test (debug), pas de clé release dans les secrets GitHub, ou serveur sans accès à GitHub | Installer une fois la version release ; vérifier `/api/android/status` (champ `check.error`) ; à défaut, déposer l'APK dans `data/apk/` |
| *Mise à jour refusée : APK signée par une autre clé* | Appli installée avec une autre clé (APK de test, ancienne clé) | Désinstaller ArrMada une fois, installer la version release par adb ; les suivantes passent seules |
| *Aucun dossier vidéo* dans l'écran Vidéos | Rien de déclaré dans la web app | *Réglages › Dossiers vidéo* : nom + chemin vu par le serveur (sous `/mnt/user`) |
| Dossier vidéo *Introuvable sur le NAS* | Partage démonté, ou chemin vu par l'hôte et non par le conteneur | Vérifier le montage (`/mnt/user` dans `docker-compose.yml`) et le chemin dans la web app |
| Sous-titre `.srt` absent du menu | Nom différent de la vidéo | Même début de nom : `Episode 01.mkv` → `Episode 01.srt` ou `Episode 01.fr.srt` |
| Pas de rangée ArrMada sur l'accueil de la Shield | Option coupée, ou chaîne masquée dans les réglages d'Android TV | *Réglages* d'ArrMada : rangées affichées ; Android : *Écran d'accueil › Personnaliser les chaînes*. Les cartes arrivent après la première synchro (en quittant l'appli) |
| *Aucune TV appairée* dans « Lire sur une TV » | Aucune TV (appli ou Kodi) appairée, ou seulement des téléphones | Appairer la TV ; les téléphones / tablettes ne sont pas proposés |
| *Cette TV n'est plus appairée* | TV supprimée dans la web app | L'appli revient seule à l'écran d'appairage |
| *Film absent de Jellyfin* / *Jellyfin non configuré* | Titre non scanné par Jellyfin, ou Jellyfin pas déclaré | Lancer un scan Jellyfin ; déclarer Jellyfin dans ArrMada |
| *Sortie audio impossible* | Format refusé par l'ampli en passthrough | Choisir une autre piste dans le menu pause (onglet Audio) ; vérifier le réglage « Format audio surround » |
| Piste « non lisible ici » | Ni passthrough ni décodeur pour ce format sur cet appareil | Choisir une autre piste |
| Pas de vignettes dans *Chapitres* | Jellyfin n'a pas extrait les images | Cocher « Extraire les images des chapitres » dans Jellyfin, relancer le scan |
| Sous-titres ASS simplifiés | ExoPlayer ne gère pas les effets ASS avancés | Limite connue (ADR-007) |
| Message *Format m2ts : conversion par Jellyfin…* | Fichier que la TV ne lit pas directement (Blu-ray .m2ts, .iso) | Normal : Jellyfin le remuxe (image intacte ; son TrueHD / DTS converti en Dolby Digital Plus 5.1). Démarrage de 2 à 5 s |
| Image **violette / verte** (films 4K) | Dolby Vision **profil 5** (sans image de secours HDR10) sur un écran qui n'annonce pas le Dolby Vision | Automatique depuis 2.10.2 : Jellyfin convertit en SDR (message *image convertie en SDR*). Vérifier *Réglages › Écran* : sur la Shield, activer *Écran et son › Réglages avancés d'affichage › Faire correspondre la plage dynamique du contenu* (et le Dolby Vision) si la TV le gère. Côté Jellyfin : *Lecture › Transcodage* avec accélération matérielle et **mappage tonal** activés. Sinon, préférer une version HDR10 (format TRaSH « DV (w/o HDR fallback) » à score négatif) |
| *Lecture interrompue* + code (`ERROR_CODE_…`, `fichier .xxx`) | Format que ni la TV ni le remux ne passent | Envoyer le message : le code et l'extension disent ce qui coince |

## Organisation du code

```
android/
├── build-apk.sh                    # tests + APK + signature + installation adb
├── app/build.gradle.kts            # versions figées des bibliothèques
└── app/src/
    ├── main/java/fr/arrmada/app/
    │   ├── MainActivity.kt         # fenêtre unique + navigation entre écrans + Réglages
    │   ├── ArrMadaApplication.kt   # objets partagés (réglages, client HTTP, images)
    │   ├── data/                   # API (client, modèles JSON, appels, caches) + règles en Kotlin pur :
    │   │                           #   SeriesLogic (Lire la suite), PlaybackLogic (intro, générique),
    │   │                           #   DownloadLogic (feuille Télécharger), CaseLogic (boîtier),
    │   │                           #   ImageSizes (taille des images TMDB)
    │   ├── home/                   # rangées sur l'accueil Android TV (À suivre, chaîne), tâche de fond
    │   ├── update/                 # mises à jour proposées par le serveur (téléchargement, installeur)
    │   └── ui/
    │       ├── theme/              # charte de l'add-on (couleurs, police)
    │       ├── components/         # affiches, boutons, rangées, fond « Ken Burns »,
    │       │                       #   format d'écran (Screen.kt : TV / tablette / téléphone, tap)
    │       ├── shell/              # navigation tactile (barre du bas, colonne, « Plus »)
    │       ├── videos/             # écran Vidéos : explorateur des dossiers hors médiathèque
    │       ├── setup/              # adresse du serveur, appairage
    │       ├── home/               # accueil, grilles Films / Séries, Découvrir
    │       ├── detail/             # fiche film (boîtier + disque animé), écran Série
    │       ├── request/            # recherche (et dictée), feuille Télécharger
    │       └── player/             # lecteur ExoPlayer, menu pause, pistes
    └── test/                       # tests JVM + captures d'écran (Robolectric)
```

Côté serveur : `backend/app/api/tv.py` et `backend/app/services/tv_playback.py` ;
mises à jour : `backend/app/api/android.py` et `backend/app/services/android_update.py` ;
écran Vidéos : `backend/app/api/videos.py` et `backend/app/services/video_files.py` ;
séries maison : `backend/app/api/local_series.py` et `backend/app/services/local_series.py`
(infos de lecture, relais du flux Jellyfin, remux HLS des .m2ts / .iso,
vignettes de chapitres).
