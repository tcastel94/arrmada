package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SagaRulesTest {
    private val dune = Saga(title = "Dune", total = 3, available = 1, missing = 1, upcoming = 1, years = listOf(2021, 2026))

    @Test
    fun badge() {
        assertEquals("1 film manquant", SagaRules.badge(dune))
        assertEquals("2 films annoncés", SagaRules.badge(Saga(total = 4, available = 2, upcoming = 2)))
        assertEquals("1 en recherche", SagaRules.badge(Saga(total = 3, available = 2, wanted = 1)))
        assertEquals("Complète", SagaRules.badge(Saga(total = 3, available = 3, complete = true)))
    }

    @Test
    fun factsAndProgress() {
        assertEquals("3 films · 2021 – 2026 · 1 sur le NAS", SagaRules.facts(dune))
        assertEquals(1f / 3, SagaRules.progress(dune), 0.001f)
        assertEquals(0f, SagaRules.progress(Saga()), 0f)
    }

    @Test
    fun filmTags() {
        assertNull(SagaRules.tag(SagaFilm(state = "available")))
        assertEquals("+ Ajouter", SagaRules.tag(SagaFilm(state = "missing")))
        assertEquals("Annoncé 2026", SagaRules.tag(SagaFilm(state = "upcoming", year = 2026)))
        assertTrue(SagaRules.dimmed(SagaFilm(state = "upcoming")))
        assertFalse(SagaRules.dimmed(SagaFilm(state = "wanted")))
        assertEquals("2 · 2002", SagaRules.position(1, SagaFilm(year = 2002)))
    }
}
