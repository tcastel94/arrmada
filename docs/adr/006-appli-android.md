# ADR-006 : Appli Android (téléphone, tablette, Android TV)

## Statut

**Accepté** le 18/10/2026. Complète l'[ADR-004](004-arrmada-remplace-kodi.md)
sans le contredire (voir « Rapport avec Kodi »).

## Contexte

On veut ArrMada en **APK** installable sur téléphone, tablette et Android TV,
plutôt qu'un onglet de navigateur : icône sur l'écran d'accueil, appli dans le
lanceur de la TV, touche Retour qui se comporte comme dans une appli.

Contraintes relevées dans le code :

- La web app (Next.js 14, `output: "standalone"`) a besoin de son serveur Node :
  elle ne peut pas être embarquée telle quelle dans un APK.
- Le navigateur appelle l'API sur `<hôte de la page>:8420`
  (`frontend/src/lib/constants.ts`) : l'appli doit charger la page depuis le
  serveur pour que ces appels fonctionnent.
- Serveur de homelab : souvent en **HTTP** sur une IP privée, parfois derrière
  un reverse proxy HTTPS avec une **autorité de certification maison**.
- Sur TV, ni souris ni écran tactile : tout doit se piloter aux flèches et à OK.

## Options étudiées

| Option | Verdict |
|---|---|
| **A. Coquille native minimale** : une appli Kotlin d'une poignée de fichiers, un WebView qui charge l'adresse du serveur | ✅ **Retenue** |
| B. Capacitor (framework qui emballe un site web dans une appli) en mode « URL distante » | ❌ Proposé au départ, écarté à l'analyse. Les besoins réels (écran d'erreur natif, touche Retour, clavier TV, menu) demandent de toute façon du code natif. Capacitor ajouterait une chaîne Node + npm au build Android, et un outil de migration à chaque version majeure, sans rien apporter puisqu'on n'utilise aucun de ses plugins |
| C. Capacitor avec la web app embarquée (export statique) | ❌ Il faudrait réécrire une partie de la web app (rendu serveur), et republier l'APK à chaque évolution de l'interface |
| D. TWA (PWA empaquetée par Chrome) | ❌ Exige du HTTPS public et un fichier de vérification sur le domaine : inadapté à `http://192.168.x.x` |
| E. Appli native complète (interface refaite en Kotlin) | ❌ Deuxième interface à maintenir en parallèle de la web app |

## Décision

### 1. Architecture

L'APK est un **navigateur dédié** : il ne contient ni données ni logique
métier. Analogie infra : un reverse proxy embarqué, le serveur fait tout le
travail. Conséquence directe : **une mise à jour du serveur met l'appli à
jour**, sans republier l'APK. L'APK ne change que pour son propre
comportement (TV, Retour, erreurs).

| Brique | Rôle |
|---|---|
| `SetupActivity` | Saisie de l'adresse, test (le serveur répond-il, est-ce ArrMada ?), taille TV |
| `MainActivity` | WebView, touche Retour, menu, écran d'erreur, plein écran vidéo, liens externes |
| `assets/arrmada-bridge.js` | Retour → ferme la modale ouverte (Échap simulé), tous appareils |
| `assets/tv-navigation.js` | TV : navigation spatiale aux flèches, OK, focus visible, largeur d'affichage |

Les scripts sont injectés **avant** le code de la page (`addDocumentStartJavaScript`,
repli sur la fin du chargement sur les vieux WebView), et **uniquement** dans
les pages du serveur configuré.

### 2. Android TV sans toucher à la web app

La web app est déjà bien construite pour le clavier : presque tout ce qui est
cliquable est un vrai `<button>` ou `<a>` (relevé du 18/10/2026 : 2 `<div>`
cliquables, dont une déjà en `role="button"`). Le script TV peut donc s'en
contenter :

- **Flèches** : l'élément cliquable le plus proche dans la direction (score =
  distance + 4 × décalage latéral, la voisine de la même rangée gagne) ; rien
  dans cette direction ou cible très loin → la page défile.
- Les composants qui gèrent déjà leurs flèches (menus, listes Radix) marquent
  la touche traitée : le script s'efface.
- **OK** sur un champ : ouvre le clavier à l'écran (appel natif, car un focus
  donné par script ne l'ouvre pas sur TV).
- **Largeur** : une TV 1080p se présente comme un écran de 960 px. On impose
  1280 par défaut (mise en page « portable »), réglable : 960 / 1280 / 1600.

### 3. Sécurité

- HTTP en clair autorisé (impossible de lister les IP privées à l'avance),
  mais l'appli ne charge **que** le serveur saisi : tout autre lien part dans
  le navigateur de l'appareil.
- Certificats installés par l'utilisateur acceptés (CA de homelab) ; un
  certificat invalide est **toujours refusé**, jamais accepté en silence.
- Pont natif exposé à la page (TV uniquement) réduit à deux fonctions sans
  risque : « le clavier est-il ouvert ? » et « ouvre le clavier ».
- Pas de sauvegarde Android des données de l'appli (`allowBackup="false"`).

### 4. Build et distribution

- Gradle + 3 bibliothèques AndroidX, versions figées. `build-apk.sh` : tests,
  APK, vérification de signature, installation `adb`.
- CI `android.yml` : tests des scripts injectés dans Chromium (moteur du
  WebView), tests Kotlin, APK publié en artifact.
- Signature release par une clé **hors dépôt** (`~/.arrmada/`, secrets GitHub
  pour la CI). Sans secret, la CI produit un APK de test.
- Sideload (pas de Play Store) : usage familial, pas de compte développeur.

## Rapport avec Kodi (ADR-004)

L'ADR-004 a écarté une « appli Android TV native » **comme lecteur** (option B :
refaire le passthrough audio, le HDR, les sous-titres PGS…). Cette décision
tient toujours : l'APK ArrMada **ne lit pas de vidéo**. Sur la Shield, Kodi
reste le lecteur et l'appli Kodi reste l'interface du canapé ; l'APK est la
**console de gestion** (tableau de bord, demandes, téléchargements, réglages)
disponible aussi sur la TV.

## Conséquences

- ➕ Une seule base de code d'interface (la web app) pour navigateur, téléphone,
  tablette et TV.
- ➕ APK léger (~3 Mo), presque jamais à republier.
- ➖ Sans serveur joignable, l'appli n'affiche rien (pas de mode hors ligne).
- ➖ La navigation TV dépend de la structure de la web app : une future
  `<div onClick>` sans `role="button"` sera inatteignable à la télécommande.
  Règle pour la web app : un élément cliquable est un `<button>`, un `<a>`, ou
  porte `role="button"` + `tabIndex={0}`.

## Pistes ultérieures

- Signaler l'appli à la web app (l'identifiant du navigateur contient
  `ArrMadaAndroid/<version> (TV|Mobile)`) pour adapter l'affichage.
- Notifications push natives (téléchargement terminé) : nécessiterait un
  service en arrière-plan ou Firebase.
