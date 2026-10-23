package fr.arrmada.app.ui.player

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.LaunchedEffect
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
 * Vignette de l'instant visé, au-dessus de la barre de lecture.
 *
 * Les planches sont téléchargées une fois (par le chargeur d'images de
 * l'appli, avec le jeton de la TV) puis gardées en mémoire le temps de la
 * lecture : avancer de 30 s en 30 s réutilise souvent la même planche.
 * Tant qu'une planche arrive, la vignette précédente reste affichée.
 */
@Composable
fun TrickplayThumb(info: Trickplay, positionSeconds: Double, absolute: (String?) -> String?, width: Dp = 240.dp) {
    val context = LocalContext.current
    val tiles = remember(info.url) { mutableStateMapOf<Int, ImageBitmap>() }
    val frame = TrickplayLogic.frame(info, positionSeconds) ?: return

    LaunchedEffect(info.url, frame.tile) {
        if (tiles.containsKey(frame.tile)) return@LaunchedEffect
        val url = absolute(TrickplayLogic.tileUrl(info, frame.tile)) ?: return@LaunchedEffect
        val request = ImageRequest.Builder(context)
            .data(url)
            .allowHardware(false) // découpée ensuite : il faut une image en mémoire classique
            .build()
        val result = context.imageLoader.execute(request) as? SuccessResult ?: return@LaunchedEffect
        tiles[frame.tile] = result.drawable.toBitmap().asImageBitmap()
    }

    // Planche de l'instant, sinon la dernière reçue (pas de trou pendant le téléchargement)
    val tile = tiles[frame.tile]
    val height = width * info.height / info.width
    Box(
        Modifier
            .size(width, height)
            .clip(RoundedCornerShape(8.dp))
            .background(Color(0xFF111111))
            .border(2.dp, Color.White.copy(alpha = 0.85f), RoundedCornerShape(8.dp)),
    ) {
        if (tile != null) {
            Canvas(Modifier.size(width, height)) {
                // Planche plus petite que prévu (dernière planche, réglage modifié) : on ne lit pas hors de l'image
                if (frame.x + info.width > tile.width || frame.y + info.height > tile.height) return@Canvas
                drawImage(
                    image = tile,
                    srcOffset = IntOffset(frame.x, frame.y),
                    srcSize = IntSize(info.width, info.height),
                    dstSize = IntSize(size.width.toInt(), size.height.toInt()),
                )
            }
        }
    }
}
