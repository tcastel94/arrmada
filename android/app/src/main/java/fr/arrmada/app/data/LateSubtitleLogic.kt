package fr.arrmada.app.data

/**
 * Pistes de sous-titres qui peuvent mettre des minutes à répondre : ne pas
 * les attendre pour démarrer la vidéo, les poser quand elles arrivent.
 *
 * À la bascule vers un flux converti (menu pause › Qualité, remux de secours,
 * SDR), la TV pose à côté du flux les pistes texte intégrées au fichier,
 * servies par le serveur depuis l'extraction de Jellyfin
 * (`/api/tv/subtitle/…`, StreamSwitchLogic). À la première demande, Jellyfin
 * extrait toutes les pistes texte en une passe ffmpeg sur le fichier entier,
 * et ne répond qu'à la fin : quelques secondes pour un épisode, 3 à 10 min
 * pour un remux 4K de 70 Go. Or Media3 ne prépare la lecture qu'une fois
 * TOUTES les pistes posées à côté reçues : la TV « moulinait » sans fin, sans
 * même demander l'image (constaté le 08/11/2026, bascule 60 s après le
 * lancement de Dragons).
 *
 * Pourquoi aller les chercher d'abord, plutôt que de rendre leurs erreurs
 * de chargement non fatales dans Media3 (`SingleSampleMediaSource.Factory
 * .setTreatLoadErrorsAsEndOfStream`) : depuis Media3 1.4, les sous-titres
 * posés à côté sont lus par un `ProgressiveMediaSource` (décodage pendant
 * l'extraction, `APPLICATION_MEDIA3_CUES`), qui n'a pas ce réglage et ne se
 * déclare prêt qu'à la réponse HTTP ; et tant qu'une piste choisie n'a rien
 * reçu, la position mise en mémoire tampon reste à zéro, la lecture ne
 * démarre pas. Même en revenant à l'ancien chemin, l'image aurait attendu
 * la fin des trois essais (plus d'une minute) et la piste aurait été perdue
 * pour de bon. Ici la vidéo part tout de suite, avec les sous-titres qui
 * répondent vite (fichiers `.srt` à côté de la vidéo : lus sur le disque),
 * et les pistes extraites s'ajoutent dès qu'elles sont là, par une relecture
 * du même flux au même endroit (comme après un décalage de sous-titres).
 *
 * Les pistes reçues sont gardées dans un fichier de l'appli (voir
 * `ui/player/LateSubtitleFetcher`) : la relecture les lit en local, sans
 * redemander au serveur, et ne peut donc plus bloquer.
 *
 * Logique pure (sans Android) : testée sur la JVM.
 */
object LateSubtitleLogic {

    /**
     * Attente accordée aux pistes avant de démarrer sans elles. Déjà
     * extraites (cache permanent de Jellyfin), elles répondent en moins d'une
     * seconde sur le réseau local : la bascule garde alors son comportement
     * d'avant (un seul chargement, pistes comprises). Au-delà, l'extraction
     * est en cours, et elle prendra des minutes : inutile d'attendre plus.
     */
    const val PROBE_MS = 2_000L

    /**
     * Attente totale, par bascule : l'extraction d'un remux 4K prend jusqu'à
     * 10 min sur un disque occupé (Jellyfin tue lui-même ffmpeg à 30 min).
     * Au-delà, la vidéo continue sans ces pistes, et on le dit.
     */
    const val MAX_WAIT_MS = 10 * 60_000L

    /** Pause avant de redemander après un échec rapide (serveur injoignable, erreur 5xx immédiate). */
    const val PAUSE_MS = 5_000L

    /**
     * Une tentative qui a duré au moins ce temps avant d'échouer a attendu
     * Jellyfin : le serveur ArrMada coupe son relais au bout de 30 s (502),
     * le client de la TV au bout de 45 s. L'extraction continue chez
     * Jellyfin (vérifié dans son code, voir `services/tv_playback.py`) :
     * on redemande aussitôt, la nouvelle demande la rejoint.
     */
    const val LONG_ATTEMPT_MS = 15_000L

    /** Sous-titres à poser tout de suite, et ceux à aller chercher d'abord. */
    data class Split(val now: List<SideSubtitle>, val later: List<SideSubtitle>)

