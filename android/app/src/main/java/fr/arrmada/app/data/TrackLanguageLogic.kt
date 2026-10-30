package fr.arrmada.app.data

import java.util.Locale

/**
 * Pistes choisies d'office au lancement d'un film ou d'un épisode, sans
 * écran : testé en JVM.
 *
 * D'abord, le **dernier choix du profil** pour ce titre ([Remembered]) :
 * quelqu'un a passé la série en VF, coupé les sous-titres… l'épisode
 * suivant reprend ce choix (rangé sur le serveur, par profil). S'il n'y en
 * a pas, ou si le fichier n'a pas la piste voulue, la règle automatique :
 *  1. Titre étranger (langue originale connue, pas le français) dont le
 *     fichier a la piste audio originale ET des sous-titres français
 *     complets → VO + sous-titres français.
 *  2. Sinon, s'il y a une piste audio française (film français, ou VF
 *     faute de sous-titres) → français + sous-titres français « forcés »
 *     s'il y en a (les passages dans une autre langue), rien sinon.
 *  3. Sinon (VO seule) → la VO, avec des sous-titres français si possible.
 *
 * Langue originale inconnue (vidéo hors médiathèque, Sonarr v3…) : on
 * retombe sur la règle 2, l'ancien comportement.
 */
object TrackLanguageLogic {
    /** Piste audio vue par la logique (même ordre que le menu pause). */
    data class Audio(val language: String?, val supported: Boolean = true)

    /** Piste de sous-titres : [forced] = passages en langue étrangère seulement. */
    data class Text(
        val language: String?,
        val forced: Boolean = false,
        val supported: Boolean = true,
        val isDefault: Boolean = false,
        val label: String? = null,
    )

    /**
     * Choix : index dans les listes passées, null = laisser (audio) / couper (sous-titres).
     * [textLanguage] : langue de sous-titres à préférer au lecteur (rechargement du flux),
     * null quand seuls des « forcés » (ou rien) sont voulus.
     */
    data class Plan(
        val audio: Int?,
        val text: Int?,
        val audioLanguage: String?,
        val fullSubtitles: Boolean,
        val textLanguage: String? = if (fullSubtitles) FRENCH else null,
    )

    /**
     * Dernier choix d'un profil pour un titre. [subtitle] : langue (« fr »),
     * [SUBTITLES_OFF] (coupés) ou null (pas de choix sur les sous-titres).
     */
    data class Remembered(val audio: String?, val subtitle: String?, val subtitleForced: Boolean = false)

    const val SUBTITLES_OFF = "off"
    private const val FRENCH = "fr"

    // Noms de Radarr / Sonarr que Locale ne reconnaît pas tels quels
    private val ALIASES = mapOf(
        "flemish" to "nl",
        "mandarin" to "zh",
        "cantonese" to "zh",
        "portuguese (brazil)" to "pt",
        "spanish (latino)" to "es",
        "latino" to "es",
        "farsi" to "fa",
        "tagalog" to "tl",
    )

    // Index des noms anglais des langues ISO 639-1 (« french » → « fr »), construit une fois
    private val BY_ENGLISH_NAME: Map<String, String> by lazy {
        Locale.getISOLanguages().associateBy { Locale.forLanguageTag(it).getDisplayLanguage(Locale.ENGLISH).lowercase(Locale.ROOT) }
    }

    /** « French » (nom Radarr / Sonarr) → « fr » ; null si inconnu. */
    fun isoCode(name: String?): String? {
        val key = name?.trim()?.lowercase(Locale.ROOT)?.takeIf { it.isNotEmpty() } ?: return null
        ALIASES[key]?.let { return it }
        BY_ENGLISH_NAME[key]?.let { return it }
        // « Portuguese (Portugal) », « Chinese (Simplified) »… : le nom avant la parenthèse
        return BY_ENGLISH_NAME[key.substringBefore('(').trim()]
    }

    /** Code de piste (« fre », « fra », « fr-FR », « FR ») → « fr » ; null si indéterminé. */
    fun normalize(code: String?): String? {
        val raw = code?.trim()?.takeIf { it.isNotEmpty() } ?: return null
        val base = raw.substringBefore('-').substringBefore('_').lowercase(Locale.ROOT)
        if (base == "und" || base == "mul" || base == "zxx") return null
        if (base.length == 2) return base
        // Codes à 3 lettres : « fre » (bibliographique) et « fra » (terminologique)
        return when (base) {
            "fre", "fra" -> "fr"
            "ger", "deu" -> "de"
            "dut", "nld" -> "nl"
            "chi", "zho" -> "zh"
            "cze", "ces" -> "cs"
            "gre", "ell" -> "el"
            "per", "fas" -> "fa"
            "rum", "ron" -> "ro"
            "slo", "slk" -> "sk"
            else -> Locale.getISOLanguages().firstOrNull { Locale.forLanguageTag(it).isO3Language == base } ?: base
        }
    }

