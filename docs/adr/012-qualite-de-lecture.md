# ADR-012 : qualité de lecture, un flux 1080p unique choisi par la TV

## Statut

**Accepté** le 26/10/2026, après des films 4K qui se figeaient sur une NVIDIA Shield liée à 100 Mb/s.

## Contexte

L'appli Android TV lit le **fichier d'origine** relayé depuis Jellyfin
(`/api/tv/stream/{id}`, ADR-007). Une Shield branchée en Ethernet s'est
retrouvée sur un lien à **100 Mb/s** à cause d'un câble abîmé. Un remux 4K à
**89,7 Mb/s de moyenne** (Upgrade, 2018, 67 Go) se figeait alors
régulièrement, puis repartait. Le débit mesuré vers la Shield était de
94,5 Mb/s, avec une file d'envoi pleine en permanence. **171 films sur 326**
de la médiathèque sont des remux. Rien dans ArrMada ne permettait de demander
une version allégée, et rien ne disait à l'utilisateur que son réseau était
en cause.

Le serveur a une RTX 3060 (NVENC) et le mappage tonal activé dans Jellyfin :
une conversion 1080p en temps réel ne pose pas de problème. Un flux de
conversion existait déjà (`sdr.m3u8` : H.264 SDR 1080p, 20 Mb/s, son copié),
réservé au Dolby Vision profil 5 sur un écran sans Dolby Vision.

## Décision

1. **Une qualité réduite unique, 1080p à 20 Mb/s**, choisie par la TV :
   menu pause › Qualité (Original / 1080p HDR / 1080p SDR), réglage par
   défaut de la TV, ou proposition automatique. Le serveur fournit le débit
   moyen du fichier (`bitrate`, `MediaSources[0].Bitrate` de Jellyfin,
   `null` s'il est inconnu).
2. **Le 1080p SDR réutilise le flux `sdr`** tel quel. 20 Mb/s, plafonnés à
   30 Mb/s avec le son copié, passent sur un lien à 100 Mb/s ou en Wi-Fi.
3. **Pas de 1080p HDR côté serveur pour l'instant.** La demande initiale
   voulait garder le HDR10 (HEVC 10 bits, `hevc-rangetype=HDR10`). Vérifié
   sur le Jellyfin 12.3 installé et dans son code source :
   - le mappage tonal s'applique à **tout réencodage** d'une image HDR quand
     il est activé, quel que soit le codec de sortie, et les filtres écrivent
     une image BT.709 ;
   - le HEVC réencodé est forcé en profil Main (8 bits) ;
   - `{codec}-rangetype` ne sert qu'à décider si l'image peut être **copiée**,
     pas à produire du HDR ;
   - l'encodage HEVC est d'ailleurs désactivé sur ce serveur
     (`AllowHevcEncoding=false`), et Jellyfin se replierait sur le H.264.

   Un `lite.m3u8` aurait donc donné le même SDR que `sdr.m3u8`, sous une
   étiquette « HDR » mensongère. L'appli gère quand même `lite_stream` (vide
   par défaut) : l'option « 1080p HDR » apparaîtra d'elle-même le jour où le
   serveur saura la fournir, sur un écran HDR10, pour une image HDR.
4. **Détection des coupures** : une attente de chargement compte si la
   lecture est demandée (`playWhenReady`), après la première image du flux,
   et plus de **3 s** après un saut ou un changement de flux (le tampon se
   remplit forcément). **3 coupures en moins de 5 minutes** en lecture
   Original déclenchent une carte non bloquante : « Le réseau ne suit pas ce
   fichier (90 Mb/s). Passer en 1080p ? ». Refusée, elle ne revient plus de
   la séance. Sans réponse, elle s'efface après 20 s et le compte repart de
   zéro. Pas de proposition pour un fichier de moins de 25 Mb/s : le 1080p à
   20 Mb/s ne le soulagerait pas, la cause est ailleurs. Après un premier
   « oui », la TV demande une seule fois « Toujours lire en 1080p sur cette
   TV ? ».
5. **Priorités au lancement** : le Dolby Vision profil 5 sur un écran sans
   DV part en SDR quoi qu'il arrive (sinon image violette), puis le réglage
   de la TV, puis l'original.
6. **Arrêt de la conversion avant la bascule** : remux, SDR et 1080p
   partagent la session `arrmada-{id}` chez Jellyfin, et
   `DELETE /Videos/ActiveEncodings` arrête toutes ses conversions. La TV
   arrête donc la conversion en cours **avant** de charger le nouveau flux
   (lecteur stoppé entre les deux, position gardée), jamais après.

## Alternatives écartées

- **Débit adaptatif (ABR) à plusieurs qualités** : Jellyfin ne produit qu'une
  variante par conversion. Une échelle de qualités voudrait plusieurs
  encodages simultanés (trois fois la charge GPU) ou un empaqueteur en plus.
  Le besoin réel est binaire : le réseau suit l'original, ou non. Un choix
  explicite et visible reste aussi plus lisible qu'un lecteur qui change de
  qualité sans le dire.
- **Un `lite.m3u8` « HDR » quand même** : même image que le SDR (voir
  décision 3), et du HEVC à activer côté Jellyfin pour rien.
