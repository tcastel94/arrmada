package fr.arrmada.app.ui.player

import androidx.media3.common.PlaybackException
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Quand le lecteur retente en remux (conversion par Jellyfin) après un échec en direct. */
class RemuxRetryTest {
    @Test
    fun containerErrorsAlwaysRetry() {
        assertTrue(remuxRetry(PlaybackException.ERROR_CODE_PARSING_CONTAINER_UNSUPPORTED, "m2ts"))
        assertTrue(remuxRetry(PlaybackException.ERROR_CODE_DECODING_FORMAT_UNSUPPORTED, "mkv"))
    }

    @Test
    fun sourceErrorRetriesOnlyForAvi() {
        // Vieil AVI (XviD + MP3) : « Source error » → conversion par Jellyfin
        assertTrue(remuxRetry(PlaybackException.ERROR_CODE_IO_UNSPECIFIED, "avi"))
        assertTrue(remuxRetry(PlaybackException.ERROR_CODE_IO_UNSPECIFIED, "AVI"))
        // Ailleurs, c'est d'abord le réseau : un remux n'y changerait rien
        assertFalse(remuxRetry(PlaybackException.ERROR_CODE_IO_UNSPECIFIED, "mkv"))
        assertFalse(remuxRetry(PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_FAILED, "avi"))
    }
}
