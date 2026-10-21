package fr.arrmada.app.ui.intro

import androidx.compose.ui.Alignment
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.annotation.DrawableRes
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.Easing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.R
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.launch
import kotlin.math.PI
import kotlin.math.cos

/** Durée de l'intro, puis du fondu de sortie (comme l'add-on : 2,4 s + 0,52 s). */
const val INTRO_MS = 2_400f
private const val EXIT_MS = 520

/**
 * Intro animée de l'add-on (script-arrmada-home.xml), au lancement de
 * l'appli : les deux jambes du « A » glissent en place, deux ondes partent
 * du logo, le bouton lecture surgit avec un rebond, un reflet balaie le
 * logo, puis le nom et la devise montent. Une touche de la télécommande la
 * passe. Mêmes textures, positions et minutages (pixels du skin ÷ 2).
 *
 * Tout est calculé à partir d'une seule horloge `t` (millisecondes depuis le
 * début), comme une timeline de montage : chaque élément lit sa position et
 * son opacité à l'instant t.
 */
@Composable
fun IntroAnimation(version: String, skip: Boolean, onDone: () -> Unit) {
    val clock = remember { Animatable(0f) }
    val exit = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        clock.animateTo(INTRO_MS, tween(INTRO_MS.toInt(), easing = LinearEasing))
        exit.animateTo(1f, tween(EXIT_MS, easing = FastOutSlowInEasing))
        onDone()
    }
    // Touche pressée : sortie immédiate (le fondu reste, pour ne pas « couper »)
    LaunchedEffect(skip) {
        if (skip) {
            launch { clock.stop() }
            exit.animateTo(1f, tween(EXIT_MS, easing = FastOutSlowInEasing))
            onDone()
        }
    }
    Box(
        Modifier.fillMaxSize().graphicsLayer {
            alpha = 1f - exit.value
            val s = 1f + 0.12f * exit.value // zoom 100 → 112 % en sortant
            scaleX = s
            scaleY = s
        },
    ) {
        // Composée pour un écran 960 × 540 (la TV) : ramenée à l'écran du
        // téléphone ou de la tablette, centrée, sans rien déformer
        BoxWithConstraints(Modifier.fillMaxSize().background(ArrColors.Night), contentAlignment = Alignment.Center) {
            val scale = minOf(maxWidth / 960.dp, maxHeight / 540.dp)
            Box(Modifier.requiredSize(960.dp, 540.dp).graphicsLayer { scaleX = scale; scaleY = scale }) {
                IntroFrame(clock.value, version)
            }
        }
    }
}

// ── Courbes (équivalents des « tween » de Kodi) ──
private val CubicOut = CubicBezierEasing(0.33f, 1f, 0.68f, 1f)
private val QuadOut = CubicBezierEasing(0.5f, 1f, 0.89f, 1f)
private val SineInOut = Easing { x -> (-(cos(PI * x) - 1) / 2).toFloat() }
private val BackOut = Easing { x ->
    val c1 = 1.70158f
    val c3 = c1 + 1f
    val u = x - 1f
    1f + c3 * u * u * u + c1 * u * u
}

/** Avancement 0 → 1 d'une étape qui commence à [delay] ms et dure [duration] ms. */
private fun step(t: Float, delay: Int, duration: Int, easing: Easing = LinearEasing): Float =
    easing.transform(((t - delay) / duration).coerceIn(0f, 1f))

