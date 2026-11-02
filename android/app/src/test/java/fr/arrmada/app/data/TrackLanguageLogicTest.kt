package fr.arrmada.app.data

import fr.arrmada.app.data.TrackLanguageLogic.Audio
import fr.arrmada.app.data.TrackLanguageLogic.Text
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pistes choisies d'office : VO + sous-titres FR, ou VF + forcés pour un film français. */
class TrackLanguageLogicTest {

    private val multi = listOf(Audio("fra"), Audio("eng"))
    private val subs = listOf(Text("fre", forced = true), Text("fre"), Text("eng"))

    @Test
    fun languageNamesFromRadarr() {
        assertEquals("fr", TrackLanguageLogic.isoCode("French"))
        assertEquals("en", TrackLanguageLogic.isoCode("english"))
        assertEquals("ja", TrackLanguageLogic.isoCode("Japanese"))
        assertEquals("pt", TrackLanguageLogic.isoCode("Portuguese (Brazil)"))
        assertEquals("nl", TrackLanguageLogic.isoCode("Flemish"))
        assertNull(TrackLanguageLogic.isoCode(""))
        assertNull(TrackLanguageLogic.isoCode(null))
    }

    @Test
    fun trackCodesAreNormalized() {
        assertEquals("fr", TrackLanguageLogic.normalize("fre"))
        assertEquals("fr", TrackLanguageLogic.normalize("fra"))
        assertEquals("fr", TrackLanguageLogic.normalize("fr-FR"))
        assertEquals("en", TrackLanguageLogic.normalize("eng"))
        assertEquals("ja", TrackLanguageLogic.normalize("jpn"))
        assertNull(TrackLanguageLogic.normalize("und"))
        assertNull(TrackLanguageLogic.normalize(null))
    }

    @Test
    fun foreignTitleWithFrenchSubtitlesPlaysOriginalVersion() {
        val plan = TrackLanguageLogic.plan("en", multi, subs)
        assertEquals(1, plan.audio) // anglais
        assertEquals(1, plan.text) // français complet, pas les forcés
        assertTrue(plan.fullSubtitles)
        assertEquals(listOf("en", "fr"), TrackLanguageLogic.preferredAudioLanguages(plan))
    }

    @Test
    fun frenchTitleGetsForcedSubtitlesOnly() {
        val plan = TrackLanguageLogic.plan("fr", multi, subs)
        assertEquals(0, plan.audio)
        assertEquals(0, plan.text) // forcés : passages en langue étrangère
        assertFalse(plan.fullSubtitles)
        // Pas de forcés : aucun sous-titre
        assertNull(TrackLanguageLogic.plan("fr", multi, listOf(Text("fre"), Text("eng"))).text)
    }

    @Test
    fun forcedTrackDetectedByItsName() {
        val texts = listOf(Text("fre", label = "Français (Forcés)"), Text("fre", label = "Français complet"))
        assertEquals(0, TrackLanguageLogic.plan("fr", multi, texts).text)
        assertEquals(1, TrackLanguageLogic.plan("en", multi, texts).text)
    }

    @Test
    fun withoutFrenchSubtitlesForeignTitleFallsBackToFrenchAudio() {
        val plan = TrackLanguageLogic.plan("en", multi, listOf(Text("fre", forced = true), Text("eng")))
        assertEquals(0, plan.audio) // VF
        assertEquals(0, plan.text) // forcés français
    }

    @Test
    fun originalAudioMissingKeepsFrench() {
        val plan = TrackLanguageLogic.plan("ja", multi, subs) // fichier sans piste japonaise
        assertEquals(0, plan.audio)
        assertEquals(0, plan.text)
    }

    @Test
    fun originalOnlyFileGetsFrenchSubtitles() {
        val plan = TrackLanguageLogic.plan("ko", listOf(Audio("kor")), subs)
        assertEquals(0, plan.audio)
        assertEquals(1, plan.text)
        assertTrue(plan.fullSubtitles)
    }

