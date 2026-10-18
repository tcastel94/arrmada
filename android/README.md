# ArrMada Android

Appli Android d'ArrMada : **un seul APK** pour le téléphone, la tablette et
Android TV (Shield, Chromecast avec Google TV…).

L'appli affiche l'interface web de ton serveur ArrMada. Elle ne contient ni
données ni logique métier : tout reste sur le serveur, comme dans le
navigateur. Une mise à jour du serveur met donc l'appli à jour, sans
réinstaller l'APK. Voir l'[ADR-006](../docs/adr/006-appli-android.md) pour le
pourquoi de ce choix.

> **Et Kodi ?** Sur la Shield, l'appli Kodi reste **le lecteur** (ADR-004) :
> c'est elle qui lit les films, gère le son, les sous-titres et la reprise.
> L'appli Android, c'est **la console de gestion** sur la TV : tableau de bord,
> demandes, téléchargements, réglages. Les deux cohabitent.

## Ce que l'appli ajoute à un simple navigateur

| Besoin | Ce que fait l'appli |
|---|---|
| Pas de barre d'adresse | L'adresse du serveur est saisie une fois, testée, puis mémorisée |
| Touche **Retour** | Ferme d'abord la fenêtre ouverte (modale, menu), sinon page précédente, sinon menu *Recharger / Changer de serveur / Quitter* |
| **Télécommande TV** | Flèches = déplacer la sélection (liseré bleu) ; OK = cliquer ; OK sur un champ = clavier à l'écran ; touche Menu (≡) = menu de l'appli |
| Lisibilité TV | Largeur d'affichage réglable : *Grande* (960), *Normale* (1280), *Compacte* (1600) |
| Serveur arrêté | Écran *Serveur injoignable* avec *Réessayer* et *Changer de serveur* (pas de page d'erreur grise) |
| Liens externes (TMDB, IMDb, YouTube) | Ouverts dans le navigateur de l'appareil |
| Bandes-annonces | Plein écran |

## Installer l'APK

### 1. Récupérer l'APK

Le plus simple : **GitHub Actions** compile l'APK à chaque modification de
`android/`. Onglet **Actions** du dépôt > workflow **ArrMada Android** > dernier
run vert > section **Artifacts** > `arrmada-android-release` (ou `-debug`).
Le zip contient l'APK et son empreinte SHA-256.

### 2a. Sur un téléphone ou une tablette

1. Copie l'APK sur l'appareil (Drive, câble, mail…) et ouvre-le.
2. Android demande d'autoriser « l'installation d'applis inconnues » pour
   l'appli qui ouvre le fichier (Fichiers, Chrome…) : accepte.

### 2b. Sur Android TV (Shield) avec adb

Il n'y a pas de gestionnaire de fichiers pratique sur une TV : on installe à
distance depuis un PC, avec `adb` (paquet `android-tools` sur AlmaLinux 9,
`adb` sur Ubuntu 24.04).

1. Sur la Shield, active les options développeur : **Paramètres > Préférences
   de l'appareil > À propos**, clique 7 fois sur **Build**.
2. **Paramètres > Préférences de l'appareil > Options pour les développeurs** :
   active **Débogage réseau** (ou *Débogage USB* selon la version). Note l'IP
   de la Shield (**À propos > État**).
3. Depuis le PC :

   ```bash
   adb connect 192.168.1.50:5555          # accepte la demande affichée sur la TV
   adb install -r arrmada-1.0.0-123-release.apk
   ```

   Ou en une commande si tu compiles toi-même : `./build-apk.sh --install 192.168.1.50`.
4. L'appli apparaît dans la rangée **Applications** du lanceur, avec sa bannière.

**Astuce** : taper une adresse à la télécommande est pénible. L'écran de
connexion ouvert sur la TV, envoie le texte depuis le PC :

```bash
adb shell input text 'http://192.168.1.10:3000'
```

### 3. Premier lancement

Saisis l'adresse de l'**interface web** ArrMada, la même que dans ton
navigateur (ex. `http://192.168.1.10:3000`), puis *Tester et enregistrer*.
Le test vérifie que le serveur répond **et** que c'est bien ArrMada (erreur
classique : le port de l'API, 8420, au lieu de celui de l'interface).

Pour changer de serveur plus tard : touche **Retour** sur la première page (ou
touche **Menu** de la télécommande) > *Changer de serveur*.

## Compiler sur ta machine

Pas obligatoire (la CI le fait), mais utile pour tester une modification.