- **Seuil sur le débit seul** (« fichier > X Mb/s → 1080p d'office ») : la
  même Shield lit la même 4K sans souci une fois le câble changé. Seules les
  coupures réelles disent que le réseau ne suit pas.
- **Une seule coupure suffit** : un Wi-Fi qui hoquette, ou Jellyfin qui
  démarre un remux, déclencherait la carte à tort.

## Conséquences

- 171 remux deviennent lisibles sur un lien à 100 Mb/s, au prix d'un
  réencodage NVENC et de la perte du HDR / Dolby Vision en 1080p.
- Un serveur ArrMada plus ancien (sans `bitrate` ni `lite_stream`) ne casse
  pas l'appli : « Original » et « 1080p SDR » restent proposés, la carte se
  fie aux coupures seules.
- Le jour où Jellyfin saura réencoder en HDR10 : ajouter un préréglage
  `lite.m3u8` (HEVC 10 bits, `hevc-rangetype=HDR10`), l'autoriser dans
  `HLS_PATH` et dans `device_may_call` (`services/devices.py`), activer
  « Autoriser l'encodage au format HEVC » dans Jellyfin, puis renvoyer
  `lite_stream` dans `_found()`. Rien à changer dans l'appli.
- **La piste audio suit la bascule.** La liste HLS de Jellyfin (vérifié dans
  le code de la 12.4, `DynamicHlsHelper` / `EncodingHelper`) ne porte qu'une
  piste audio : celle d'`AudioStreamIndex`, sinon la première du fichier. Sur
  un fichier MULTi, la VF (ou la VO) choisie en direct était donc perdue en
  1080p. Le serveur donne les pistes du fichier avec leur index Jellyfin
  (`audio_tracks`) et accepte `?audio=N` sur `master.m3u8` / `sdr.m3u8` ; la
  TV retrouve la piste entendue (langue, format, canaux, rang :
  `HlsAudioLogic`) et la demande. L'arrêt de la conversion avant la bascule
  (décision 6) devient indispensable : le dossier de sortie de Jellyfin ne
  dépend que de la session, pas de la piste, il resservirait sinon les
  morceaux déjà produits. Pendant un flux converti (dès le départ : réglage
  « 1080p », remux ; ou après une bascule), le lecteur ne voit qu'une piste :
  le panneau Audio du menu pause et la tablette proposent alors les
  `audio_tracks` du serveur, la piste lue cochée (celle demandée, sinon celle
  que Jellyfin prend seul : par défaut, sinon la première) ; en choisir une
  autre arrête la conversion, puis recharge le même flux avec `?audio=N` à la
  même position, et la langue de la piste du serveur est rangée dans la
  mémoire du profil (le lecteur ne la connaît pas) avec les sous-titres en
  cours.
- **Lecture convertie dès le départ : la langue d'office se décide avant le
  lecteur.** Le lecteur ne verra jamais les pistes du fichier, la règle des
  langues (dernier choix du profil, sinon VO + sous-titres FR, sinon VF :
  `TrackLanguageLogic`) s'applique donc aux `audio_tracks` du serveur
  (`HlsAudioLogic.indexAtStart`) et la piste est demandée dans l'adresse de
  départ. Comptent pour la VO + sous-titres FR les sous-titres que le flux
  converti aura : ceux posés à côté du fichier (Bazarr) et les pistes texte du
  MKV que la TV pose à côté elle aussi (voir Sous-titres ci-dessous). La fiche et
  le dernier choix du profil sont attendus par `PlayerScreen` (3 s au plus)
  avant de créer le lecteur ; s'ils arrivent après, le flux n'est pas
  rechargé (la conversion repartirait de zéro pour une fiche en retard) :
  piste par défaut de Jellyfin, changeable au panneau Audio.
- À vérifier à la main sur la Shield : bascule Original → 1080p → Original
  pendant un film (position à moins de 2 s près, langue gardée sur un fichier
  MULTi, sous-titres intégrés toujours proposés), passage en VF depuis le
  panneau Audio en lecture 1080p dès le départ (position et sous-titres
  gardés), épisode suivant d'une série passée en VF lu en 1080p dès le départ
  et en VF sans intervention, et plus aucune session de transcodage orpheline
  dans le tableau de bord Jellyfin après le retour à l'original ou la sortie
  de la lecture.
- **Sous-titres** (ajouté le 08/11/2026, après des sous-titres disparus en
  1080p) : le flux HLS de Jellyfin ne transporte que l'image et le son. Les
  pistes texte intégrées au fichier (SRT, ASS) sont donc posées à côté du
  flux converti par la TV, depuis l'extraction de Jellyfin que le serveur
  liste déjà (`embedded_subtitles`), et la piste affichée est rechoisie par
  sa langue et sa sorte (`data/StreamSwitchLogic.kt`). Les pistes image
  (PGS, VobSub) n'ont pas d'équivalent texte : elles ne suivent pas en
  1080p, la TV l'annonce ; les incruster dans l'image (`SubtitleMethod=
  Encode` de Jellyfin, une conversion par piste) reste à décider.
