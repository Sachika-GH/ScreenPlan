package com.screenplan.agent.data.repository

import android.util.Log
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
    companion object {
        const val TAG = "ScreenPlanSync"
    }

    suspend fun uploadSingleEvent(
        deviceId: Int,
        appName: String,
        appPackage: String,
        category: String,
        timestamp: String
    ): Boolean {
        val token = tokenManager.loadToken()
        if (token == null) {
            Log.w(TAG, "uploadSingleEvent: no token")
            queueForRetry(deviceId, appName, appPackage, category, timestamp)
            return false
        }

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
                Log.d(TAG, "uploadSingleEvent OK: $appName dev=$deviceId")
                true
            } else {
                val errBody = resp.errorBody()?.string() ?: "unknown"
                Log.e(TAG, "uploadSingleEvent HTTP ${resp.code()}: $errBody")
                queueForRetry(deviceId, appName, appPackage, category, timestamp)
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "uploadSingleEvent exception: ${e.javaClass.simpleName} ${e.message}")
            queueForRetry(deviceId, appName, appPackage, category, timestamp)
            false
        }
    }

    suspend fun queueForRetry(
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
        val token = tokenManager.loadToken()
        if (token == null) {
            Log.w(TAG, "flushOfflineQueue: no token")
            return 0
        }
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
                Log.d(TAG, "flushOfflineQueue OK: ${events.size} events")
                events.size
            } else {
                val errBody = resp.errorBody()?.string() ?: "unknown"
                Log.e(TAG, "flushOfflineQueue HTTP ${resp.code()}: $errBody")
                0
            }
        } catch (e: Exception) {
            Log.e(TAG, "flushOfflineQueue exception: ${e.javaClass.simpleName} ${e.message}")
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
