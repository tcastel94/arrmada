package fr.arrmada.app.ui.setup

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import fr.arrmada.app.BuildConfig
import fr.arrmada.app.R
import fr.arrmada.app.data.ApiException
import fr.arrmada.app.data.PairStart
import fr.arrmada.app.data.Prefs
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.ServerProbe
import fr.arrmada.app.data.ServerUrl
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Écran 1 : adresse du serveur ArrMada (la même que dans l'add-on Kodi,
 * port de l'API : 8420). Testée avant d'être enregistrée.
 */
@Composable
fun ServerScreen(prefs: Prefs, onSaved: () -> Unit) {
    var text by remember { mutableStateOf(prefs.serverUrl ?: "http://") }
    var status by remember { mutableStateOf<String?>(null) }
    var isError by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var allowForce by remember { mutableStateOf(false) }
    var fieldFocused by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val fieldFocus = remember { FocusRequester() }

    fun save(url: String) {
        prefs.serverUrl = url
        onSaved()
    }

    fun submit(test: Boolean) {
        val url = ServerUrl.normalize(text)
        if (url == null) {
            status = "Adresse invalide. Exemple : http://192.168.1.10:8420"
            isError = true
            return
        }
        text = url
        if (!test) return save(url)
        busy = true
        isError = false
        status = "Test de $url…"
        scope.launch {
            val result = withContext(Dispatchers.IO) { ServerProbe.check(url) }
            busy = false
            if (result.outcome == ServerProbe.Outcome.OK) {
                save(url)
            } else {
                isError = true
                allowForce = true
                status = when (result.outcome) {
                    ServerProbe.Outcome.NOT_ARRMADA -> "Ce serveur répond, mais ce n’est pas l’API ArrMada. Vérifie le port : 8420 par défaut (celui de l’add-on Kodi), pas celui de la web app."
                    ServerProbe.Outcome.HTTP_ERROR -> "Le serveur a répondu avec l’erreur HTTP ${result.detail}."
                    ServerProbe.Outcome.UNKNOWN_HOST -> "Nom inconnu sur le réseau : ${result.detail}. Essaie avec l’adresse IP."
                    ServerProbe.Outcome.TIMEOUT -> "Pas de réponse en 5 secondes. Vérifie l’IP, le port, et que la TV est sur le même réseau."
                    ServerProbe.Outcome.SSL -> "Certificat HTTPS refusé."
                    else -> "Connexion impossible : ${result.detail}"
                }
            }
        }
    }

    LaunchedEffect(Unit) { fieldFocus.requestFocus() }

    SetupFrame(title = "Connexion au serveur ArrMada") {
        Text(
            "Adresse du serveur ArrMada, la même que dans l’add-on Kodi. Exemple : http://192.168.1.10:8420",
            style = MaterialTheme.typography.bodyLarge,
            color = ArrColors.TextSecondary,
        )
        Spacer(Modifier.height(20.dp))
        BasicTextField(
            value = text,
            onValueChange = { text = it },
            singleLine = true,
            textStyle = MaterialTheme.typography.titleLarge.copy(color = ArrColors.Text),
            cursorBrush = SolidColor(ArrColors.Accent),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Go),
            keyboardActions = KeyboardActions(onGo = { submit(test = true) }),
            modifier = Modifier
                .fillMaxWidth()
                .focusRequester(fieldFocus)
                .onFocusChanged { fieldFocused = it.isFocused }
                .clip(RoundedCornerShape(6.dp))
                .background(ArrColors.Card)
                .border(BorderStroke(if (fieldFocused) 2.dp else 1.dp, if (fieldFocused) ArrColors.Accent else ArrColors.Track), RoundedCornerShape(6.dp))
                .padding(horizontal = 16.dp, vertical = 12.dp),
        )
        if (status != null) {
            Text(
                status!!,
                style = MaterialTheme.typography.bodyLarge,
                color = if (isError) ArrColors.Error else ArrColors.TextSecondary,
                modifier = Modifier.padding(top = 14.dp),
            )
        }
        Row(Modifier.padding(top = 24.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ArrButton(if (busy) "Test en cours…" else "Tester et enregistrer", { if (!busy) submit(test = true) }, primary = true)
            if (allowForce) ArrButton("Enregistrer sans tester", { submit(test = false) })
        }
    }
}

/**
 * Écran 2 : appairage, comme l'add-on Kodi. La TV affiche un code et un QR
 * code ; on les valide dans la web app (Réglages › Appareils) depuis son
 * téléphone ; le serveur remet alors un jeton à la TV.
 */
@Composable
fun PairScreen(prefs: Prefs, repository: Repository, onPaired: () -> Unit, onChangeServer: () -> Unit) {
    var start by remember { mutableStateOf<PairStart?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var attempt by remember { mutableIntStateOf(0) }
    var remaining by remember { mutableIntStateOf(0) }

    LaunchedEffect(attempt) {
        error = null
        start = null
        val pairing = try {
            repository.pairStart()
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
            return@LaunchedEffect
        }
        start = pairing
        remaining = pairing.expiresIn
        // Demande « est-ce validé ? » toutes les 3 s (comme l'add-on)
        while (remaining > 0) {
            delay(pairing.interval * 1000L)
            remaining -= pairing.interval
            try {
                val poll = repository.pairPoll(pairing.deviceCode)
                if (poll.status == "ok" && poll.token != null) {
                    prefs.token = poll.token
                    prefs.deviceName = poll.device?.name
                    onPaired()
                    return@LaunchedEffect
                }
            } catch (e: ApiException) {
                if (e.code == 410) break // code expiré
            } catch (_: Exception) {
                // coupure réseau passagère : on réessaie au tour suivant
            }
        }
        error = "Le code a expiré."
    }

    PairContent(
        pairing = start,
        error = error,
        remaining = remaining,
        qrUrl = start?.let { (prefs.serverUrl ?: "") + it.qrUrl },
        onNewCode = { attempt++ },
        onChangeServer = onChangeServer,
    )
}

/** Affichage de l'appairage (séparé de l'attente pour les captures d'écran de test). */
@Composable
fun PairContent(
    pairing: PairStart?,
    error: String?,
    remaining: Int,
    qrUrl: String?,
    onNewCode: () -> Unit,
    onChangeServer: () -> Unit,
) {
    SetupFrame(title = "Appairer cette TV") {
        when {
            error != null -> {
                Text(error, style = MaterialTheme.typography.bodyLarge, color = ArrColors.Error)
                Row(Modifier.padding(top = 24.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    ArrButton("Nouveau code", onNewCode, primary = true)
                    ArrButton("Changer de serveur", onChangeServer)
                }
            }
            pairing == null -> Text("Demande d’un code…", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary)
            else -> Row(horizontalArrangement = Arrangement.spacedBy(32.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        "Sur ton téléphone, scanne le QR code, ou ouvre la web app ArrMada › Réglages › Appareils et saisis ce code :",
                        style = MaterialTheme.typography.bodyLarge,
                        color = ArrColors.TextSecondary,
                    )
                    Row(Modifier.padding(vertical = 18.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        pairing.userCode.forEach { char ->
                            Box(
                                Modifier.size(width = 44.dp, height = 56.dp).clip(RoundedCornerShape(8.dp)).background(ArrColors.Card),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(char.toString(), style = MaterialTheme.typography.displayMedium, color = ArrColors.AccentText)
                            }
                        }
                    }
                    Text(
                        "Code valable encore ${remaining / 60} min ${"%02d".format(remaining % 60)} s",
                        style = MaterialTheme.typography.labelMedium,
                        color = ArrColors.TextSecondary,
                    )
                    Row(Modifier.padding(top = 20.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        ArrButton("Nouveau code", onNewCode)
                        ArrButton("Changer de serveur", onChangeServer)
                    }
                }
                Box(Modifier.size(200.dp).clip(RoundedCornerShape(12.dp)).background(androidx.compose.ui.graphics.Color.White).padding(8.dp)) {
                    AsyncImage(model = qrUrl, contentDescription = "QR code d’appairage", modifier = Modifier.fillMaxSize())
                }
            }
        }
    }
}

/** Cadre commun des écrans de mise en route : logo, titre, contenu, version. */
@Composable
private fun SetupFrame(title: String, content: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize().background(ArrColors.Night).padding(horizontal = 96.dp, vertical = 48.dp)) {
        Column(Modifier.align(Alignment.CenterStart).width(720.dp)) {
            androidx.compose.foundation.Image(
                painter = painterResource(R.drawable.ic_logo),
                contentDescription = null,
                modifier = Modifier.size(56.dp),
            )
            Text(title, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(top = 12.dp, bottom = 12.dp))
            content()
        }
        Text(
            "ArrMada Android ${BuildConfig.VERSION_NAME}",
            style = MaterialTheme.typography.labelMedium,
            color = ArrColors.TextSecondary,
            modifier = Modifier.align(Alignment.BottomStart),
        )
    }
}
