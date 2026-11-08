package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Changement de flux (qualité, remux) : sous-titres posés à côté, piste rechoisie. */
class StreamSwitchLogicTest {

    private val fileFr = SideSubtitle("/api/tv/subtitle/x/5.srt", "Français · fichier", "fr", "application/x-subrip")
    private val inMkvFr = SideSubtitle("/api/tv/subtitle/x/3.ass", "Français", "fr", "text/x-ssa")
    private val inMkvForced = SideSubtitle("/api/tv/subtitle/x/4.ass", "Français (forcés)", "fr", "text/x-ssa")
    private val shifted = SideSubtitle("/api/tv/subtitle/x/3.ass?shift=1500", "Français (décalé +1,5 s)", "fr", "text/x-ssa")

    private fun text(language: String?, forced: Boolean = false, label: String? = null, supported: Boolean = true) =
        TrackLanguageLogic.Text(language, forced = forced, supported = supported, label = label)

    @Test
    fun `en direct, seuls les sous-titres poses a cote du fichier`() {
        // Les pistes du MKV sont déjà lues par le lecteur : pas de doublon
        assertEquals(listOf(fileFr), StreamSwitchLogic.sideloaded(hls = false, side = listOf(fileFr), embedded = listOf(inMkvFr, inMkvForced)))
    }

    @Test
    fun `en HLS, les pistes texte integrees s'ajoutent, integrees d'abord`() {
        // Le flux HLS de Jellyfin n'a ni les unes ni les autres
        assertEquals(
            listOf(inMkvFr, inMkvForced, fileFr),
            StreamSwitchLogic.sideloaded(hls = true, side = listOf(fileFr), embedded = listOf(inMkvFr, inMkvForced)),
        )
        // Copie décalée d'une piste intégrée : adresse différente, les deux restent
        assertEquals(
            listOf(inMkvFr, shifted),
            StreamSwitchLogic.sideloaded(hls = true, side = listOf(shifted), embedded = listOf(inMkvFr)),
        )
        // Même adresse des deux côtés : une seule fois
        assertEquals(listOf(inMkvFr), StreamSwitchLogic.sideloaded(hls = true, side = listOf(inMkvFr), embedded = listOf(inMkvFr)))
        assertEquals(emptyList<SideSubtitle>(), StreamSwitchLogic.sideloaded(hls = true, side = emptyList(), embedded = emptyList()))
    }

    @Test
    fun `piste du MKV retrouvee dans l'extraction de Jellyfin, meme langue meme sorte`() {
        // Direct → 1080p : « fre » du MKV sans nom, « fr » côté serveur avec un nom
        val hls = listOf(text("en", label = "Anglais"), text("fr", label = "Français"), text("fr", label = "Français (forcés)"))
        assertEquals(1, StreamSwitchLogic.sameText(StreamSwitchLogic.Shown(null, "fre", forced = false), hls))
        assertEquals(2, StreamSwitchLogic.sameText(StreamSwitchLogic.Shown(null, "fre", forced = true), hls))
        // 1080p → direct : la piste extraite « Français (forcés) » retrouve la piste forcée du MKV (drapeau, sans nom)
        val mkv = listOf(text("fre", forced = false), text("fre", forced = true))
        assertEquals(1, StreamSwitchLogic.sameText(StreamSwitchLogic.Shown("Français (forcés)", "fr", forced = true), mkv))
        // Piste du MKV nommée « Forced » sans drapeau : forcée quand même
        val named = listOf(text("fre", label = "Full"), text("fre", label = "Forced"))
        assertEquals(1, StreamSwitchLogic.sameText(StreamSwitchLogic.Shown("Français (forcés)", "fr", forced = true), named))
    }

    @Test
    fun `le meme nom gagne, pistes illisibles ecartees`() {
        // Copie décalée et piste d'origine, même langue, même sorte : le nom départage
        val texts = listOf(text("fr", label = "Français"), text("fr", label = "Français (décalé +1,5 s)"))
        assertEquals(1, StreamSwitchLogic.sameText(StreamSwitchLogic.Shown("Français (décalé +1,5 s)", "fr", forced = false), texts))
        assertEquals(0, StreamSwitchLogic.sameText(StreamSwitchLogic.Shown("Français", "fr", forced = false), texts))
        // Nom différent : la langue et la sorte suffisent
        assertEquals(0, StreamSwitchLogic.sameText(StreamSwitchLogic.Shown("French", "fre", forced = false), texts))
        // Piste que le lecteur ne sait pas lire : la suivante
        val unsupported = listOf(text("fr", supported = false), text("fr"))
        assertEquals(1, StreamSwitchLogic.sameText(StreamSwitchLogic.Shown(null, "fr", forced = false), unsupported))
    }

    @Test
    fun `rien a choisir, pas de repli sur l'autre sorte ni sur une langue inconnue`() {
        val onlyForced = listOf(text("fr", forced = true, label = "Français (forcés)"), text("en", label = "Anglais"))
        // Sous-titres complets français (PGS en direct) : pas de version texte, et pas les forcés à la place
        assertNull(StreamSwitchLogic.sameText(StreamSwitchLogic.Shown("Français", "fr", forced = false), onlyForced))
        // Langue absente du nouveau flux
        assertNull(StreamSwitchLogic.sameText(StreamSwitchLogic.Shown(null, "de", forced = false), onlyForced))
        // Langue inconnue des deux côtés : le nom seul, jamais une piste au hasard
        val unknown = listOf(text(null, label = "Commentaire"), text(null, label = "Chansons"))
        assertEquals(1, StreamSwitchLogic.sameText(StreamSwitchLogic.Shown("Chansons", null, forced = false), unknown))
        assertNull(StreamSwitchLogic.sameText(StreamSwitchLogic.Shown(null, null, forced = false), unknown))
        assertNull(StreamSwitchLogic.sameText(StreamSwitchLogic.Shown("Français", "fr", forced = false), emptyList()))
    }
}
