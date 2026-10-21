package fr.arrmada.app.data

/** Tableau de bord : chiffres de la médiathèque, stockage, téléchargements, services (home_data.py). */
object DashboardLogic {
    const val MAX_DOWNLOADS = 3
    const val MAX_SERVICES = 7

    data class Storage(val value: String, val hint: String, val usedPct: Int)

    /**
     * Volume de la médiathèque + remplissage des disques. Radarr et Sonarr
     * déclarent souvent le même disque (ex. /mnt/user) : on dédoublonne par
     * chemin, puis par couple (total, libre) pour un même montage vu sous
     * deux chemins (comme `df` qui listerait deux fois le même volume).
     */
    fun storage(dashboard: Dashboard): Storage {
        val paths = mutableSetOf<String>()
        val sizes = mutableSetOf<Pair<Long, Long>>()
        var total = 0L
        var free = 0L
        for (disk in dashboard.disks) {
            val key = disk.totalBytes to disk.freeBytes
            if (disk.path in paths || key in sizes || disk.totalBytes == 0L) continue
            paths += disk.path
            sizes += key
            total += disk.totalBytes
            free += disk.freeBytes
        }
        val used = if (total > 0) Math.round((total - free) * 100.0 / total).toInt() else 0
        return Storage(
            value = dashboard.stats.totalSize?.takeIf { it.isNotBlank() } ?: "—",
            hint = if (total > 0) "$used % · ${Fr.bytes(free.toDouble())} libres" else "médiathèque",
            usedPct = used,
        )
    }

    fun downloadsCount(dashboard: Dashboard): Int = dashboard.downloadsCount ?: dashboard.downloads.size

    /** « 3 412 films · 186 séries · 42,1 To · 3 téléchargements en cours ». */
    fun summary(dashboard: Dashboard): String {
        val stats = dashboard.stats
        val parts = mutableListOf(Fr.plural(stats.movies, "film"), Fr.plural(stats.series, "série"))
        stats.totalSize?.takeIf { it.isNotBlank() }?.let { parts += it }
        val downloads = downloadsCount(dashboard)
        if (downloads > 0) parts += Fr.plural(downloads, "téléchargement") + " en cours"
        return parts.joinToString(" · ")
    }

    /** « 60 % · 12 min · Radarr » sous un téléchargement. */
    fun downloadMeta(download: DashDownload): String = listOf(
        "${download.progress.toInt().coerceIn(0, 100)} %",
        Fr.timeLeft(download.timeleft),
        download.service.orEmpty().replaceFirstChar { it.uppercase() },
    ).filter { it.isNotBlank() }.joinToString(" · ")

    /** Services actifs d'abord, puis par nom. */
    fun services(dashboard: Dashboard): List<DashService> =
        dashboard.services.sortedWith(compareBy({ !it.isEnabled }, { it.name.lowercase() })).take(MAX_SERVICES)
}
