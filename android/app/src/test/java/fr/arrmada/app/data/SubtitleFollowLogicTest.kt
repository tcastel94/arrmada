package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Menu pause › « Sous-titres FR » : la TV suit la recherche du serveur. */
class SubtitleFollowLogicTest {

    @Test
    fun `redemande tant que le serveur cherche, dans la limite`() {
        assertTrue(SubtitleFollowLogic.shouldFollow("pending", 1))
        assertTrue(SubtitleFollowLogic.shouldFollow("pending", SubtitleFollowLogic.MAX_ROUNDS - 1))
        assertFalse(SubtitleFollowLogic.shouldFollow("pending", SubtitleFollowLogic.MAX_ROUNDS))
        // Résultat final : on s'arrête tout de suite
        for (status in listOf("ok", "none", "error")) assertFalse(SubtitleFollowLogic.shouldFollow(status, 1))
    }

    @Test
    fun `etape affichee sous le bouton`() {
        val phase = SubtitleResult(status = "pending", phase = "Recherche élargie (versions approchantes)")
        assertEquals("Bazarr : recherche élargie (versions approchantes)…", SubtitleFollowLogic.progressNote(phase))
        // Ancien serveur (pas d'étape) ou étape vide
        assertEquals("Bazarr cherche encore…", SubtitleFollowLogic.progressNote(SubtitleResult(status = "pending")))
        assertEquals("Bazarr cherche encore…", SubtitleFollowLogic.progressNote(SubtitleResult(status = "pending", phase = "Terminé")))
    }
}
