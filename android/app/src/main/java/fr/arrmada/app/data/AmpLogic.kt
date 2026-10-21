package fr.arrmada.app.data

/**
 * Ampli Yamaha, depuis l'onglet « Ampli » du menu pause : les réglages
 * utiles pendant un film (voix, mode nuit, programme sonore, volume). Le
 * reste (marche, entrée, préréglage de la pièce) se fait tout seul au
 * lancement, ou à la télécommande de la Shield (HDMI-CEC).
 */
object AmpLogic {

    const val VOLUME_STEP = 4 // un appui sur Vol + / Vol − (comme l'add-on)

    /** Programmes proposés pendant un film : (identifiant Yamaha, libellé). */
    val PROGRAMS = listOf(
        "straight" to "Son d’origine",
        "surr_decoder" to "Surround",
        "drama" to "Drama",
        "spectacle" to "Spectacle",
    )

    /** Niveau des dialogues (Yamaha « Dialogue Level » 0 à 3). */
    val DIALOG_LEVELS = listOf(0 to "Normal", 1 to "+1", 2 to "+2", 3 to "+3")

    private val ALL_PROGRAMS = mapOf(
        "straight" to "Straight", "surr_decoder" to "Surround Decoder", "7ch_stereo" to "7ch Stereo",
        "all_ch_stereo" to "All-Ch Stereo", "2ch_stereo" to "2ch Stereo", "standard" to "Standard",
        "spectacle" to "Spectacle", "sci-fi" to "Sci-Fi", "adventure" to "Adventure", "drama" to "Drama",
        "enhanced" to "Enhanced", "music_video" to "Music Video", "game" to "Game",
    )

    /** « surr_decoder » → « Surround Decoder ». */
    fun programName(id: String?): String = id?.let { ALL_PROGRAMS[it] ?: it }.orEmpty()

    /** −42.5 → « −42,5 dB » (moins typographique). */
    fun decibels(db: Double?): String = db?.let { Fr.decimal(it) + " dB" }?.replace("-", "−").orEmpty()

    /** « 42 % · −38,5 dB · Surround Decoder » sous le titre de l'onglet. */
    fun summary(amp: AmpDevice): String = listOf(
        "${amp.volumePct} %",
        decibels(amp.actualDb),
        programName(amp.soundProgram),
        if (amp.mute) "muet" else "",
    ).filter { it.isNotBlank() }.joinToString(" · ")
}
