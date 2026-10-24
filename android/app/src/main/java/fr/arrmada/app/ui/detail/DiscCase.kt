package fr.arrmada.app.ui.detail

import androidx.annotation.DrawableRes
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.Easing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import fr.arrmada.app.R
import fr.arrmada.app.data.CaseLogic
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.Motion
import kotlinx.coroutines.launch

/**
 * Boîtier du film et son disque qui en sort en roulant, repris de l'add-on
 * Kodi (fenêtre script-arrmada-detail.xml) : mêmes textures, mêmes
 * positions (pixels du skin 1080p divisés par deux), mêmes animations.
 *
 *  - Boîtier : Blu-ray bleu, 4K ULTRA HD noir, DVD, ou transparent quand le
 *    fichier n'est pas encore là. La jaquette (affiche) est dessous, le
 *    plastique (texture PNG) par-dessus.
 *  - Disque : rond imprimé de fanart.tv (« discart ») ou, à défaut,
 *    l'affiche découpée en anneau. Il glisse de 120 dp vers la gauche avec
 *    un petit rebond, en roulant (79° : la distance parcourue sur sa
 *    circonférence, sans glisser), puis tourne lentement (un tour en 12 s).
 *
 * L'ensemble occupe 196 × 276 dp ; le disque déborde à gauche une fois sorti.
 */
@Composable
fun DiscCase(
    format: CaseLogic.Format,
    poster: String?,
    discart: String?,
    title: String,
    modifier: Modifier = Modifier,
) {
    Box(modifier.size(CASE_WIDTH, 276.dp)) {
        if (poster != null || discart != null) {
            Disc(poster, discart, title, Modifier.offset(11.dp, 45.5.dp))
        }
        Case(format, poster, title)
    }
}

private val CASE_WIDTH = 196.dp
private val DISC_SIZE = 174.dp

// Distance de sortie et angle de roulement correspondant (240 px / rayon 174 px)
private const val SLIDE_DP = -120f
private const val ROLL_DEGREES = 79f

/** Easing « back, out » de Kodi : dépasse un peu la cible puis revient. */
private val BackOut = Easing { t ->
    val c1 = 1.70158f
    val c3 = c1 + 1f
    val u = t - 1f
    1f + c3 * u * u * u + c1 * u * u
}

/** Le disque : ombre, rond imprimé ou affiche en anneau, moyeu, tranche, reflet. */
@Composable
private fun Disc(poster: String?, discart: String?, title: String, modifier: Modifier) {
    // 0 → 1 : sortie du boîtier (après 450 ms, le temps que la fiche s'affiche)
    val out = remember { Animatable(if (Motion.enabled) 0f else 1f) }
    // Rotation lente continue (degrés)
    val spin = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        if (!Motion.enabled) return@LaunchedEffect
        launch { out.animateTo(1f, tween(durationMillis = 950, delayMillis = 450, easing = BackOut)) }
        launch {
            spin.animateTo(
                360f,
                infiniteRepeatable(tween(durationMillis = 12_000, easing = LinearEasing), RepeatMode.Restart),
            )
        }
    }

    Box(
        modifier
            .size(DISC_SIZE)
            .graphicsLayer { translationX = SLIDE_DP * out.value * density },
    ) {
        // Ombre portée (texture du skin teintée en noir 70 %)
        Tinted(R.drawable.disc_shadow, Color(0xB3000000), Modifier.offset((-10).dp, 2.dp).size(194.dp))

        // Partie qui tourne (sens inverse des aiguilles d'une montre : le
        // disque roule vers la gauche)
        val rotation = Modifier.graphicsLayer { rotationZ = -(ROLL_DEGREES * out.value + spin.value) }
        if (discart != null) {
            AsyncImage(
                model = discart,
                contentDescription = title,
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize().then(rotation),
            )
        } else {
            Box(Modifier.fillMaxSize().then(rotation)) {
                // Affiche recadrée au centre, découpée en anneau (zone imprimée)
                AsyncImage(
                    model = poster,
                    contentDescription = title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize().clip(RingShape),
                )
                // Moyeu en plastique transparent et tranche argentée
                Tinted(R.drawable.disc_hub, Color(0xD9DCE6F2), Modifier.fillMaxSize())
                Tinted(R.drawable.disc_edge, Color(0x99FFFFFF), Modifier.fillMaxSize())
            }
        }
        // Reflet de lumière : immobile pendant que le disque tourne
        Image(painterResource(R.drawable.disc_shine), null, Modifier.fillMaxSize())
    }
}

