package fr.arrmada.app

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.RadioGroup
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.core.view.WindowCompat
import androidx.core.view.isVisible
import kotlin.concurrent.thread

/**
 * Écran de connexion : saisie de l'adresse du serveur ArrMada.
 *
 * Affiché au premier lancement, puis depuis le menu « Changer de serveur ».
 * L'adresse est testée (le serveur répond-il, et est-ce bien ArrMada ?) avant
 * d'être enregistrée : une faute de frappe se voit tout de suite, pas sous la
 * forme d'une page blanche.
 */
class SetupActivity : ComponentActivity() {

    private lateinit var urlField: EditText
    private lateinit var status: TextView
    private lateinit var busy: ProgressBar
    private lateinit var saveButton: Button
    private lateinit var saveAnywayButton: Button
    private lateinit var tvWidthGroup: RadioGroup
    private var isTv = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContentView(R.layout.activity_setup)
        applySystemBarPadding(findViewById(R.id.root))

        urlField = findViewById(R.id.server_url)
        status = findViewById(R.id.status)
        busy = findViewById(R.id.busy)
        saveButton = findViewById(R.id.save)
        saveAnywayButton = findViewById(R.id.save_anyway)
        tvWidthGroup = findViewById(R.id.tv_width)
        isTv = ServerConfig.isTv(this)

        urlField.setText(ServerConfig.url(this) ?: "")
        findViewById<TextView>(R.id.version).text =
            getString(R.string.setup_version, BuildConfig.VERSION_NAME)

        // Taille de l'interface : réglage utile sur TV uniquement.
        findViewById<View>(R.id.tv_section).isVisible = isTv
        tvWidthGroup.check(
            when (ServerConfig.tvWidth(this)) {
                ServerConfig.TV_WIDTH_LARGE -> R.id.tv_width_large
                ServerConfig.TV_WIDTH_COMPACT -> R.id.tv_width_compact
                else -> R.id.tv_width_normal
            }
        )

        saveButton.setOnClickListener { submit(test = true) }
        saveAnywayButton.setOnClickListener { submit(test = false) }
        // Touche « OK / Aller » du clavier à l'écran = même chose que le bouton.
        urlField.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_GO) {
                submit(test = true)
                true
            } else {
                false
            }
        }
        urlField.requestFocus()
    }

    private fun selectedTvWidth(): Int = when (tvWidthGroup.checkedRadioButtonId) {
        R.id.tv_width_large -> ServerConfig.TV_WIDTH_LARGE
        R.id.tv_width_compact -> ServerConfig.TV_WIDTH_COMPACT
        else -> ServerConfig.TV_WIDTH_NORMAL
    }

    private fun submit(test: Boolean) {
        val url = ServerUrl.normalize(urlField.text.toString())
        if (url == null) {
            showStatus(getString(R.string.setup_invalid), isError = true)
            return
        }
        urlField.setText(url) // montre l'adresse telle qu'elle sera utilisée
        if (!test) {
            saveAndOpen(url)
            return
        }

        setBusy(true)
        showStatus(getString(R.string.setup_testing, url), isError = false)
        // Le test réseau tourne dans un fil à part ; le résultat revient sur
        // le fil de l'écran par runOnUiThread.
        thread(name = "arrmada-probe") {
            val result = ServerProbe.check(url)
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                setBusy(false)
                if (result.outcome == ServerProbe.Outcome.OK) {
                    saveAndOpen(url)
                } else {
                    showStatus(describe(result), isError = true)
                    // Le test peut se tromper (proxy qui filtre, page personnalisée) :
                    // on laisse toujours la possibilité de passer outre.
                    saveAnywayButton.isVisible = true
                    saveAnywayButton.requestFocus()
                }
            }
        }
    }

    private fun describe(result: ServerProbe.Result): String = when (result.outcome) {
        ServerProbe.Outcome.OK -> ""
        ServerProbe.Outcome.NOT_ARRMADA -> getString(R.string.probe_not_arrmada)
        ServerProbe.Outcome.HTTP_ERROR -> getString(R.string.probe_http_error, result.detail)
        ServerProbe.Outcome.UNKNOWN_HOST -> getString(R.string.probe_unknown_host, result.detail)
        ServerProbe.Outcome.TIMEOUT -> getString(R.string.probe_timeout)
        ServerProbe.Outcome.SSL -> getString(R.string.probe_ssl)
        ServerProbe.Outcome.UNREACHABLE -> getString(R.string.probe_unreachable, result.detail)
    }

    private fun saveAndOpen(url: String) {
        ServerConfig.save(this, url, selectedTvWidth())
        // CLEAR_TASK : l'ancien écran principal (ancien serveur) est fermé,
        // un nouveau démarre sur la nouvelle adresse.
        startActivity(
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        )
        finish()
    }

    private fun setBusy(isBusy: Boolean) {
        busy.isVisible = isBusy
        saveButton.isEnabled = !isBusy
        saveAnywayButton.isEnabled = !isBusy
    }

    private fun showStatus(message: String, isError: Boolean) {
        status.text = message
        status.setTextColor(getColor(if (isError) R.color.error else R.color.muted))
        status.isVisible = message.isNotEmpty()
    }
}
