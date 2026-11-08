package fr.arrmada.app.data

import fr.arrmada.app.data.LateSubtitleLogic.Failure
import fr.arrmada.app.data.LateSubtitleLogic.Next
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Bascule de qualité : la vidéo démarre sans attendre les pistes texte que Jellyfin extrait, qui s'ajoutent ensuite. */
class LateSubtitleLogicTest {

    // Pistes texte intégrées au MKV (extraction de Jellyfin), sous-titre .srt posé à côté du fichier (lu sur le disque)
    private val inMkvFr = SideSubtitle("/api/tv/subtitle/x/3.ass", "Français", "fr", "text/x-ssa")
    private val inMkvForced = SideSubtitle("/api/tv/subtitle/x/4.ass", "Français (forcés)", "fr", "text/x-ssa")
    private val fileFr = SideSubtitle("/api/tv/subtitle/x/5.srt", "Français · fichier", "fr", "application/x-subrip")
    private val shifted = SideSubtitle("/api/tv/subtitle/x/3.ass?shift=1500", "Français (décalé +1,5 s)", "fr", "text/x-ssa")
    private val embedded = listOf(inMkvFr, inMkvForced)

    // Ce que StreamSwitchLogic.sideloaded donne en HLS : les intégrées d'abord, puis le fichier
    private val hlsSubs = listOf(inMkvFr, inMkvForced, fileFr)

    @Test
    fun `pistes lentes, la video demarre sans elles, puis elles s'ajoutent`() {
        // Première bascule : rien de reçu, Jellyfin extrait peut-être encore
        val first = LateSubtitleLogic.split(hlsSubs, embedded)
        assertEquals(listOf(fileFr), first.now) // le .srt du disque part avec le flux
        assertEquals(listOf(inMkvFr, inMkvForced), first.later) // les intégrées sont demandées à part
        // Reçues (fichiers locaux) : la relecture pose tout, dans l'ordre d'avant
        val ready = first.later.map { it.url }.toSet()
        val reload = LateSubtitleLogic.split(hlsSubs, embedded, ready)
        assertEquals(hlsSubs, reload.now)
        assertTrue(reload.later.isEmpty())
    }

    @Test
    fun `pistes rapides ou deja recues, un seul chargement, comme avant`() {
        // Déjà reçues à une bascule précédente : rien à attendre, tout part avec le flux
        val ready = setOf(inMkvFr.url, inMkvForced.url)
        assertEquals(LateSubtitleLogic.Split(hlsSubs, emptyList()), LateSubtitleLogic.split(hlsSubs, embedded, ready))
        // Lecture directe : le lecteur lit les pistes du MKV lui-même, seul le .srt est posé à côté
        assertEquals(LateSubtitleLogic.Split(listOf(fileFr), emptyList()), LateSubtitleLogic.split(listOf(fileFr), embedded))
        // Fichier sans piste texte intégrée : rien ne change
        assertEquals(LateSubtitleLogic.Split(listOf(fileFr), emptyList()), LateSubtitleLogic.split(listOf(fileFr), emptyList()))
        assertEquals(LateSubtitleLogic.Split(emptyList(), emptyList()), LateSubtitleLogic.split(emptyList(), embedded))
    }

    @Test
    fun `piste en echec definitif, la video joue sans ce sous-titre`() {
        // Les forcés refusés par le serveur (404) : plus jamais posés, ils bloqueraient à nouveau
        val reload = LateSubtitleLogic.split(hlsSubs, embedded, ready = setOf(inMkvFr.url), failed = setOf(inMkvForced.url))
        assertEquals(listOf(inMkvFr, fileFr), reload.now)
        assertTrue(reload.later.isEmpty())
        assertEquals("Sous-titres « Français (forcés) » indisponibles pour ce flux", LateSubtitleLogic.outcomeMessage(listOf(inMkvForced), outOfTime = false))
        assertEquals(
            "Sous-titres « Français », « Français (forcés) » indisponibles pour ce flux",
            LateSubtitleLogic.outcomeMessage(embedded, outOfTime = false),
        )
        // Le temps a manqué : l'extraction continue chez Jellyfin, la prochaine bascule les trouvera
        assertEquals(LateSubtitleLogic.STILL_EXTRACTING, LateSubtitleLogic.outcomeMessage(emptyList(), outOfTime = true))
        // Tout est arrivé : rien à dire
        assertNull(LateSubtitleLogic.outcomeMessage(emptyList(), outOfTime = false))
    }

