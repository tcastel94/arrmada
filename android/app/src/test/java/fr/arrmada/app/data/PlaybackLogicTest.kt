package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** « Passer l'intro » et « Épisode suivant ». */
class PlaybackLogicTest {

    private fun chapters(vararg list: Pair<String, Double>) = list.mapIndexed { i, (name, start) -> Chapter(i, name, start) }

    @Test
    fun `chapitres nommes - intro, recap et generique de fin`() {
        val info = PlayInfo(chapters = chapters("Previously" to 0.0, "Générique" to 60.0, "Épisode" to 120.0, "Générique" to 2500.0))
        val segments = PlaybackLogic.chapterSegments(info.chapters, 2600.0)
        assertEquals(listOf("recap" to 0.0, "intro" to 60.0, "credits" to 2500.0), segments.map { it.kind to it.start })
        assertEquals(120.0, segments[1].end, 0.0)
        assertEquals(2600.0, segments[2].end, 0.0)
    }

    @Test
    fun `chapitres d'abord, marqueurs Jellyfin sinon`() {
        val jellyfin = listOf(Segment("intro", 95.0, 152.0), Segment("credits", 2580.0, 2640.0))
        val withChapters = PlayInfo(chapters = chapters("Opening" to 30.0, "Part 1" to 90.0), segments = jellyfin)
        assertEquals(30.0, PlaybackLogic.skippable(withChapters, 2640.0).single().start, 0.0)
        val noChapters = PlayInfo(chapters = chapters("Chapitre 1" to 0.0, "Chapitre 2" to 600.0), segments = jellyfin)
        assertEquals(95.0, PlaybackLogic.skippable(noChapters, 2640.0).single().start, 0.0)
    }

    @Test
    fun `bouton visible les 15 premieres secondes`() {
        val skips = listOf(Segment("intro", 95.0, 152.0))
        assertNull(PlaybackLogic.activeSkip(skips, 90.0))
        assertEquals("Passer l’intro", PlaybackLogic.skipLabel(PlaybackLogic.activeSkip(skips, 100.0)!!))
        assertNull(PlaybackLogic.activeSkip(skips, 115.0))
    }

    @Test
    fun `episode suivant au generique, sinon 30 s avant la fin`() {
        val credits = PlayInfo(segments = listOf(Segment("credits", 2580.0, 2640.0)))
        assertEquals(2580.0, PlaybackLogic.upNextAt(credits, 2640.0), 0.0)
        assertEquals(2610.0, PlaybackLogic.upNextAt(PlayInfo(), 2640.0), 0.0)
        assertNull(PlaybackLogic.creditsStart(PlayInfo(), 2640.0))
    }
}
