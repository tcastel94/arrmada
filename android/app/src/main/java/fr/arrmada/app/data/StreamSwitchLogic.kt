package fr.arrmada.app.data

/**
 * Changement de flux en cours de lecture (menu pause › Qualité, remux de
 * secours, SDR du Dolby Vision profil 5, sous-titres relus) : quelles pistes
 * de sous-titres poser à côté du nouveau flux, et laquelle rechoisir.
 *
 * Le flux HLS de Jellyfin (remux, 1080p) ne transporte que l'image et le
 * son : les pistes texte intégrées au MKV, que le lecteur lit tout seul en
 * direct, disparaissaient à la bascule. Le serveur les liste déjà
 * (`embedded_subtitles`, extraites par Jellyfin) : en HLS, on les pose à
 * côté du flux, comme les sous-titres posés à côté du fichier. Les pistes
 * image (PGS des Blu-ray, VobSub des DVD) n'ont pas de version texte : elles
 * ne suivent pas, et le lecteur le dit.
 *
 * Logique pure (sans Android) : testée sur la JVM.
 */
object StreamSwitchLogic {

    /**
     * Sous-titres à poser à côté du flux : ceux posés à côté du fichier
     * (Bazarr, copie décalée…) toujours ; en HLS, aussi les pistes texte
     * intégrées, absentes du flux de Jellyfin. En direct, le lecteur les lit
     * déjà dans le fichier : les ajouter les ferait apparaître en double.
     * Les intégrées d'abord, comme en direct (pistes du fichier, puis le reste).
     */
    fun sideloaded(hls: Boolean, side: List<SideSubtitle>, embedded: List<SideSubtitle>): List<SideSubtitle> =
        if (hls) embedded.filterNot { e -> side.any { it.url == e.url } } + side else side

    /**
     * Piste de sous-titres affichée avant le changement de flux. [image] :
     * piste image (PGS, VobSub), qui n'a pas de version texte à poser à côté
     * d'un flux converti (sert au message quand elle manque).
     */
    data class Shown(val label: String?, val language: String?, val forced: Boolean, val image: Boolean = false)

    /**
     * Dans les pistes du nouveau flux, celle qui correspond à [shown] : la
     * même piste (même nom, même langue), sinon la même langue et la même
     * sorte, complets ou « forcés » (passages en langue étrangère). Pas de
     * repli sur l'autre sorte : des forcés à la place de sous-titres complets
     * (ou l'inverse) surprendraient plus que leur absence, qui est annoncée.
     * Langue inconnue des deux côtés : le nom seul fait foi.
     * null : rien à choisir (piste image, langue absente du nouveau flux).
     */
    fun sameText(shown: Shown, texts: List<TrackLanguageLogic.Text>): Int? {
        val lang = TrackLanguageLogic.normalize(shown.language)
        val candidates = texts.withIndex().filter { (_, t) -> t.supported && TrackLanguageLogic.normalize(t.language) == lang }
        val label = shown.label?.takeIf { it.isNotBlank() }
        if (label != null) candidates.firstOrNull { it.value.label == label }?.let { return it.index }
        if (lang == null) return null
        return candidates.firstOrNull { TrackLanguageLogic.isForced(it.value.forced, it.value.label) == shown.forced }?.index
    }
}