/** Le boîtier : jaquette dessous, plastique par-dessus, bandeau du format. */
@Composable
private fun Case(format: CaseLogic.Format, poster: String?, title: String) {
    val case = when (format) {
        CaseLogic.Format.UHD -> R.drawable.case_uhd
        CaseLogic.Format.BLURAY -> R.drawable.case_bluray
        CaseLogic.Format.DVD -> R.drawable.case_dvd
        CaseLogic.Format.CLEAR -> R.drawable.case_clear
    }
    // Jaquette : place laissée par la texture (bandeau de 28 dp pour le Blu-ray)
    val (top, coverTop, coverHeight, height) = when (format) {
        CaseLogic.Format.UHD, CaseLogic.Format.BLURAY -> listOf(0.dp, 32.dp, 229.dp, 265.dp)
        CaseLogic.Format.DVD -> listOf((-5.5).dp, 4.dp, 268.dp, 276.dp)
        CaseLogic.Format.CLEAR -> listOf(0.dp, 4.dp, 257.dp, 265.dp)
    }
    Box(
        Modifier
            .offset(y = top)
            .size(CASE_WIDTH, height)
            // Halo sombre autour du boîtier (glow.png de l'add-on)
            .shadow(18.dp, RoundedCornerShape(6.dp), clip = false, ambientColor = Color.Black, spotColor = Color.Black),
    ) {
        ArtImage(poster, title, Modifier.offset(4.dp, coverTop).size(188.dp, coverHeight))
        Image(painterResource(case), null, Modifier.fillMaxSize(), contentScale = ContentScale.FillBounds)
        when (format) {
            CaseLogic.Format.BLURAY -> BandLabel(format.label.orEmpty(), Modifier.offset(4.dp, 4.dp).size(188.dp, 28.dp), TextAlign.Center)
            CaseLogic.Format.UHD -> {
                BandLabel(format.label.orEmpty(), Modifier.offset(12.dp, 4.dp).size(115.dp, 28.dp), TextAlign.Start)
                BandLabel("Blu-ray Disc", Modifier.offset(115.dp, 4.dp).size(71.dp, 28.dp), TextAlign.End, small = true)
            }
            else -> Unit
        }
    }
}

@Composable
private fun BandLabel(text: String, modifier: Modifier, align: TextAlign, small: Boolean = false) {
    // Toute la largeur du bandeau, pour que l'alignement (centre, gauche, droite) s'applique
    Box(modifier, contentAlignment = Alignment.CenterStart) {
        Text(
            text,
            style = MaterialTheme.typography.labelLarge.copy(
                fontSize = if (small) 10.sp else 15.sp,
                fontWeight = if (small) FontWeight.Normal else FontWeight.Bold,
            ),
            color = if (small) Color(0xE6FFFFFF) else Color.White,
            textAlign = align,
            maxLines = 1,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

/** Texture du skin teintée (équivalent du « colordiffuse » de Kodi). */
@Composable
private fun Tinted(@DrawableRes id: Int, tint: Color, modifier: Modifier) {
    Image(painterResource(id), null, modifier, colorFilter = ColorFilter.tint(tint, BlendMode.Modulate))
}

/**
 * Anneau imprimé d'un disque : entre 38 % du rayon (bord du moyeu) et le bord.
 * Remplissage « pair-impair » : le cercle intérieur fait un trou dans
 * l'extérieur (comme le masque disc-mask.png de l'add-on).
 */
private object RingShape : Shape {
    override fun createOutline(size: Size, layoutDirection: LayoutDirection, density: Density): Outline {
        val r = size.minDimension / 2
        val center = Offset(size.width / 2, size.height / 2)
        val path = Path().apply {
            fillType = PathFillType.EvenOdd
            addOval(Rect(center, r))
            addOval(Rect(center, r * 0.38f))
        }
        return Outline.Generic(path)
    }
}
