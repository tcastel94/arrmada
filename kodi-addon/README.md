# 🏴‍☠️ ArrMada — Plugin Officiel pour Kodi

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
- Met à jour l'état *Vu* et les points de reprise pour le multi-écrans.

### 4. 📺 Notifications TV des téléchargements terminés
- Dès qu'un téléchargement SABnzbd ou Torrent est terminé et importé par Radarr/Sonarr, une alerte discrète s'affiche en haut de l'écran Kodi.

### 5. 📥 Menu d'accueil ArrMada
- Consultez la liste et la progression des téléchargements actifs directement sur Kodi.
- Lancez un scan ou un nettoyage manuel de la médiathèque Kodi en un clic.

---

## 🚀 Installation dans Kodi

### Méthode 1 : Fichier ZIP (Recommandé)
1. Téléchargez ou copiez le fichier `script.arrmada-1.0.0.zip` sur votre appareil Kodi (ou partage réseau).
2. Dans Kodi, allez dans **Extensions / Add-ons** > **Installer depuis un fichier ZIP**.
3. Sélectionnez `script.arrmada-1.0.0.zip` et validez.

### Méthode 2 : Copie directe
Copiez le dossier `script.arrmada/` dans le dossier des extensions de Kodi :
- **LibreELEC / CoreELEC** : `/storage/.kodi/addons/`
- **Linux** : `~/.kodi/addons/`
- **Android** : `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/`
- **Windows** : `%APPDATA%\Kodi\addons\`

---

## ⚙️ Configuration

1. Ouvrez Kodi > **Extensions** > **Extensions Programmes** > **ArrMada** (ou faites Clic droit > **Paramètres**).
2. Renseignez :
   - **URL du serveur ArrMada** : `http://<IP_DE_VOTRE_SERVEUR>:3420` (ou port du backend).
   - **Clé API / Mot de passe** : Votre mot de passe de connexion ArrMada (`ARRMADA_AUTH_SECRET`).
   - **Nom de l'appareil** : Ex: `Kodi Salon`.
   - **Langue des sous-titres** : `fr` (ou selon votre choix).
3. Validez ! Le service démarre automatiquement en arrière-plan.
