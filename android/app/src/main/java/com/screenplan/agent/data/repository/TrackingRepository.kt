package com.screenplan.agent.data.repository

import com.screenplan.agent.data.local.ActivityDao
import com.screenplan.agent.data.local.ConfigManager
import com.screenplan.agent.model.ActivityEntry
import com.screenplan.agent.model.AppCategory
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TrackingRepository @Inject constructor(
    private val activityDao: ActivityDao,
    private val configManager: ConfigManager
) {
    private val dateFormatter = DateTimeFormatter.ISO_LOCAL_DATE
    private val timestampFormatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME

    fun classifyApp(packageName: String, appName: String, config: com.screenplan.agent.data.local.TrackerConfig? = null): AppCategory {
        val cfg = config ?: configManager.getDefaultConfig()
        val nameLower = appName.lowercase()
        val pkgLower = packageName.lowercase()

        for (learnApp in cfg.learningApps) {
            val la = learnApp.lowercase()
            if (pkgLower.contains(la) || nameLower.contains(la) || la in pkgLower || la in nameLower) {
                return AppCategory.LEARNING
            }
        }

        for (entApp in cfg.entertainmentApps) {
            val ea = entApp.lowercase()
            if (pkgLower.contains(ea) || nameLower.contains(ea) || ea in pkgLower || ea in nameLower) {
                return AppCategory.ENTERTAINMENT
            }
        }

        return AppCategory.OTHER
    }

    suspend fun recordActivity(packageName: String, appName: String, category: AppCategory): ActivityEntry {
        val now = LocalDateTime.now()
        val today = LocalDate.now().format(dateFormatter)

        val entry = ActivityEntry(
            date = today,
            timestamp = now.format(timestampFormatter),
            appPackage = packageName,
            appName = appName.ifBlank { packageName },
            category = category.name.lowercase(),
            isSynced = false
        )

        activityDao.insert(entry)
        return entry
    }

    suspend fun getTodayEntries(): List<ActivityEntry> {
        val today = LocalDate.now().format(dateFormatter)
        return activityDao.getByDate(today)
    }

    suspend fun getTodayCount(): Int {
        val today = LocalDate.now().format(dateFormatter)
        return activityDao.getCountByDate(today)
    }

    suspend fun getCategoryStats(date: String): Map<String, Int> {
        val entries = activityDao.getByDate(date)
        return entries.groupBy { it.category }
            .mapValues { it.value.size }
    }

    suspend fun getUnsyncedEntries(limit: Int = 100): List<ActivityEntry> {
        return activityDao.getUnsynced(limit)
    }

    suspend fun markEntriesSynced(ids: List<Long>) {
        activityDao.markSynced(ids)
    }

    suspend fun cleanOldData(daysToKeep: Int = 30) {
        val cutoff = LocalDate.now().minusDays(daysToKeep.toLong()).format(dateFormatter)
        activityDao.deleteOlderThan(cutoff)
    }
}
