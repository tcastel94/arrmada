# ArrMada Android (TV, tablette, téléphone)

Appli native ArrMada pour **Android TV** (Shield en tête), les **tablettes**
et les **téléphones**, avec son propre lecteur vidéo. L'interface reprend celle de l'add-on Kodi : mêmes couleurs,
police condensée, focus bleu qui grossit, fond qui zoome lentement. Les choix
sont expliqués dans l'[ADR-007](../docs/adr/007-appli-android-native.md).

> Une seule APK : elle reconnaît l'écran au lancement (TV, tablette ou
> téléphone) et adapte la navigation. Voir [Téléphone et tablette](#téléphone-et-tablette).

## Ce que fait la version 2.6 (phases 1 à 4 de l'ADR-007)

| Écran | Contenu |
|---|---|
| **Mise en route** | Adresse du serveur (celle de l'add-on Kodi, port **8420**), testée sur `/api/health`. Puis appairage par **code + QR code**, validé dans la web app (*Réglages › Appareils*), exactement comme une TV sous Kodi |
| **Accueil** | Menu du haut, héros (logo ou titre, méta, résumé, « Reprendre à… ») sur le fond de l'élément sélectionné, rangées **Reprendre** (états vu / reprise partagés avec les TV sous Kodi), **Ajouts récents**, **Pour toi**, **Bientôt** |
| **Films / Séries** | Murs d'affiches de 7 colonnes : *Récents*, *A à Z*, *Année*, *4K* (films) ou *Mieux notés* (séries) |
| **Série** | Saisons en pastilles (« 3/10 vus », « 4/10 sur le NAS »), épisodes en vignettes Jellyfin : **vu**, barre de reprise, **MANQUANT**, **À VENIR**. Bouton **Lire la suite** (reprend l'épisode commencé, sinon la suite du dernier vu). Appui long sur un épisode : *Lire depuis le début*, *Marquer comme vu / non vu*. OK sur un manquant : Sonarr le cherche |
| **Découvrir** | Tendances TMDB (films, séries) et « Parce que tu as… » : OK ouvre la fiche si le titre est déjà là, sinon la feuille *Télécharger* |
| **Rechercher** | Au clavier ou **à la voix** (bouton *Dicter*, ou touche recherche / micro de la télécommande quand elle arrive jusqu'à l'appli) : *Dans la médiathèque*, *Aussi dans Radarr / Sonarr*, *À demander* |
| **Télécharger** | La feuille de l'add-on : un film en un bouton ; une série en entier, une saison ou des épisodes cochés ; **Pour ce soir** (passe devant les autres téléchargements). Le bouton dit ce qui part (« Télécharger S02E05 », « Télécharger 3 épisodes ») |
| **Fiche film** | Logo, notes TMDB / IMDb / Rotten Tomatoes, pastilles **4K / Dolby Vision / Atmos / 7.1**, résumé, *Reprendre à…* / *Depuis le début*, bande-annonce (appli YouTube), distribution. À droite, le **boîtier de l'add-on** (Blu-ray bleu, 4K ULTRA HD noir, DVD, transparent si le fichier n'est pas là) et son **disque qui sort en roulant** puis tourne (rond imprimé fanart.tv, sinon l'affiche en anneau) |
| **Lecteur** | Fichier d'origine **sans transcodage**, son HD envoyé tel quel à l'ampli (passthrough), piste française préférée. Gauche / droite : −10 s / +30 s. Position enregistrée toutes les 30 s, en pause et en quittant ; « vu » à 90 %. Préréglage Yamaha de la pièce au lancement. Formats qu'ExoPlayer n'ouvre pas (**.m2ts** de Blu-ray, **.iso**…) : Jellyfin change le conteneur à la volée (**remux**, image intacte), automatiquement **Passer l'intro / le récap** (chapitres nommés du fichier, sinon marqueurs Jellyfin), carte **Épisode suivant dans 10 s** au générique de fin (ou 30 s avant la fin) puis enchaînement |
| **Menu pause** (façon Apple TV) | Logo, pastilles, **heure de fin**, progression, onglets **Chapitres** (vignettes, saut direct), **Infos**, **Distribution**, **Sous-titres** (pistes nommées : langue, forcés, format), et un bouton **Audio** qui ouvre les **Réglages audio** : **son conseillé** selon le film et les enceintes de la pièce (salon 5.1, salle de cinéma 7.2.2, TV sans ampli) avec **décodage auto**, piste audio (Dolby TrueHD, DTS-HD, 7.1, « non lisible ici »), ampli : programme sonore, volume, **voix plus claires**, **mode nuit**, **basses** (Extra Bass, niveau du caisson) |
| **Téléchargements** | Cartes **Pour ce soir** (« Prêt vers 21:02 », étapes jusqu'à *Prêt à regarder*) et file Radarr / Sonarr (état, %, reste, débit). OK : **Débloquer**, Passer en tête, Pause / Reprendre, Relancer la recherche, Fiche, Annuler ma demande. *Pause sauf ce soir*, *Tout reprendre* |
| **Bulles et annonces** | Bulles en bas à droite (importé sur le NAS, téléchargement lancé, import bloqué), retenues pendant un film puis résumées (« Pendant ta séance »). Pop-up **Prêt à regarder** (Regarder / Plus tard), alerte **caméra** avec photo, **Lire sur la TV** depuis la web app |
| **Tableau de bord** | Salutation, compteurs animés (films, séries, stockage, téléchargements), téléchargements en cours, services, ajouts récents ; **intro animée** de l'add-on au lancement |
| **Ce soir** | Ce qui sera fini avant 22:00, 22:30… (« fini vers 22:14 ») |
| **Applis** | Applis Android installées sur la TV, lancées avec OK |
| **Profils famille** (ADR-008) | **Qui regarde ?** au lancement, avatar dans le menu pour changer : chacun sa rangée Reprendre, ses vus, son « Pour toi », ses demandes (« Prêt à regarder » le suit sur n'importe quelle TV). Gestion dans la web app (*Réglages › Profils famille*) |
| **Bande-annonce en fond** | Sur la fiche film, la bande-annonce rangée sur le NAS se lance sans le son après 2,5 s |

Pas encore là (phase 4, voir l'ADR) : option « écran d'accueil de la Shield ».

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
| *Aucune TV appairée* dans « Lire sur une TV » | Aucune TV (appli ou Kodi) appairée, ou seulement des téléphones | Appairer la TV ; les téléphones / tablettes ne sont pas proposés |
| *Cette TV n'est plus appairée* | TV supprimée dans la web app | L'appli revient seule à l'écran d'appairage |
| *Film absent de Jellyfin* / *Jellyfin non configuré* | Titre non scanné par Jellyfin, ou Jellyfin pas déclaré | Lancer un scan Jellyfin ; déclarer Jellyfin dans ArrMada |
| *Sortie audio impossible* | Format refusé par l'ampli en passthrough | Choisir une autre piste dans le menu pause (onglet Audio) ; vérifier le réglage « Format audio surround » |
| Piste « non lisible ici » | Ni passthrough ni décodeur pour ce format sur cet appareil | Choisir une autre piste |
| Pas de vignettes dans *Chapitres* | Jellyfin n'a pas extrait les images | Cocher « Extraire les images des chapitres » dans Jellyfin, relancer le scan |
| Sous-titres ASS simplifiés | ExoPlayer ne gère pas les effets ASS avancés | Limite connue (ADR-007) |
| Message *Format m2ts : conversion par Jellyfin…* | Fichier que la TV ne lit pas directement (Blu-ray .m2ts, .iso) | Normal : Jellyfin le remuxe (image intacte ; son TrueHD / DTS converti en Dolby Digital Plus 5.1). Démarrage de 2 à 5 s |
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
    │   └── ui/
    │       ├── theme/              # charte de l'add-on (couleurs, police)
    │       ├── components/         # affiches, boutons, rangées, fond « Ken Burns »,
    │       │                       #   format d'écran (Screen.kt : TV / tablette / téléphone, tap)
    │       ├── shell/              # navigation tactile (barre du bas, colonne, « Plus »)
    │       ├── setup/              # adresse du serveur, appairage
    │       ├── home/               # accueil, grilles Films / Séries, Découvrir
    │       ├── detail/             # fiche film (boîtier + disque animé), écran Série
    │       ├── request/            # recherche (et dictée), feuille Télécharger
    │       └── player/             # lecteur ExoPlayer, menu pause, pistes
    └── test/                       # tests JVM + captures d'écran (Robolectric)
```

Côté serveur : `backend/app/api/tv.py` et `backend/app/services/tv_playback.py`
(infos de lecture, relais du flux Jellyfin, remux HLS des .m2ts / .iso,
vignettes de chapitres).
