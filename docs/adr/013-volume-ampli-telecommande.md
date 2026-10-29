# ADR-013 : volume de l'ampli à la télécommande, par un service d'accessibilité

## Statut

**Accepté** le 28/10/2026, à la demande de régler le son de l'ampli Yamaha avec la télécommande de la TV.

## Contexte

Le son des films passe par l'ampli Yamaha de la pièce (salon 5.1, salle de
cinéma 7.2.2). ArrMada sait déjà le piloter : préréglage de la pièce au
lancement d'un film, réglages audio du menu pause (programme, voix, mode
nuit, Vol + / Vol −), via `POST /api/yamaha/control` et l'API YXC de l'ampli.
Chaque TV appairée pilote l'ampli de **sa** pièce (ADR-003 § 6) ; une pièce
sans ampli répond `no_amp`.

Ce qui manque : les touches **Vol + / Vol − / Muet** de la télécommande. La
demande était de les capter dans l'appli TV et de les envoyer à l'ampli par
le serveur.

**Une appli Android TV ne reçoit jamais ces touches.** Sur un appareil
« leanback » (la Shield), `PhoneWindowManager` les traite lui-même
(`mUseTvRouting` : « On TVs … volume keys never go to the foreground app »)
et les transmet au système audio (HDMI-CEC vers la TV ou l'ampli, ou volume
interne). `dispatchKeyEvent` de l'activité ne les voit pas ; un
`VolumeProvider` de session média non plus (la voie TV appelle
`AudioService.handleVolumeKey` directement).

## Décision

1. **Un service d'accessibilité dans l'APK** (`amp/AmpVolumeService`), avec
   le filtre des touches (`flagRequestFilterKeyEvents`). Le filtre
   d'accessibilité passe **avant** le traitement du système : le service
   garde Vol + / Vol − / Muet et les envoie au serveur. L'utilisateur
   l'active **une fois** dans Paramètres › Accessibilité ; ArrMada ne peut
   pas le faire à sa place, et c'est voulu.
2. **Le serveur reste le seul à parler à l'ampli** : même route
   `POST /api/yamaha/control`, même choix de l'ampli par la pièce de la TV.
   `mute` accepte `"toggle"` (la télécommande n'a qu'une touche), et le
   volume et le muet renvoient le nouveau niveau (`volume_pct`, `mute`,
   `actual_db`) que la TV affiche brièvement (« Ampli : 42 % (−38,5 dB) »).
3. **Rafales regroupées** : une touche maintenue envoie un seul
   `volume_step` toutes les 150 ms (pas de 2 dB par appui, comme Vol + du
   menu pause), au lieu d'une requête par répétition.
4. **Garde-fous** : rien n'est intercepté si le réglage est coupé, si la TV
   n'est pas appairée ou sur un téléphone. Après `no_amp`, les touches
   reviennent au système pendant 10 min ; après une panne (serveur ou ampli
   injoignable), pendant 1 min. Le volume de la TV n'est donc jamais perdu.

## Alternatives écartées

- **Capter les touches dans l'activité** (`dispatchKeyEvent`, `onKeyDown`) :
  impossible sur Android TV, voir le contexte.
- **Session média en volume distant** (`setPlaybackToRemote`) : ignorée par
  la voie des touches volume sur TV ; et elle ne jouerait que pendant une
  lecture dans ArrMada.
- **HDMI-CEC / IR seuls**, sans code : c'est la meilleure solution quand elle
  est possible (aucune latence, aucun réseau) et elle reste documentée dans
  les Réglages de l'appli : télécommande de la Shield réglée en IR sur
  l'ampli, ou HDMI-CEC de l'ampli (« HDMI Control ») avec la TV en ARC. Elle
  dépend du matériel (TV, ampli, câbles) et ne marche pas partout : le
  service couvre les autres cas.
- **Remapper d'autres touches** (chaînes +/−) : pas intuitif, et ces touches
  n'existent pas sur toutes les télécommandes.

## Conséquences

- Les touches volume règlent l'ampli **aussi dans les autres applis**
  (Netflix, YouTube…) tant que le service est actif : c'est ce qu'on attend
  d'une télécommande d'ampli. Le réglage de l'appli permet de revenir au
  volume de la TV sans désactiver le service.
- Un service d'accessibilité est une permission forte. Celui-ci ne déclare
  que le filtre des touches (`canRetrieveWindowContent="false"`) et ne lit
  que trois codes de touche ; sa description dans les Paramètres le dit.
  L'APK est distribuée hors Play Store (ADR-009), la politique du Play Store
  sur l'accessibilité ne s'applique pas.
- Latence : un aller-retour réseau TV → serveur → ampli (quelques dizaines de
  millisecondes sur le réseau local), contre zéro en IR ou CEC.
