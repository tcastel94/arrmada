package fr.arrmada.app.ui.player

import android.content.Context
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.core.graphics.drawable.toBitmap
import coil.imageLoader
import coil.request.ImageRequest
import coil.request.SuccessResult
import fr.arrmada.app.data.Trickplay
import fr.arrmada.app.data.TrickplayLogic

/**
 * Planches « trickplay » déjà téléchargées, partagées par toutes les
 * vignettes d'un écran (barre de lecture, chapitres du menu pause) : comme
 * un cache disque commun, une planche n'est demandée qu'une fois au serveur
 * même si dix chapitres y piochent leur image.
 */
@Stable
class TrickplayTiles {
    val bitmaps = mutableStateMapOf<Int, ImageBitmap>()
    private val loading = mutableSetOf<Int>() // planches en cours de téléchargement

    /** Télécharge la planche [tile] si elle manque (appelé sur le fil de l'interface). */
    suspend fun load(context: Context, info: Trickplay, tile: Int, absolute: (String?) -> String?) {
        if (bitmaps.containsKey(tile) || !loading.add(tile)) return
        try {
            val url = absolute(TrickplayLogic.tileUrl(info, tile)) ?: return
            val request = ImageRequest.Builder(context)
                .data(url)
                .allowHardware(false) // découpée ensuite : il faut une image en mémoire classique
                .build()
            val result = context.imageLoader.execute(request) as? SuccessResult ?: return
            bitmaps[tile] = result.drawable.toBitmap().asImageBitmap()
        } finally {
            loading.remove(tile)
        }
    }
}

/** Planches d'un aperçu, gardées le temps de l'écran. */
@Composable
fun rememberTrickplayTiles(info: Trickplay?): TrickplayTiles = remember(info?.url) { TrickplayTiles() }

/**
 * Image de l'instant [positionSeconds], découpée dans sa planche, qui
 * remplit [modifier]. [crop] : recadrée au centre pour remplir une case
 * 16:9 (film en 2,39:1 dans une vignette de chapitre) ; sinon étirée à la
 * case (dont la taille suit déjà le format de l'aperçu).
 * Rien n'est dessiné tant que la planche n'est pas arrivée (fond visible).
 */
@Composable
fun TrickplayImage(
    info: Trickplay,
    positionSeconds: Double,
    absolute: (String?) -> String?,
    tiles: TrickplayTiles,
    modifier: Modifier = Modifier,
    crop: Boolean = false,
) {
    val context = LocalContext.current
    val frame = TrickplayLogic.frame(info, positionSeconds) ?: return
    LaunchedEffect(info.url, frame.tile) { tiles.load(context, info, frame.tile, absolute) }
    val tile = tiles.bitmaps[frame.tile] ?: return
    Canvas(modifier) {
        // Planche plus petite que prévu (dernière planche, réglage modifié) : on ne lit pas hors de l'image
        if (frame.x + info.width > tile.width || frame.y + info.height > tile.height) return@Canvas
        var srcX = frame.x
        var srcY = frame.y
        var srcW = info.width
        var srcH = info.height
        if (crop && size.height > 0f) {
            // Recadrage centré : on garde la plus grande zone au format de la case
            val boxRatio = size.width / size.height
            val imageRatio = srcW.toFloat() / srcH
            if (imageRatio > boxRatio) {
                val w = (srcH * boxRatio).toInt().coerceIn(1, srcW)
                srcX += (srcW - w) / 2
                srcW = w
            } else {
                val h = (srcW / boxRatio).toInt().coerceIn(1, srcH)
                srcY += (srcH - h) / 2
                srcH = h
            }
        }
        drawImage(
            image = tile,
            srcOffset = IntOffset(srcX, srcY),
            srcSize = IntSize(srcW, srcH),
            dstSize = IntSize(size.width.toInt(), size.height.toInt()),
        )
    }
}

/**
 * Vignette de l'instant visé, au-dessus de la barre de lecture.
 *
 * Les planches sont téléchargées une fois (par le chargeur d'images de
 * l'appli, avec le jeton de la TV) puis gardées en mémoire le temps de la
 * lecture : avancer de 30 s en 30 s réutilise souvent la même planche.
 * Tant qu'une planche arrive, le cadre reste affiché (fond sombre).
 */
@Composable
fun TrickplayThumb(info: Trickplay, positionSeconds: Double, absolute: (String?) -> String?, width: Dp = 240.dp) {
    TrickplayLogic.frame(info, positionSeconds) ?: return
    val tiles = rememberTrickplayTiles(info)
    val height = width * info.height / info.width
    Box(
        Modifier
            .size(width, height)
            .clip(RoundedCornerShape(8.dp))
            .background(Color(0xFF111111))
            .border(2.dp, Color.White.copy(alpha = 0.85f), RoundedCornerShape(8.dp)),
    ) {
        TrickplayImage(info, positionSeconds, absolute, tiles, Modifier.fillMaxSize())
    }
}