    /** Sous-titres « forcés » : drapeau du fichier, ou nom de piste qui le dit. */
    fun isForced(flagForced: Boolean, label: String?): Boolean =
        flagForced || label?.contains("forc", ignoreCase = true) == true

    /**
     * Titre sous lequel le choix est rangé sur le serveur : la série entière
     * (tous ses épisodes), le film, ou la série maison ; null : rien à ranger
     * (vidéo isolée de l'écran Vidéos).
     */
    fun scope(kind: String, id: Long, localSeries: Int): String? = when {
        kind == "movie" && id > 0 -> "movie:tmdb:$id"
        kind == "episode" && id > 0 -> "series:tvdb:$id"
        kind == "file" && localSeries > 0 -> "local:$localSeries"
        else -> null
    }

    /**
     * Ce qui est lu en ce moment, à ranger quand l'utilisateur change de piste.
     * [subtitleLanguage] null avec [subtitlesOn] faux : sous-titres coupés.
     */
    fun remember(audioLanguage: String?, subtitlesOn: Boolean, subtitleLanguage: String?, subtitleForced: Boolean): Remembered =
        Remembered(
            audio = normalize(audioLanguage),
            subtitle = if (!subtitlesOn) SUBTITLES_OFF else normalize(subtitleLanguage),
            subtitleForced = subtitlesOn && subtitleForced,
        )

    /** Les pistes à choisir : le dernier choix du profil s'il s'applique, sinon la règle automatique. */
    fun plan(originalLanguage: String?, audios: List<Audio>, texts: List<Text>, remembered: Remembered? = null): Plan {
        val automatic = automaticPlan(originalLanguage, audios, texts)
        if (remembered == null) return automatic

        // Audio voulu absent de ce fichier (épisode sans VF…) : la règle automatique, en entier
        val wantedAudio = normalize(remembered.audio)
        val audio = if (wantedAudio == null) {
            automatic.audio
        } else {
            audios.indexOfFirst { it.supported && normalize(it.language) == wantedAudio }.takeIf { it >= 0 } ?: return automatic
        }
        val audioLanguage = wantedAudio ?: automatic.audioLanguage

        return when (val wantedText = remembered.subtitle) {
            // Pas de choix sur les sous-titres : ceux de la règle
            null -> automatic.copy(audio = audio, audioLanguage = audioLanguage)
            SUBTITLES_OFF -> Plan(audio, null, audioLanguage, fullSubtitles = false, textLanguage = null)
            else -> {
                val lang = normalize(wantedText)
                // La même sorte (complets / forcés) d'abord, sinon l'autre, dans la langue voulue
                val text = lang?.let { bestText(texts, it, remembered.subtitleForced) ?: bestText(texts, it, !remembered.subtitleForced) }
                if (text == null) {
                    automatic.copy(audio = audio, audioLanguage = audioLanguage)
                } else {
                    val forced = isForced(texts[text].forced, texts[text].label)
                    Plan(audio, text, audioLanguage, fullSubtitles = !forced, textLanguage = if (forced) null else lang)
                }
            }
        }
    }

    /** Langues audio à préférer au lecteur (rechargement du flux : même choix). */
    fun preferredAudioLanguages(plan: Plan): List<String> =
        listOfNotNull(plan.audioLanguage, FRENCH, "en").distinct()

    // Règle automatique (voir l'en-tête du fichier)
    private fun automaticPlan(originalLanguage: String?, audios: List<Audio>, texts: List<Text>): Plan {
        val original = normalize(originalLanguage)
        val originalAudio = original?.let { lang -> audios.indexOfFirst { it.supported && normalize(it.language) == lang } }?.takeIf { it >= 0 }
        val frenchAudio = audios.indexOfFirst { it.supported && normalize(it.language) == FRENCH }.takeIf { it >= 0 }
        val fullFrench = bestText(texts, FRENCH, forced = false)
        val forcedFrench = bestText(texts, FRENCH, forced = true)

        // 1. Titre étranger : VO + sous-titres français complets
        if (original != null && original != FRENCH && originalAudio != null && fullFrench != null) {
            return Plan(originalAudio, fullFrench, original, fullSubtitles = true)
        }
        // 2. Piste française : forcés français seulement (dialogues dans une autre langue)
        if (frenchAudio != null) {
            return Plan(frenchAudio, forcedFrench, FRENCH, fullSubtitles = false)
        }
        // 3. Pas de français à l'oreille : la VO (sinon la piste par défaut), sous-titres FR si possible
        val subtitle = fullFrench ?: forcedFrench
        return Plan(originalAudio, subtitle, original, fullSubtitles = subtitle != null && subtitle == fullFrench)
    }

    // Meilleure piste de la langue [lang] : celle marquée « par défaut » d'abord, sinon la première lisible
    private fun bestText(texts: List<Text>, lang: String, forced: Boolean): Int? {
        val candidates = texts.withIndex().filter {
            it.value.supported && normalize(it.value.language) == lang && isForced(it.value.forced, it.value.label) == forced
        }
        return (candidates.firstOrNull { it.value.isDefault } ?: candidates.firstOrNull())?.index
    }
}