### Prérequis

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
```

Pas besoin d'installer Gradle : `./gradlew` télécharge la bonne version tout
seul (c'est le principe du « wrapper »).

### Commandes

```bash
cd android
./build-apk.sh --debug                         # APK de test, sans clé
./build-apk.sh --init-keystore                 # une seule fois : crée la clé de release
./build-apk.sh                                 # APK release signé, dans dist/
./build-apk.sh --debug --install 192.168.1.50  # build + installation sur la Shield
```

Le script lance les tests unitaires avant de produire l'APK, et s'arrête au
premier échec (codes retour documentés en tête de `build-apk.sh`).

## Signature : à lire une fois

Android **refuse d'installer un APK non signé**, et **refuse une mise à jour
signée par une autre clé**. Deux types d'APK :

| | `--release` | `--debug` |
|---|---|---|
| Clé | La tienne, créée par `--init-keystore`, dans `~/.arrmada/` | Clé de debug générée par le SDK, propre à chaque machine |
| Identifiant | `fr.arrmada.app` | `fr.arrmada.app.debug` (installé **à côté**) |
| Mises à jour | Par-dessus, en gardant l'adresse et la session | Seulement depuis la même machine. En CI la clé change à chaque run : désinstaller avant |

Pièges :

- **Ne perds pas la clé release** (ni son mot de passe). Sans elle, impossible
  de mettre à jour l'appli : il faut la désinstaller sur chaque appareil.
  Sauvegarde `~/.arrmada/arrmada-release.jks` (NAS, gestionnaire de mots de passe).
- **Ne la committe jamais** : `*.jks` est dans `.gitignore`.
- Pour que la CI signe en release, crée ces **secrets** du dépôt (*Settings >
  Secrets and variables > Actions*) :

  | Secret | Valeur |
  |---|---|
  | `ARRMADA_KEYSTORE_BASE64` | `base64 -w0 ~/.arrmada/arrmada-release.jks` |
  | `ARRMADA_KEYSTORE_PASSWORD` | Le mot de passe de la clé |
  | `ARRMADA_KEY_ALIAS` | `arrmada` |

- Le **numéro de version interne** (versionCode) est le nombre de commits git :
  il doit toujours augmenter, sinon Android refuse la mise à jour
  (`INSTALL_FAILED_VERSION_DOWNGRADE`). Compile depuis un clone **complet**
  (pas `git clone --depth 1`). La version affichée se change dans
  `gradle.properties` (`arrmada.versionName`).

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| *Pas de réponse en 5 secondes* | Mauvaise IP / port, appareil sur un autre réseau (Wi-Fi invité, 4G) | Vérifie avec le navigateur de l'appareil, ou passe par le VPN |
| *Ce serveur répond, mais ce n'est pas l'interface ArrMada* | Port de l'API (8420) au lieu de celui de l'interface | Mets le port de l'interface web |
| *Nom inconnu sur le réseau* | Nom `.local` / nom Unraid non résolu par Android | Utilise l'IP |
| *Certificat HTTPS refusé* | Reverse proxy avec CA maison | Installe la CA : *Paramètres > Sécurité > Chiffrement et identifiants > Installer un certificat* |
| L'appli n'apparaît pas sur la TV | Lanceur tiers qui ignore les applis TV | Elle est dans *Paramètres > Applications* ; le lanceur Google TV l'affiche |
| *Aucun navigateur sur cet appareil* | Normal sur Android TV | Ouvre le lien depuis le téléphone |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | APK signé par une autre clé | `adb uninstall fr.arrmada.app`, puis réinstalle |
| Écran figé ou blanc sur TV | WebView de la TV trop ancien | Mets à jour *Android System WebView* depuis le Play Store |

Pour inspecter la page dans un APK `--debug` : téléphone en USB, Chrome sur le
PC, `chrome://inspect`.

## Organisation du code

```
android/
├── build-apk.sh                 # build + tests + signature + installation adb
├── app/build.gradle.kts         # versions, signature, dépendances (3 bibliothèques AndroidX)
├── app/src/main/
│   ├── AndroidManifest.xml      # permissions, lanceurs téléphone + TV, bannière
│   ├── java/fr/arrmada/app/
│   │   ├── MainActivity.kt      # le WebView : Retour, erreurs, plein écran, liens externes
│   │   ├── SetupActivity.kt     # écran de connexion
│   │   ├── ServerUrl.kt         # nettoyage / comparaison d'adresses (testé)
│   │   ├── ServerProbe.kt       # test de connexion
│   │   ├── ServerConfig.kt      # réglages enregistrés, détection TV
│   │   └── Insets.kt            # marges des barres système (Android 15)
│   ├── assets/
│   │   ├── arrmada-bridge.js    # touche Retour → ferme la modale (tous appareils)
│   │   └── tv-navigation.js     # flèches + OK, focus visible, largeur TV
│   └── res/                     # écrans, textes, couleurs, icônes
├── app/src/test/                # tests Kotlin (JVM, sans appareil)
└── tests/tv-navigation/         # tests des scripts injectés, dans Chromium
```

Icônes et bannière TV : **générées** par `python3 branding/export.py` à partir
du logo SVG, jamais retouchées à la main.

Tester les scripts injectés en local (Playwright, comme la CI) :

```bash
npm install --no-save --prefix /tmp/pw playwright@1.56.1
/tmp/pw/node_modules/.bin/playwright install chromium
NODE_PATH=/tmp/pw/node_modules node android/tests/tv-navigation/run.cjs
```
