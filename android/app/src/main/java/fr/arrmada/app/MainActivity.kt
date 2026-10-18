package fr.arrmada.app

import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.graphics.Bitmap
import android.net.Uri
import android.net.http.SslError
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.RenderProcessGoneDetail
import android.webkit.SslErrorHandler
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.core.view.isVisible
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature

/**
 * Écran principal : l'interface web du serveur ArrMada dans un « WebView »
 * (le moteur de Chrome intégré à Android, sans barre d'adresse).
 *
 * Analogie infra : l'appli est un reverse proxy embarqué. Le serveur fait tout
 * le travail ; l'appli ajoute seulement ce qu'un navigateur ne sait pas faire
 * proprement sur un téléphone ou une TV :
 *  - touche Retour : ferme la fenêtre ouverte, sinon page précédente, sinon menu ;
 *  - Android TV : navigation aux flèches de la télécommande (assets/tv-navigation.js) ;
 *  - serveur injoignable : écran natif « Réessayer / Changer de serveur » ;
 *  - liens externes (TMDB, YouTube…) : ouverts dans le navigateur de l'appareil.
 */
class MainActivity : ComponentActivity() {

    private lateinit var webView: WebView
    private lateinit var progress: ProgressBar
    private lateinit var errorPanel: View
    private lateinit var errorDetail: TextView

    private lateinit var serverUrl: String
    private lateinit var pageScript: String
    private var isTv = false

    // Vrai quand le chargement de la page principale a échoué (panneau d'erreur affiché).
    private var mainFrameFailed = false

    // Vrai si le moteur du WebView a planté et été détruit (voir onRenderProcessGone).
    private var webViewDead = false

    // Vidéo en plein écran (bande-annonce YouTube).
    private var fullscreenView: View? = null
    private var fullscreenCallback: WebChromeClient.CustomViewCallback? = null

    // Lu depuis le fil JavaScript du WebView, écrit par le fil de l'écran : @Volatile.
    @Volatile
    private var keyboardVisible = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val savedUrl = ServerConfig.url(this)
        if (savedUrl == null) {
            // Premier lancement : pas encore d'adresse de serveur.
            startActivity(Intent(this, SetupActivity::class.java))
            finish()
            return
        }
        serverUrl = savedUrl
        isTv = ServerConfig.isTv(this)
        pageScript = buildPageScript()

        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContentView(R.layout.activity_main)
        applySystemBarPadding(findViewById(R.id.root)) { visible -> keyboardVisible = visible }

        webView = findViewById(R.id.webview)
        progress = findViewById(R.id.progress)
        errorPanel = findViewById(R.id.error_panel)
        errorDetail = findViewById(R.id.error_detail)
        findViewById<View>(R.id.retry).setOnClickListener { reload() }
        findViewById<View>(R.id.change_server).setOnClickListener { openSetup() }

