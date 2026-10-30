# ADR-009 : Mises à jour de l'appli Android sans adb

## Statut

**Accepté** le 21/10/2026 (suite de l'[ADR-007](007-appli-android-native.md)).

## Contexte

L'appli ArrMada s'installe hors Play Store (« sideload ») : jusqu'ici, chaque
nouvelle version passait par `adb install` depuis un PC, TV par TV, téléphone
par téléphone. Avec plusieurs TV et les téléphones de la famille, ça ne tient
pas. L'add-on Kodi, lui, se met à jour tout seul par le dépôt Kodi que sert le
serveur ArrMada (`/kodi/repo`) : on veut la même chose.

Contraintes :

- Android **n'installe une mise à jour que si elle est signée par la même
  clé** : il faut une clé « release » fixe (voir `android/README.md`,
  « Signature »), jamais la clé de test jetable de la CI.
- Android **confirme toujours** l'installation d'une appli hors Play Store
  (sauf appli système) : c'est voulu, on ne le contourne pas.
- Les appareils ne parlent qu'au serveur ArrMada (jeton d'appareil, réseau
  local ou VPN, ADR-002) ; ils n'ont pas à joindre GitHub.

## Décision

Un circuit en trois étages, comme un miroir de paquets (`reposync` puis `dnf
upgrade`) :

| Étage | Qui | Quoi |
|---|---|---|
| 1. Publication | CI GitHub (`android.yml`) | APK signée avec la clé release → release GitHub **`android-latest`** (pré-version), avec son fichier `.sha256`. Seulement sur un push, jamais l'APK de test |
| 2. Miroir | Serveur ArrMada (tâche horaire) | Lit la release, télécharge l'APK si elle est plus récente que celles de `data/apk`, **vérifie l'empreinte SHA-256** (fichier `.part` renommé à la fin), garde les 2 dernières |
| 3. Installation | Appli (TV, téléphone, tablette) | Au lancement : `GET /api/android/update?version_code=…&build_type=release`. Si plus récent : fenêtre « ArrMada X est disponible » → téléchargement depuis le serveur, empreinte vérifiée, installeur d'Android (session `PackageInstaller`) → confirmation d'Android |

Détails :

- **Version** : le nom de fichier de `build-apk.sh` la porte
  (`arrmada-2.8.0-160-release.apk` : version affichée, numéro interne =
  nombre de commits, type). Pas besoin de lire le binaire de l'APK.
- **APK compilée à la main** : la déposer dans `data/apk/` (même nom) ; elle est
  proposée si elle est la plus récente. `ANDROID_UPDATE_REPO=` (vide) coupe
  GitHub et ne garde que ce dépôt manuel.
- **Type** : une appli `release` ne se voit proposer que des APK `release`
  (une APK de test, signée par une autre clé, échouerait).
- **API** : `/api/android/update` et `/api/android/apk/{fichier}` ouverts aux
  jetons d'appareil (lecture seule, nom exact d'une APK du dossier) ;
  `POST /api/android/update/check` aussi (bouton de l'appli, voir plus bas) ;
  `/api/android/status` et `/api/android/refresh` réservés à la web app.
- **Appli** : vérification une fois par lancement (jamais pendant un film),
  « Plus tard » la repousse au lancement suivant, *Réglages › Rechercher une
  mise à jour* force la vérification : le serveur revérifie alors GitHub avant
  de répondre (`POST /api/android/update/check`), sans attendre sa
  vérification horaire. Limité à une vérification GitHub toutes les 2 minutes
  (quota de l'API GitHub sans jeton : 60 appels par heure) ; GitHub
  injoignable = réponse avec l'APK déjà présente. Un serveur plus ancien
  (route inconnue) répond comme avant. La première fois, Android demande
  d'autoriser ArrMada à installer des applis : l'appli ouvre l'écran voulu.

## Alternatives écartées

| Option | Pourquoi non |
|---|---|
| Les appareils interrogent GitHub directement | Chaque TV sortirait sur Internet ; plus de point de contrôle sur le serveur ; débit d'API GitHub limité sans jeton |
| Téléversement manuel dans la web app | Reste une étape à la main à chaque version (télécharger l'artifact, le déposer) ; gardé sous forme de dossier `data/apk` pour les APK locales |
| Lanceur / appli système, Play Store privé | Demande root ou un compte développeur Google ; disproportionné pour une maison |

## Conséquences

- ➕ Une version poussée sur `android/apk` (ou `main`) arrive sur toutes les TV
  et téléphones en une heure au plus, sans PC ni adb.
- ➕ Empreinte vérifiée deux fois (serveur, appareil) : une APK tronquée ou
  modifiée n'est jamais installée.
- ➖ Il faut la **clé release** dans les secrets GitHub ; sans elle, la CI ne
  produit que l'APK de test et rien n'est publié.
- ➖ La première installation de la version « release » se fait encore par
  adb (une seule fois par appareil). L'APK de test, autre nom de paquet
  (`fr.arrmada.app.debug`), reste installable à côté mais ne se met pas à
  jour toute seule.
- ➖ Le serveur doit pouvoir joindre `api.github.com` et
  `objects.githubusercontent.com` (sinon : dépôt manuel dans `data/apk`).
