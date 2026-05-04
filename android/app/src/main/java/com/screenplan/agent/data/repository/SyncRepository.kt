package com.screenplan.agent.data.repository

import com.screenplan.agent.data.api.ScreenPlanApi
import com.screenplan.agent.data.local.OfflineQueueDao
import com.screenplan.agent.data.local.TokenManager
import com.screenplan.agent.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SyncRepository @Inject constructor(
    private val api: ScreenPlanApi,
    private val offlineQueueDao: OfflineQueueDao,
    private val tokenManager: TokenManager,
    private val trackingRepository: TrackingRepository
) {
    suspend fun uploadSingleEvent(
        deviceId: Int,
        appName: String,
        appPackage: String,
        category: String,
        timestamp: String
    ): Boolean {
        val token = tokenManager.loadToken() ?: return false

        val event = TimelineEvent(
            appName = appName,
            category = when (category.lowercase()) {
                "learning" -> AppCategory.LEARNING
                "entertainment" -> AppCategory.ENTERTAINMENT
                else -> AppCategory.OTHER
            },
            timestamp = timestamp
        )

        return try {
            val resp = api.uploadTimeline(
                "Bearer $token",
                TimelineUploadRequest(deviceId, listOf(event))
            )
            if (resp.isSuccessful) {
                true
            } else {
                queueForRetry(deviceId, appName, appPackage, category, timestamp)
                false
            }
        } catch (e: Exception) {
            queueForRetry(deviceId, appName, appPackage, category, timestamp)
            false
        }
    }

    private suspend fun queueForRetry(
        deviceId: Int,
        appName: String,
        appPackage: String,
        category: String,
        timestamp: String
    ) {
        offlineQueueDao.insert(
            OfflineQueueEntry(
                deviceId = deviceId,
                appName = appName,
                appPackage = appPackage,
                category = category,
                timestamp = timestamp
            )
        )
    }

    suspend fun getQueueSize(): Int = offlineQueueDao.getCount()

    suspend fun flushOfflineQueue(deviceId: Int): Int {
        val token = tokenManager.loadToken() ?: return 0
        val queue = offlineQueueDao.getAll()
        if (queue.isEmpty()) return 0

        val events = queue.map { entry ->
            TimelineEvent(
                appName = entry.appName,
                category = when (entry.category.lowercase()) {
                    "learning" -> AppCategory.LEARNING
                    "entertainment" -> AppCategory.ENTERTAINMENT
                    else -> AppCategory.OTHER
                },
                timestamp = entry.timestamp
            )
        }

        return try {
            val resp = api.uploadTimeline(
                "Bearer $token",
                TimelineUploadRequest(deviceId, events)
            )
            if (resp.isSuccessful) {
                val ids = queue.map { it.id }
                offlineQueueDao.deleteByIds(ids)
                events.size
            } else {
                0
            }
        } catch (e: Exception) {
            0
        }
    }

    suspend fun uploadBatch(deviceId: Int): Int {
        val unsynced = trackingRepository.getUnsyncedEntries(100)
        if (unsynced.isEmpty()) return 0

        val token = tokenManager.loadToken() ?: return 0

        val events = unsynced.map { entry ->
            TimelineEvent(
                appName = entry.appName,
                category = when (entry.category.lowercase()) {
                    "learning" -> AppCategory.LEARNING
                    "entertainment" -> AppCategory.ENTERTAINMENT
                    else -> AppCategory.OTHER
                },
                timestamp = entry.timestamp
            )
        }

        return try {
            val resp = api.uploadTimeline(
                "Bearer $token",
                TimelineUploadRequest(deviceId, events)
            )
            if (resp.isSuccessful) {
                trackingRepository.markEntriesSynced(unsynced.map { it.id })
                events.size
            } else {
                0
            }
        } catch (e: Exception) {
            0
        }
    }
}
