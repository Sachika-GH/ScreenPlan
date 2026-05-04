package com.screenplan.agent.service

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.*
import com.screenplan.agent.data.local.DeviceStateManager
import com.screenplan.agent.data.repository.SyncRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.flow.first
import java.util.concurrent.TimeUnit

@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val syncRepository: SyncRepository,
    private val deviceStateManager: DeviceStateManager
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val deviceId = deviceStateManager.deviceId.first() ?: return Result.retry()

        val flushed = syncRepository.flushOfflineQueue(deviceId)
        val uploaded = syncRepository.uploadBatch(deviceId)

        val successCount = flushed + uploaded
        if (successCount > 0) {
            val now = java.time.LocalDateTime.now()
                .format(java.time.format.DateTimeFormatter.ISO_LOCAL_DATE_TIME)
            deviceStateManager.saveLastSyncTime(now)
        }

        return Result.success()
    }

    companion object {
        private const val WORK_NAME = "screenplan_sync_work"

        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = PeriodicWorkRequestBuilder<SyncWorker>(
                15, TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    30, TimeUnit.SECONDS
                )
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
        }
    }
}
