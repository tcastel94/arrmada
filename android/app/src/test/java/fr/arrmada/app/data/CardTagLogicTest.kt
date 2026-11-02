package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate
import java.time.ZoneId

/** Étiquette « Ajouté… » des cartes : une semaine, puis plus rien. */
class CardTagLogicTest {

    private val today = LocalDate.of(2026, 10, 30)
    private val paris = ZoneId.of("Europe/Paris")

    @Test
    fun addedLabels() {
        assertEquals("Aujourd’hui", CardTagLogic.added("2026-10-30T08:00:00Z", today, paris))
        assertEquals("Hier", CardTagLogic.added("2026-10-29", today, paris))
        assertEquals("Il y a 3 j", CardTagLogic.added("2026-10-27T12:00:00+00:00", today, paris))
        assertEquals("Il y a 6 j", CardTagLogic.added("2026-10-24", today, paris))
    }

    @Test
    fun noLabel() {
        assertNull(CardTagLogic.added("2026-10-23", today, paris)) // une semaine : plus d'étiquette
        assertNull(CardTagLogic.added("2026-11-02", today, paris)) // date future
        assertNull(CardTagLogic.added(null, today, paris))
        assertNull(CardTagLogic.added("", today, paris))
        assertNull(CardTagLogic.added("hier", today, paris))
    }

    @Test
    fun utcEveningIsNextDayInParis() {
        // 23:30 UTC le 29 = 00:30 le 30 à Paris : ajouté « aujourd'hui »
        assertEquals("Aujourd’hui", CardTagLogic.added("2026-10-29T23:30:00Z", today, paris))
    }
}
