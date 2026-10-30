package fr.arrmada.app.data

import fr.arrmada.app.data.HomeLayoutLogic.Row
import fr.arrmada.app.data.HomeLayoutLogic.Slot
import org.junit.Assert.assertEquals
import org.junit.Test

class HomeLayoutLogicTest {

    @Test
    fun `sans reglage, ordre d'origine, tout visible`() {
        assertEquals(HomeLayoutLogic.DEFAULT, HomeLayoutLogic.parse(null))
        assertEquals(HomeLayoutLogic.DEFAULT, HomeLayoutLogic.parse(""))
        assertEquals(Row.entries.toList(), HomeLayoutLogic.visible(HomeLayoutLogic.DEFAULT))
    }

    @Test
    fun `aller-retour : ordre et rangees masquees conserves`() {
        val slots = listOf(
            Slot(Row.RECENT), Slot(Row.RESUME), Slot(Row.WATCHLIST, visible = false), Slot(Row.FOR_YOU), Slot(Row.UPCOMING, visible = false),
        )
        val text = HomeLayoutLogic.serialize(slots)
        assertEquals("recent,resume,-watchlist,foryou,-upcoming", text)
        assertEquals(slots, HomeLayoutLogic.parse(text))
        assertEquals(listOf(Row.RECENT, Row.RESUME, Row.FOR_YOU), HomeLayoutLogic.visible(slots))
    }

    @Test
    fun `nom inconnu ignore, rangee absente remise a la fin, doublon ignore`() {
        val slots = HomeLayoutLogic.parse("upcoming, inconnu ,-resume,upcoming")
        assertEquals(
            listOf(Slot(Row.UPCOMING), Slot(Row.RESUME, visible = false), Slot(Row.WATCHLIST), Slot(Row.RECENT), Slot(Row.FOR_YOU)),
            slots,
        )
    }

    @Test
    fun `masquer puis reafficher`() {
        val hidden = HomeLayoutLogic.toggle(HomeLayoutLogic.DEFAULT, Row.FOR_YOU)
        assertEquals(false, hidden.first { it.row == Row.FOR_YOU }.visible)
        assertEquals(HomeLayoutLogic.DEFAULT, HomeLayoutLogic.toggle(hidden, Row.FOR_YOU))
    }

    @Test
    fun `monter une rangee, sans effet sur la premiere`() {
        val moved = HomeLayoutLogic.moveUp(HomeLayoutLogic.DEFAULT, Row.RECENT)
        assertEquals(listOf(Row.RESUME, Row.RECENT, Row.WATCHLIST, Row.FOR_YOU, Row.UPCOMING), moved.map { it.row })
        assertEquals(HomeLayoutLogic.DEFAULT, HomeLayoutLogic.moveUp(HomeLayoutLogic.DEFAULT, Row.RESUME))
    }
}
