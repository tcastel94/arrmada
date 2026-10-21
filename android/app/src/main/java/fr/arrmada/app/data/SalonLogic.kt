package fr.arrmada.app.data

/** Écran Salon : état de l'ampli Yamaha, comme l'add-on (screens_data.build_salon). */
object SalonLogic {

    const val VOLUME_STEP = 4 // un appui sur Vol + / Vol − (comme l'add-on)

    val SOUND_PROGRAMS = mapOf(
        "straight" to "Straight", "surr_decoder" to "Surround Decoder", "7ch_stereo" to "7ch Stereo",
        "all_ch_stereo" to "All-Ch Stereo", "2ch_stereo" to "2ch Stereo", "standard" to "Standard",
        "spectacle" to "Spectacle", "sci-fi" to "Sci-Fi", "adventure" to "Adventure", "drama" to "Drama",
        "enhanced" to "Enhanced", "music_video" to "Music Video", "game" to "Game",
    )

    private val INPUT = Regex("""^([a-z_]+?)(\d+)$""")

    /** « hdmi1 » → « HDMI 1 », « av_on » → « Av On ». */
    fun input(value: String?): String {
        val v = value.orEmpty()
        val m = INPUT.matchEntire(v)
        if (m != null && m.groupValues[1] in listOf("hdmi", "av", "audio", "optical", "coaxial")) {
            return "${m.groupValues[1].uppercase()} ${m.groupValues[2]}"
        }
        return v.replace("_", " ").split(" ").filter { it.isNotEmpty() }
            .joinToString(" ") { w -> w.lowercase().replaceFirstChar { it.uppercase() } }
    }

    /** −42.5 → « −42,5 dB » (moins typographique). */
    fun decibels(db: Double?): String = db?.let { Fr.decimal(it) + " dB" }?.replace("-", "−").orEmpty()

    data class Amp(
        val configured: Boolean,
        val online: Boolean,
        val name: String,
        val power: String,
        val isOn: Boolean,
        val volumePct: Int,
        val decibels: String,
        val mute: Boolean,
        val input: String,
        val program: String,
    )

    fun amp(state: AmpState): Amp {
        val device = state.devices.firstOrNull()
        val online = device?.online == true
        return Amp(
            configured = device != null,
            online = online,
            name = device?.name?.ifBlank { null } ?: "Ampli Yamaha",
            power = when {
                device?.power == "on" -> "Allumé"
                online -> "En veille"
                else -> "Hors ligne"
            },
            isOn = device?.power == "on",
            volumePct = device?.volumePct ?: 0,
            decibels = decibels(device?.actualDb),
            mute = device?.mute == true,
            input = input(device?.input),
            program = device?.soundProgram?.let { SOUND_PROGRAMS[it] ?: it }.orEmpty(),
        )
    }

    /** Message sous l'ampli quand il n'y a rien à piloter. */
    fun message(state: AmpState?, hasAmp: Boolean): String? = when {
        !hasAmp || state?.status == "no_amp" -> "Pas d’ampli dans cette pièce : le son passe par la TV."
        state == null -> "L’ampli ne répond pas pour l’instant."
        state.devices.isEmpty() -> "Aucun ampli Yamaha configuré (web app › Réglages › Services)."
        !state.devices.first().online -> "L’ampli ne répond pas : vérifie qu’il est branché et sur le réseau."
        else -> null
    }
}
