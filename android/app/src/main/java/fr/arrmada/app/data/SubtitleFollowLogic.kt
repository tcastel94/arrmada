package fr.arrmada.app.data

/**
 * Menu pause › « Sous-titres FR » : suivre la recherche jusqu'au bout.
 *
 * Le serveur cherche en arrière-plan (services/subtitle_jobs.py) et répond
 * au bout de 30 s au plus. Tant qu'il répond « pending », la TV redemande :
 * la nouvelle demande REJOINT la même recherche (aucune recherche Bazarr en
 * plus), comme un `tail -f` sur un job en cours. Avant, la TV s'arrêtait
 * là et affichait « réessaie dans une minute » : il fallait le faire à la main.
 *
 * Logique pure, testée sans appareil (SubtitleFollowLogicTest).
 */
object SubtitleFollowLogic {
    /**
     * Demandes au plus pour une même recherche (~30 s chacune côté serveur) :
     * environ 4 minutes, de quoi couvrir la recherche élargie et le recalage
     * sur le son d'un épisode d'anime.
     */
    const val MAX_ROUNDS = 8

    /** Pause entre deux demandes quand le serveur a répondu vite (ms). */
    const val PAUSE_MS = 2_000L

    /** Faut-il redemander après la réponse n° [round] (1 = première) ? */
    fun shouldFollow(status: String, round: Int): Boolean = status == "pending" && round < MAX_ROUNDS

    /**
     * Texte sous le bouton pendant l'attente : l'étape envoyée par le
     * serveur (« Recherche élargie (versions approchantes) »), sinon un
     * message d'attente. Court : la puce n'a que deux lignes.
     */
    fun progressNote(result: SubtitleResult): String {
        val phase = result.phase?.takeIf { it.isNotBlank() && it != "Terminé" }
        return if (phase != null) "Bazarr : ${phase.replaceFirstChar { it.lowercase() }}…" else "Bazarr cherche encore…"
    }

    /** Message final quand la TV arrête de suivre une recherche pas finie. */
    const val STILL_RUNNING =
        "Bazarr cherche toujours : le sous-titre sera là au prochain lancement (ou réessaie dans 2 min)"
}