/** Une image de l'intro à l'instant [t] (ms) — publique pour les captures d'écran. */
@Composable
fun IntroFrame(t: Float, version: String) {
    Box(Modifier.fillMaxSize().background(ArrColors.Night)) {
        // Halo d'ambiance (haut) et second halo cyan (bas à gauche)
        Layer(R.drawable.blob, Color(0x664A9EFF), 180.dp, (-60).dp, 600.dp, 550.dp) {
            alpha = step(t, 0, 1400)
            val z = 0.7f + 0.3f * step(t, 0, 1800, CubicOut)
            scaleX = z
            scaleY = z
        }
        Layer(R.drawable.blob, Color(0x3322E0EE), (-100).dp, 260.dp, 550.dp, 450.dp) { alpha = step(t, 300, 1600, SineInOut) }

        // Deux ondes qui partent du logo
        Layer(R.drawable.ring_circle, Color(0xFF4A9EFF), 375.dp, 110.dp, 210.dp, 210.dp) {
            val z = 0.35f + (1.9f - 0.35f) * step(t, 620, 1300, QuadOut)
            scaleX = z
            scaleY = z
            alpha = 0.9f * step(t, 620, 120) * (1f - step(t, 760, 1100))
        }
        Layer(R.drawable.ring_circle, Color(0x9922E0EE), 375.dp, 110.dp, 210.dp, 210.dp) {
            val z = 0.35f + (1.5f - 0.35f) * step(t, 820, 1300, QuadOut)
            scaleX = z
            scaleY = z
            alpha = 0.8f * step(t, 820, 120) * (1f - step(t, 960, 1100))
        }

        // Halo derrière le logo, qui « respire »
        Layer(R.drawable.blob, Color(0x994A9EFF), 350.dp, 85.dp, 260.dp, 260.dp) {
            val pulse = if (t > 1260f) 1f - 0.35f * ((1 - cos(2 * PI * (t - 1260f) / 2400f)) / 2).toFloat() else 1f
            alpha = step(t, 560, 700, SineInOut) * pulse
        }

        // Les deux jambes du « A » glissent en place
        Layer(R.drawable.brand_leg_left, null, 390.dp, 125.dp, 180.dp, 180.dp) {
            val p = step(t, 120, 620, CubicOut)
            translationX = (-55).dp.toPx() * (1 - p)
            translationY = 45.dp.toPx() * (1 - p)
            alpha = step(t, 120, 300)
        }
        Layer(R.drawable.brand_leg_right, null, 390.dp, 125.dp, 180.dp, 180.dp) {
            val p = step(t, 260, 620, CubicOut)
            translationX = 55.dp.toPx() * (1 - p)
            translationY = 45.dp.toPx() * (1 - p)
            alpha = step(t, 260, 300)
        }
        // Le bouton lecture surgit avec un rebond (centré sur le triangle)
        Layer(R.drawable.brand_play, null, 390.dp, 125.dp, 180.dp, 180.dp) {
            val z = step(t, 700, 520, BackOut)
            scaleX = z
            scaleY = z
            transformOrigin = TransformOrigin(0.53f, 0.656f)
        }

        // Reflet qui balaie le logo
        Layer(R.drawable.sweep, Color(0x4DFFFFFF), 345.dp, 115.dp, 85.dp, 200.dp) {
            translationX = 190.dp.toPx() * step(t, 1000, 700, SineInOut)
            alpha = step(t, 1000, 200) * (1f - step(t, 1400, 300))
        }

        // Nom et devise
        Layer(R.drawable.brand_wordmark, null, 317.dp, 330.dp, 326.dp, 54.dp) {
            val p = step(t, 980, 700, CubicOut)
            translationY = 23.dp.toPx() * (1 - p)
            alpha = p
        }
        Layer(R.drawable.brand_tagline, null, 378.5.dp, 400.dp, 203.dp, 12.dp) {
            val p = step(t, 1280, 600, CubicOut)
            translationY = 12.dp.toPx() * (1 - p)
            alpha = p
        }
        Text(
            "v$version",
            style = MaterialTheme.typography.labelSmall,
            color = Color(0x66C9D3E0),
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().offset(y = 500.dp).graphicsLayer { alpha = step(t, 1500, 600) },
        )
    }
}

/** Une texture du skin placée en dp, teintée (colordiffuse) et animée par [layer]. */
@Composable
private fun Layer(
    @DrawableRes id: Int,
    tint: Color?,
    x: Dp,
    y: Dp,
    width: Dp,
    height: Dp,
    layer: androidx.compose.ui.graphics.GraphicsLayerScope.() -> Unit,
) {
    Image(
        painterResource(id),
        contentDescription = null,
        contentScale = ContentScale.FillBounds,
        colorFilter = tint?.let { ColorFilter.tint(it, BlendMode.Modulate) },
        modifier = Modifier.offset(x, y).size(width, height).graphicsLayer(layer),
    )
}