    @Test
    fun `copie decalee d'une piste integree, lente tant que la piste n'est pas extraite`() {
        // Décalage demandé en lecture directe : le serveur passe par l'extraction de Jellyfin
        assertEquals(LateSubtitleLogic.Split(emptyList(), listOf(shifted)), LateSubtitleLogic.split(listOf(shifted), embedded))
        // La piste d'origine est reçue : l'extraction est faite, la copie décalée répond vite (serveur)
        assertEquals(LateSubtitleLogic.Split(listOf(shifted), emptyList()), LateSubtitleLogic.split(listOf(shifted), embedded, setOf(inMkvFr.url)))
        // La copie elle-même reçue : posée depuis le disque
        assertEquals(LateSubtitleLogic.Split(listOf(shifted), emptyList()), LateSubtitleLogic.split(listOf(shifted), embedded, setOf(shifted.url)))
        assertEquals("/api/tv/subtitle/x/3.ass", LateSubtitleLogic.base(shifted.url))
    }

    @Test
    fun `apres un echec, redemander, attendre, ou renoncer`() {
        val elapsed = 60_000L
        // Pas de réponse dans le délai du client : l'extraction continue, on la rejoint
        assertEquals(Next.RETRY_NOW, LateSubtitleLogic.afterFailure(Failure.Timeout, attemptMs = 45_000, elapsedMs = elapsed))
        // Le serveur ArrMada a coupé son relais vers Jellyfin au bout de 30 s (502) : pareil
        assertEquals(Next.RETRY_NOW, LateSubtitleLogic.afterFailure(Failure.Http(502), attemptMs = 30_000, elapsedMs = elapsed))
        // Erreur 5xx immédiate, serveur injoignable : on souffle avant de redemander
        assertEquals(Next.RETRY_AFTER_PAUSE, LateSubtitleLogic.afterFailure(Failure.Http(500), attemptMs = 200, elapsedMs = elapsed))
        assertEquals(Next.RETRY_AFTER_PAUSE, LateSubtitleLogic.afterFailure(Failure.Unreachable, attemptMs = 200, elapsedMs = elapsed))
        // Piste inconnue du serveur : abandonnée pour la séance
        assertEquals(Next.GIVE_UP, LateSubtitleLogic.afterFailure(Failure.Http(404), attemptMs = 200, elapsedMs = elapsed))
        assertEquals(Next.GIVE_UP, LateSubtitleLogic.afterFailure(Failure.Http(404), attemptMs = 30_000, elapsedMs = elapsed))
        // Budget épuisé : on arrête d'attendre, sans condamner la piste
        assertEquals(Next.OUT_OF_TIME, LateSubtitleLogic.afterFailure(Failure.Timeout, attemptMs = 45_000, elapsedMs = LateSubtitleLogic.MAX_WAIT_MS))
        assertEquals(Next.OUT_OF_TIME, LateSubtitleLogic.afterFailure(Failure.Http(404), attemptMs = 200, elapsedMs = LateSubtitleLogic.MAX_WAIT_MS + 1))
    }

    @Test
    fun `la piste affichee avant la bascule reviendra-t-elle plus tard`() {
        val later = listOf(inMkvFr, inMkvForced)
        // Piste du MKV lue en direct (« fre », sans nom) : son extraction est attendue
        assertTrue(LateSubtitleLogic.comingLater(StreamSwitchLogic.Shown(null, "fre", forced = false), later))
        assertTrue(LateSubtitleLogic.comingLater(StreamSwitchLogic.Shown("Forced", "fre", forced = true), later))
        // Seuls les forcés sont attendus : les complets ne reviendront pas par eux
        assertFalse(LateSubtitleLogic.comingLater(StreamSwitchLogic.Shown("Français", "fr", forced = false), listOf(inMkvForced)))
        // Autre langue, ou plus rien d'attendu
        assertFalse(LateSubtitleLogic.comingLater(StreamSwitchLogic.Shown(null, "en", forced = false), later))
        assertFalse(LateSubtitleLogic.comingLater(StreamSwitchLogic.Shown("Français", "fr", forced = false), emptyList()))
        assertEquals("Sous-titres « Français » en préparation : ils reviendront tout seuls", LateSubtitleLogic.waitingMessage("Français"))
    }

    @Test
    fun `nom du fichier local, extension gardee, adresses distinctes`() {
        assertTrue(LateSubtitleLogic.fileName(inMkvFr.url).endsWith(".ass"))
        assertTrue(LateSubtitleLogic.fileName(fileFr.url).endsWith(".srt"))
        // La copie décalée n'écrase pas la piste d'origine
        assertNotEquals(LateSubtitleLogic.fileName(inMkvFr.url), LateSubtitleLogic.fileName(shifted.url))
        assertTrue(LateSubtitleLogic.fileName(shifted.url).endsWith(".ass"))
        // Adresse sans extension lisible : .srt par défaut
        assertTrue(LateSubtitleLogic.fileName("/api/tv/subtitle/x/3").endsWith(".srt"))
        assertFalse('/' in LateSubtitleLogic.fileName(inMkvFr.url))
    }
}