    @Test
    fun unknownOriginalLanguageKeepsFrenchAndForced() {
        val plan = TrackLanguageLogic.plan(null, multi, subs)
        assertEquals(0, plan.audio)
        assertEquals(0, plan.text)
    }

    @Test
    fun defaultFlaggedFrenchTrackPreferredAndUnsupportedSkipped() {
        val texts = listOf(Text("fre", supported = false), Text("fre"), Text("fre", isDefault = true))
        assertEquals(2, TrackLanguageLogic.plan("en", multi, texts).text)
        assertEquals(1, TrackLanguageLogic.plan("en", multi, texts.dropLast(1)).text)
    }

    // ── Dernier choix du profil (épisode suivant, autre TV) ──

    @Test
    fun rememberedFrenchDubWithoutSubtitlesWinsOverRule() {
        val remembered = TrackLanguageLogic.Remembered(audio = "fr", subtitle = TrackLanguageLogic.SUBTITLES_OFF)
        val plan = TrackLanguageLogic.plan("en", multi, subs, remembered)
        assertEquals(0, plan.audio) // VF, alors que la règle donnerait la VO
        assertNull(plan.text)
        assertNull(plan.textLanguage)
    }

    @Test
    fun rememberedEnglishSubtitles() {
        val remembered = TrackLanguageLogic.Remembered(audio = "en", subtitle = "en")
        val plan = TrackLanguageLogic.plan("en", multi, subs, remembered)
        assertEquals(1, plan.audio)
        assertEquals(2, plan.text) // sous-titres anglais
        assertEquals("en", plan.textLanguage)
        assertEquals(listOf("en", "fr"), TrackLanguageLogic.preferredAudioLanguages(plan))
    }

    @Test
    fun rememberedForcedOnlyAndMissingKindFallsBackToOther() {
        val forced = TrackLanguageLogic.Remembered(audio = "fr", subtitle = "fr", subtitleForced = true)
        assertEquals(0, TrackLanguageLogic.plan("en", multi, subs, forced).text)
        // Cet épisode n'a pas de forcés : les français complets
        val plan = TrackLanguageLogic.plan("en", multi, listOf(Text("fre"), Text("eng")), forced)
        assertEquals(0, plan.text)
        assertTrue(plan.fullSubtitles)
    }

    @Test
    fun rememberedAudioMissingInThisFileUsesTheRule() {
        val remembered = TrackLanguageLogic.Remembered(audio = "ja", subtitle = TrackLanguageLogic.SUBTITLES_OFF)
        assertEquals(TrackLanguageLogic.plan("en", multi, subs), TrackLanguageLogic.plan("en", multi, subs, remembered))
    }

    @Test
    fun rememberedSubtitleLanguageMissingKeepsRuleSubtitles() {
        val remembered = TrackLanguageLogic.Remembered(audio = "en", subtitle = "de")
        val plan = TrackLanguageLogic.plan("en", multi, subs, remembered)
        assertEquals(1, plan.audio)
        assertEquals(1, plan.text) // pas d'allemand : français complets de la règle
    }

    @Test
    fun whatIsPlayingIsRemembered() {
        assertEquals(
            TrackLanguageLogic.Remembered("fr", TrackLanguageLogic.SUBTITLES_OFF, false),
            TrackLanguageLogic.remember("fra", subtitlesOn = false, subtitleLanguage = "fre", subtitleForced = true),
        )
        assertEquals(TrackLanguageLogic.Remembered("en", "fr", true), TrackLanguageLogic.remember("eng", true, "fre", true))
    }

    @Test
    fun scopeOfATitle() {
        assertEquals("movie:tmdb:438631", TrackLanguageLogic.scope("movie", 438631, 0))
        assertEquals("series:tvdb:280619", TrackLanguageLogic.scope("episode", 280619, 0))
        assertEquals("local:12", TrackLanguageLogic.scope("file", 0, 12))
        assertNull(TrackLanguageLogic.scope("file", 0, 0)) // vidéo isolée : rien à ranger
    }
}