        setupWebView()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = handleBack()
        })

        // Après un redémarrage de l'appli par Android (mémoire), on reprend
        // l'historique de navigation ; sinon on ouvre la page d'accueil.
        if (savedInstanceState == null || webView.restoreState(savedInstanceState) == null) {
            webView.loadUrl(serverUrl)
        }
    }

    /**
     * Scripts ajoutés à chaque page du serveur : le pont Retour (tous les
     * appareils) et, sur TV, la navigation à la télécommande avec la largeur
     * d'affichage choisie dans l'écran de connexion.
     */
    private fun buildPageScript(): String {
        val bridge = assets.open("arrmada-bridge.js").bufferedReader().use { it.readText() }
        if (!isTv) return bridge
        val tv = assets.open("tv-navigation.js").bufferedReader().use { it.readText() }
            .replace("__ARRMADA_TV_WIDTH__", ServerConfig.tvWidth(this).toString())
        return bridge + "\n" + tv
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        // Inspection à distance (chrome://inspect) seulement dans l'APK de test.
        val debuggable = (applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0
        WebView.setWebContentsDebuggingEnabled(debuggable)

        webView.setBackgroundColor(getColor(R.color.night)) // pas d'éclair blanc au démarrage
        webView.settings.apply {
            javaScriptEnabled = true // la web app est une appli JavaScript
            domStorageEnabled = true // localStorage : session de connexion ArrMada
            useWideViewPort = true // respecte la largeur demandée par la page (TV)
            loadWithOverviewMode = true
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
            // Signature ajoutée à l'identifiant du navigateur : la web app
            // pourra un jour adapter son affichage à l'appli.
            val device = if (isTv) "TV" else "Mobile"
            userAgentString = "$userAgentString ArrMadaAndroid/${BuildConfig.VERSION_NAME} ($device)"
        }
        CookieManager.getInstance().setAcceptCookie(true)

        if (isTv) webView.addJavascriptInterface(TvBridge(), "ArrMadaAndroid")

        // Injection des scripts AVANT le code de la page (la largeur TV est
        // appliquée dès le premier affichage). Repli sur onPageFinished si le
        // WebView de l'appareil est trop ancien.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            try {
                WebViewCompat.addDocumentStartJavaScript(
                    webView, pageScript, setOf(ServerUrl.origin(serverUrl))
                )
            } catch (e: IllegalArgumentException) {
                // Origine refusée par le WebView : le repli suffit.
            }
        }

        webView.webViewClient = ArrMadaWebViewClient()
        webView.webChromeClient = ArrMadaChromeClient()
    }

    // ─── Touche Retour et menu ───────────────────────────────────────────────

    private fun handleBack() {
        if (fullscreenView != null) {
            exitFullscreen()
            return
        }
        if (errorPanel.isVisible || webViewDead) {
            showAppMenu()
            return
        }
        // 1. Une fenêtre est ouverte dans la page (modale, menu) ? On la ferme.
        // 2. Sinon page précédente. 3. Sinon (première page) : menu de l'appli.
        webView.evaluateJavascript("window.__arrmadaBack ? window.__arrmadaBack() : false") { closed ->
            when {
                closed == "true" -> Unit
                webView.canGoBack() -> webView.goBack()
                else -> showAppMenu()
            }
        }
    }

    private fun showAppMenu() {
        val items = arrayOf(
            getString(R.string.menu_reload),
            getString(R.string.menu_change_server),
            getString(R.string.menu_quit),
        )
        AlertDialog.Builder(this)
            .setTitle(R.string.app_name)
            .setItems(items) { _, which ->
                when (which) {
                    0 -> reload()
                    1 -> openSetup()
                    else -> finish()
                }
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    /** Touche Menu de la télécommande (≡) : ouvre le menu de l'appli. */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode == KeyEvent.KEYCODE_MENU && ::webView.isInitialized) {
            if (event.action == KeyEvent.ACTION_UP) showAppMenu()
            return true
        }
        return super.dispatchKeyEvent(event)
    }

    private fun openSetup() {
        startActivity(Intent(this, SetupActivity::class.java))
    }

    private fun reload() {
        if (webViewDead) {
            recreate()
            return
        }
        errorPanel.isVisible = false
        webView.isVisible = true
        // Après un échec, webView.url peut être vide ou une page interne :
        // on recharge l'adresse courante si elle est sur le serveur, sinon l'accueil.
        val current = webView.url?.takeIf { ServerUrl.sameHost(serverUrl, it) }
        webView.loadUrl(current ?: serverUrl)
    }

    private fun showError(detail: String?) {
        mainFrameFailed = true
        progress.isVisible = false
        webView.isVisible = false
        errorDetail.text = getString(R.string.error_detail, serverUrl, detail ?: "")
        errorPanel.isVisible = true
        findViewById<View>(R.id.retry).requestFocus() // focus télécommande
    }

    private fun openExternally(uri: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
        } catch (e: ActivityNotFoundException) {
            // Fréquent sur Android TV : aucun navigateur installé.
            Toast.makeText(this, R.string.no_browser, Toast.LENGTH_LONG).show()
        }
    }

    // ─── Plein écran vidéo (bandes-annonces) ─────────────────────────────────

    private fun enterFullscreen(view: View, callback: WebChromeClient.CustomViewCallback) {
        if (fullscreenView != null) {
            callback.onCustomViewHidden()
            return
        }
        fullscreenView = view
        fullscreenCallback = callback
        (window.decorView as FrameLayout).addView(
            view,
            FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        )
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    private fun exitFullscreen() {
        val view = fullscreenView ?: return
        (window.decorView as FrameLayout).removeView(view)
        fullscreenView = null
        WindowInsetsControllerCompat(window, window.decorView).show(WindowInsetsCompat.Type.systemBars())
        fullscreenCallback?.onCustomViewHidden()
        fullscreenCallback = null
    }

    // ─── Cycle de vie ────────────────────────────────────────────────────────

    override fun onResume() {
        super.onResume()
        if (::webView.isInitialized && !webViewDead) webView.onResume()
    }

    override fun onPause() {
        if (::webView.isInitialized && !webViewDead) {
            webView.onPause()
            // Écrit les cookies sur disque : la session survit à un arrêt brutal.
            CookieManager.getInstance().flush()
        }
        super.onPause()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        if (::webView.isInitialized && !webViewDead) webView.saveState(outState)
    }

    override fun onDestroy() {
        if (::webView.isInitialized && !webViewDead) {
            webView.stopLoading()
            webView.destroy()
        }
        super.onDestroy()
    }

    // ─── Comportement du WebView ─────────────────────────────────────────────

    private inner class ArrMadaWebViewClient : WebViewClient() {

        /** Lien cliqué : reste dans l'appli s'il vise le serveur, sinon navigateur. */
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            if (!request.isForMainFrame) return false // iframe (lecteur YouTube) : on laisse faire
            val uri = request.url
            val isWeb = uri.scheme == "http" || uri.scheme == "https"
            if (isWeb && ServerUrl.sameHost(serverUrl, uri.toString())) return false
            openExternally(uri)
            return true
        }

        override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
            mainFrameFailed = false
            progress.isVisible = true
        }

        override fun onPageFinished(view: WebView, url: String?) {
            progress.isVisible = false
            if (mainFrameFailed) return
            errorPanel.isVisible = false
            view.isVisible = true
            // Repli (et filet de sécurité) : les scripts se protègent contre
            // une double exécution, on peut donc les rejouer sans risque.
            if (url != null && ServerUrl.sameHost(serverUrl, url)) {
                view.evaluateJavascript(pageScript, null)
            }
            if (isTv && !view.hasFocus()) view.requestFocus()
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            // Une image ou un appel d'API en échec ne doit pas masquer la page.
            if (request.isForMainFrame) showError(error.description?.toString())
        }

        override fun onReceivedHttpError(
            view: WebView,
            request: WebResourceRequest,
            errorResponse: WebResourceResponse,
        ) {
            // 502/503/504 : reverse proxy ou conteneur en train de redémarrer.
            if (request.isForMainFrame && errorResponse.statusCode in 502..504) {
                showError(getString(R.string.error_http, errorResponse.statusCode))
            }
        }

        /**
         * Certificat HTTPS invalide : on REFUSE toujours (handler.cancel). Accepter
         * en silence ouvrirait la porte à une interception. Solution propre :
         * installer la CA du homelab dans Android (voir network_security_config.xml).
         */
        override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
            handler.cancel()
            if (ServerUrl.sameHost(serverUrl, error.url)) showError(getString(R.string.error_ssl))
        }

        /**
         * Le moteur du WebView a planté ou a été tué par Android faute de
         * mémoire (cas connu sur les boîtiers TV). Sans ce code, toute l'appli
         * plante ; ici on jette le WebView et on reconstruit l'écran.
         */
        override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
            webViewDead = true
            (view.parent as? ViewGroup)?.removeView(view)
            view.destroy()
            recreate()
            return true
        }
    }

    private inner class ArrMadaChromeClient : WebChromeClient() {
        override fun onProgressChanged(view: WebView, newProgress: Int) {
            progress.progress = newProgress
        }

        override fun onShowCustomView(view: View, callback: CustomViewCallback) {
            enterFullscreen(view, callback)
        }

        override fun onHideCustomView() {
            exitFullscreen()
        }
    }

    /**
     * Fonctions appelables depuis la page web (TV uniquement), sous le nom
     * window.ArrMadaAndroid. Volontairement minimales : la page ne peut rien
     * faire d'autre que demander le clavier à l'écran.
     */
    private inner class TvBridge {
        @JavascriptInterface
        fun isKeyboardVisible(): Boolean = keyboardVisible

        /** Sur TV, mettre le focus dans un champ n'ouvre pas le clavier : on le demande. */
        @JavascriptInterface
        fun showKeyboard() {
            runOnUiThread {
                if (webViewDead) return@runOnUiThread
                webView.requestFocus()
                getSystemService(InputMethodManager::class.java)?.showSoftInput(webView, 0)
            }
        }
    }
}
