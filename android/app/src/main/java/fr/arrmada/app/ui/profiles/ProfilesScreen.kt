package fr.arrmada.app.ui.profiles

import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import fr.arrmada.app.ui.components.tapToClick
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.Glow
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import fr.arrmada.app.data.FamilyProfile
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.theme.ArrColors

/** Couleur de l'avatar (« #4A9EFF ») ; illisible → bleu de l'appli. */
fun profileColor(hex: String): Color =
    runCatching { Color(android.graphics.Color.parseColor(hex)) }.getOrDefault(ArrColors.Accent)

/** Pastille ronde du profil : emoji, sinon initiale, sur sa couleur. */
@Composable
fun ProfileAvatar(profile: FamilyProfile, size: Dp, modifier: Modifier = Modifier) {
    Box(
        modifier.size(size).background(profileColor(profile.color), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            profile.emoji.ifBlank { profile.initial },
            fontSize = (size.value * 0.45f).sp,
            color = if (profile.emoji.isBlank()) ArrColors.Night else Color.Unspecified,
            textAlign = TextAlign.Center,
        )
    }
}

/**
 * « Qui regarde ? » (comme les services de streaming), au lancement et
 * depuis l'avatar du menu : chaque profil a sa rangée Reprendre, ses vus,
 * son « Pour toi » et ses demandes « Pour ce soir ». Avec le seul profil
 * « Famille », l'écran passe tout seul.
 */
@Composable
fun ProfilesScreen(
    repository: Repository,
    current: FamilyProfile?,
    onChosen: (FamilyProfile?) -> Unit,
    onHasProfiles: (Boolean) -> Unit = {}, // la maison a des profils (avatar dans le menu)
) {
    var profiles by remember { mutableStateOf<List<FamilyProfile>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        runCatching { repository.profiles() }
            .onSuccess { list ->
                val several = list.any { !it.isDefault }
                onHasProfiles(several)
                if (several) profiles = list else onChosen(null)
            }
            .onFailure { error = it.message ?: "Serveur injoignable" }
    }
    val list = profiles
    when {
        // Serveur injoignable : on continue avec le profil déjà choisi
        error != null -> MessageScreen("Profils indisponibles", error, "Continuer") { onChosen(current) }
        list == null -> MessageScreen("Chargement…")
        else -> ProfilesContent(list, current?.id, onChosen)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ProfilesContent(profiles: List<FamilyProfile>, currentId: Int?, onChosen: (FamilyProfile?) -> Unit) {
    val focus = remember { FocusRequester() }
    // Le profil en cours a le focus (« Famille » si aucun)
    val focused = profiles.firstOrNull { it.id == currentId } ?: profiles.firstOrNull { it.isDefault } ?: profiles.first()
    Column(
        Modifier.fillMaxSize().background(ArrColors.Night),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Qui regarde ?", style = MaterialTheme.typography.displayMedium)
        // Plusieurs lignes si l'écran est étroit (téléphone)
        FlowRow(
            Modifier.padding(top = 36.dp, start = 16.dp, end = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(28.dp, Alignment.CenterHorizontally),
            verticalArrangement = Arrangement.spacedBy(24.dp),
        ) {
            profiles.forEach { profile ->
                Column(Modifier.width(120.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Surface(
                        onClick = { onChosen(profile.takeIf { !it.isDefault }) },
                        modifier = Modifier.size(104.dp).then(if (profile == focused) Modifier.focusRequester(focus) else Modifier)
                            .tapToClick({ onChosen(profile.takeIf { !it.isDefault }) }),
                        shape = ClickableSurfaceDefaults.shape(CircleShape),
                        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.12f),
                        border = ClickableSurfaceDefaults.border(
                            focusedBorder = Border(BorderStroke(3.dp, ArrColors.Text), shape = CircleShape),
                        ),
                        glow = ClickableSurfaceDefaults.glow(focusedGlow = Glow(profileColor(profile.color).copy(alpha = 0.6f), 18.dp)),
                        colors = ClickableSurfaceDefaults.colors(containerColor = Color.Transparent, focusedContainerColor = Color.Transparent),
                    ) {
                        ProfileAvatar(profile, 104.dp)
                    }
                    Text(
                        profile.name,
                        style = MaterialTheme.typography.titleMedium,
                        color = if (profile.id == currentId || (currentId == null && profile.isDefault)) ArrColors.Text else ArrColors.TextSecondary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.padding(top = 12.dp),
                    )
                }
            }
        }
        Text(
            "Les profils se gèrent dans la web app (Réglages › Profils)",
            style = MaterialTheme.typography.labelMedium,
            color = ArrColors.TextSecondary,
            modifier = Modifier.padding(top = 40.dp),
        )
    }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
}