    /**
     * Parmi les sous-titres [subtitles] à poser à côté du flux : ceux qui
     * répondent vite ([Split.now]) et ceux qui passent par l'extraction de
     * Jellyfin ([Split.later]) : les pistes intégrées [embedded] et leurs
     * copies décalées (`?shift=`), tant qu'aucune n'a encore été reçue.
     * [ready] : adresses déjà reçues (fichier local) ; une piste intégrée
     * reçue dit que l'extraction est faite, ses copies décalées répondent
     * alors vite. [failed] : adresses abandonnées, qu'on ne pose plus (elles
     * bloqueraient à nouveau). L'ordre de [subtitles] est conservé.
     */
    fun split(
        subtitles: List<SideSubtitle>,
        embedded: List<SideSubtitle>,
        ready: Set<String> = emptySet(),
        failed: Set<String> = emptySet(),
    ): Split {
        val extracted = embedded.map { base(it.url) }.toSet()
        val readyBases = ready.map(::base).toSet()
        val kept = subtitles.filterNot { it.url in failed }
        val (later, now) = kept.partition { sub ->
            base(sub.url) in extracted && sub.url !in ready && base(sub.url) !in readyBases
        }
        return Split(now, later)
    }

    /** Adresse sans ses paramètres (`?shift=1500`) : la piste extraite elle-même. */
    fun base(url: String): String = url.substringBefore('?')

    /** Pourquoi une tentative a échoué. */
    sealed class Failure {
        /** Pas de réponse dans le délai du client (45 s). */
        data object Timeout : Failure()

        /** Serveur injoignable, connexion coupée. */
        data object Unreachable : Failure()

        /** Réponse HTTP en erreur. */
        data class Http(val code: Int) : Failure()
    }

    /**
     * Suite à donner à une tentative échouée. [GIVE_UP] : la piste est
     * abandonnée pour la séance (le serveur la refuse) ; [OUT_OF_TIME] : on
     * arrête d'attendre, sans condamner la piste, qui sera redemandée au
     * prochain changement de flux (l'extraction aura peut-être fini).
     */
    enum class Next { RETRY_NOW, RETRY_AFTER_PAUSE, GIVE_UP, OUT_OF_TIME }

    /**
     * Après un échec [failure] d'une tentative de [attemptMs], [elapsedMs]
     * après le début de l'attente : redemander tout de suite (l'extraction
     * est en cours, voir [LONG_ATTEMPT_MS]), après une pause (échec rapide,
     * serveur injoignable), abandonner la piste (erreur 4xx : inconnue du
     * serveur), ou arrêter d'attendre (budget [MAX_WAIT_MS] épuisé).
     */
    fun afterFailure(failure: Failure, attemptMs: Long, elapsedMs: Long): Next {
        if (elapsedMs >= MAX_WAIT_MS) return Next.OUT_OF_TIME
        return when (failure) {
            is Failure.Timeout -> Next.RETRY_NOW
            is Failure.Unreachable -> Next.RETRY_AFTER_PAUSE
            is Failure.Http -> when {
                failure.code in 400..499 -> Next.GIVE_UP
                attemptMs >= LONG_ATTEMPT_MS -> Next.RETRY_NOW
                else -> Next.RETRY_AFTER_PAUSE
            }
        }
    }

    /**
     * La piste [shown], affichée avant le changement de flux, fait-elle
     * partie des pistes [later] encore attendues ? Elle n'est alors pas
     * « absente de ce flux » : elle reviendra d'elle-même à la relecture.
     */
    fun comingLater(shown: StreamSwitchLogic.Shown, later: List<SideSubtitle>): Boolean =
        StreamSwitchLogic.sameText(
            shown,
            later.map { TrackLanguageLogic.Text(it.language.ifBlank { null }, forced = "forcés" in it.label, supported = true, label = it.label) },
        ) != null

    /** Message discret quand la piste retenue reviendra plus tard. */
    fun waitingMessage(label: String): String = "Sous-titres « $label » en préparation : ils reviendront tout seuls"

    /** Le temps a manqué : l'extraction continue chez Jellyfin, la prochaine bascule les trouvera. */
    const val STILL_EXTRACTING = "Sous-titres du fichier toujours en préparation : ils seront là au prochain changement de flux"

    /**
     * Message discret une fois l'attente finie : les pistes [failed]
     * abandonnées (le serveur les refuse), ou [outOfTime] ; null si tout
     * est arrivé. Jamais bloquant : la vidéo joue, avec ou sans elles.
     */
    fun outcomeMessage(failed: List<SideSubtitle>, outOfTime: Boolean): String? {
        if (failed.isNotEmpty()) {
            val names = failed.joinToString(", ") { "« ${it.label} »" }
            return "Sous-titres $names indisponibles pour ce flux"
        }
        return if (outOfTime) STILL_EXTRACTING else null
    }

    /**
     * Nom du fichier local d'une piste : empreinte de l'adresse (deux pistes
     * ou deux décalages ne se confondent pas) et son extension (`srt`,
     * `ass`, `vtt`), que Media3 lit pour reconnaître le format.
     */
    fun fileName(url: String): String {
        val ext = base(url).substringAfterLast('.', "").takeIf { it.isNotBlank() && it.length <= 4 && '/' !in it } ?: "srt"
        return "${url.hashCode().toUInt().toString(16)}.$ext"
    }
}
