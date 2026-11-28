# ADR-022 : Trakt, notes de fin de lecture et historique en direct

- **Statut** : accepté
- **Date** : 2026-11-28

## Contexte

On veut noter chaque film et chaque épisode à la fin de la lecture sur la TV,
et que ces notes, comme ce qu'on regarde, arrivent sur son compte
[Trakt](https://trakt.tv). La TV est partagée : Famille, Jeff, Morgane…
(profils, ADR-008), chacun avec SON compte Trakt.

## Décision

1. **Un compte Trakt par profil** (`trakt_accounts`, clé `profile_key`,
   0 = « Famille »). Jetons chiffrés comme les clés des services, renouvelés
   tout seuls avant expiration et une fois de plus sur un 401. Un profil sans
   compte ne voit jamais de demande de note.

2. **Liaison par code d'appareil** (OAuth *device flow*), depuis
   Paramètres › Trakt de la web app : ArrMada demande un code à Trakt, on le
   tape sur trakt.tv/activate, la page attend au rythme demandé par Trakt.
   Rien à exposer sur Internet, aucune adresse de retour. Analogie :
   l'appairage d'une TV avec un code. Prérequis : une application Trakt
   (`TRAKT_CLIENT_ID` / `TRAKT_CLIENT_SECRET`, redirect URI
   `urn:ietf:wg:oauth:2.0:oob`).

3. **Notes à la fin, sur la TV** : quand on quitte un titre vu au-delà de
   90 % (fin du fichier, épisode suivant, Retour, « Quitter »), une carte
   5 étoiles apparaît. ← / → par demi-étoile (les 10 niveaux de Trakt,
   libellés traduits), chiffres 1 à 5 pour des étoiles pleines, OK pour
   noter, Retour pour passer. Puis l'épisode suivant démarre (ou retour).

   | Titre | Notes proposées |
   |---|---|
   | Film | le film |
   | Épisode | l'épisode |
   | Dernier épisode d'une saison (d'après Sonarr) | l'épisode, puis la saison |
   | Dernier épisode de la dernière saison d'une série terminée | l'épisode, la saison, puis la série |

   Le serveur calcule ces étapes dès le début de la lecture
   (`GET /api/trakt/prompt`), la note part par `POST /api/trakt/rate`.

4. **Lecture en direct (scrobble)** côté serveur : la TV envoie déjà
   « lecture / pause / reprise / arrêt » pour la tablette du salon
   (`/api/kodi/scrobble`). Le serveur relaie à Trakt (start / pause / stop,
   avec le % vu), en arrière-plan, sans faire attendre la TV. Passé 80 %,
   Trakt marque le titre comme vu. Pour un épisode, la TV ajoute le TVDB de
   la série au message. Pas de relais pour les « progress » : Trakt suit seul
   l'avancement entre start et stop.

5. **Droits** : la TV peut lire son statut, les étapes et envoyer une note
   (`devices.device_may_call`) ; la liaison des comptes reste réservée à
   l'administrateur (web app).

## Conséquences

- Hors Trakt : vidéos maison et séries maison (pas d'identifiant connu de
  Trakt), lecture depuis un téléphone (il n'envoie pas le flux « lecture en
  cours »), add-on Kodi (pas de carte de note).
- Une note existante n'est pas pré-remplie : revoir un film propose une carte
  vide ; la nouvelle note remplace l'ancienne sur Trakt.
- Si Sonarr ne répond pas, seule la note de l'épisode est proposée.
