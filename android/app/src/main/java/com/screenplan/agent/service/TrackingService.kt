package com.screenplan.agent.service

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.screenplan.agent.R
import com.screenplan.agent.data.local.DeviceStateManager
import com.screenplan.agent.data.repository.SyncRepository
import com.screenplan.agent.data.repository.TrackingRepository
import com.screenplan.agent.util.AppClassifier
import com.screenplan.agent.util.UsageStatsHelper
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import javax.inject.Inject

@AndroidEntryPoint
class TrackingService : Service() {

    @Inject lateinit var trackingRepository: TrackingRepository
    @Inject lateinit var syncRepository: SyncRepository
    @Inject lateinit var appClassifier: AppClassifier
    @Inject lateinit var deviceStateManager: DeviceStateManager
    @Inject lateinit var tokenManager: com.screenplan.agent.data.local.TokenManager
    @Inject lateinit var api: com.screenplan.agent.data.api.ScreenPlanApi

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var trackingJob: Job? = null
    private var flushJob: Job? = null
    private var wakeLockRenewJob: Job? = null
    private var lastPackage: String? = null
    private var wakeLock: PowerManager.WakeLock? = null

    private var trackingRunning = false

    companion object {
        const val TAG = "ScreenPlan"
        const val CHANNEL_ID = "screenplan_tracking_channel"
        const val NOTIFICATION_ID = 1001

        const val ACTION_START_TRACKING = "com.screenplan.agent.START_TRACKING"
        const val ACTION_STOP_TRACKING = "com.screenplan.agent.STOP_TRACKING"

        private const val WAKELOCK_DURATION_MS = 9 * 60 * 1000L
        private const val WAKELOCK_RENEW_MS = 8 * 60 * 1000L

        fun start(context: Context) {
            val intent = Intent(context, TrackingService::class.java).apply {
                action = ACTION_START_TRACKING
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            val intent = Intent(context, TrackingService::class.java).apply {
                action = ACTION_STOP_TRACKING
            }
            context.startService(intent)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d(TAG, "onStartCommand action=${intent?.action} flags=$flags")
        when (intent?.action) {
            ACTION_START_TRACKING -> startTracking()
            ACTION_STOP_TRACKING -> stopTracking()
            null -> {
                Log.d(TAG, "onStartCommand null intent - checking resume")
                checkAndResumeTracking()
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun checkAndResumeTracking() {
        serviceScope.launch {
            try {
                val wasTracking = deviceStateManager.trackingEnabled.first()
                Log.d(TAG, "checkAndResumeTracking wasTracking=$wasTracking")
                if (wasTracking && !trackingRunning) {
                    Log.d(TAG, "checkAndResumeTracking -> resuming")
                    startTracking()
                }
            } catch (e: Exception) {
                Log.e(TAG, "checkAndResumeTracking failed", e)
            }
        }
    }

    private fun tryRecoverDeviceId() {
        serviceScope.launch {
            try {
                val token = tokenManager.loadToken() ?: return@launch
                val resp = api.getDevices("Bearer $token")
                if (resp.isSuccessful && resp.body() != null) {
                    val device = resp.body()!!.firstOrNull { it.platform == "android" }
                    if (device != null) {
                        deviceStateManager.saveDeviceId(device.id)
                        deviceStateManager.saveDeviceName(device.name)
                        Log.d(TAG, "tryRecoverDeviceId: recovered deviceId=${device.id}")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "tryRecoverDeviceId failed", e)
            }
        }
    }

    private fun acquireWakeLock() {
        try {
            wakeLock?.let { if (it.isHeld) it.release() }
            wakeLock = (getSystemService(Context.POWER_SERVICE) as PowerManager)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ScreenPlan:TrackingLock")
            wakeLock?.acquire(WAKELOCK_DURATION_MS)
        } catch (_: Exception) {}
    }

    private fun releaseWakeLock() {
        try {
            wakeLock?.let { if (it.isHeld) it.release() }
            wakeLock = null
        } catch (_: Exception) {}
    }

    private fun startTracking() {
        if (trackingRunning) return
        trackingRunning = true
        Log.d(TAG, "startTracking begin")

        val notification = buildNotification()
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                startForeground(NOTIFICATION_ID, notification,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE or
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIFICATION_ID, notification,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        } catch (e: Exception) {
            Log.e(TAG, "startForeground primary failed: ${e.javaClass.simpleName}", e)
            // Fallback: try with just dataSync type (API 24+)
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    startForeground(NOTIFICATION_ID, notification,
                        android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
                } else {
                    startForeground(NOTIFICATION_ID, notification)
                }
                Log.d(TAG, "startForeground fallback OK")
            } catch (e2: Exception) {
                Log.e(TAG, "startForeground fallback also failed: ${e2.javaClass.simpleName}", e2)
                trackingRunning = false
                return
            }
        }

        acquireWakeLock()

        wakeLockRenewJob = serviceScope.launch {
            while (isActive && trackingRunning) {
                delay(WAKELOCK_RENEW_MS)
                try {
                    if (trackingRunning) acquireWakeLock()
                } catch (e: Exception) {
                    Log.e(TAG, "wakeLockRenew failed", e)
                }
            }
        }

        trackingJob = serviceScope.launch {
            val usageStatsHelper = UsageStatsHelper(this@TrackingService)
            val hasPerm = usageStatsHelper.hasUsageStatsPermission()
            Log.d(TAG, "trackingJob started, usagePerm=$hasPerm")

            var loopCount = 0
            while (isActive && trackingRunning) {
                loopCount++
                try {
                    val deviceId = deviceStateManager.deviceId.first()
                    val interval = deviceStateManager.recordIntervalMinutes.first()

                    if (loopCount % 10 == 1 || loopCount <= 3) {
                        Log.d(TAG, "trackingLoop #$loopCount deviceId=$deviceId interval=$interval lastPkg=$lastPackage")
                    }

                    val pkg = usageStatsHelper.getCurrentForegroundPackage()

                    if (pkg == null) {
                        if (loopCount <= 3) Log.w(TAG, "trackingLoop: no foreground package (perm?)")
                        updateNotification("Loop #$loopCount | devId=$deviceId | no fg")
                    } else if (pkg == packageName) {
                        if (loopCount <= 3) Log.d(TAG, "trackingLoop: foreground is self")
                        updateNotification("Loop #$loopCount | devId=$deviceId | self")
                    } else {
                        val currentTimestamp = java.time.LocalDateTime.now()
                            .format(java.time.format.DateTimeFormatter.ISO_LOCAL_DATE_TIME)

                        val appChanged = pkg != lastPackage
                        lastPackage = pkg

                        val appName = usageStatsHelper.getAppName(pkg)
                        val category = appClassifier.classify(pkg, appName)

                        trackingRepository.recordActivity(pkg, appName, category)
                        Log.d(TAG, "recorded: $appName ($pkg) cat=$category deviceId=$deviceId")

                        deviceStateManager.saveLastRecordTime(currentTimestamp)

                        if (deviceId != null) {
                            val uploaded = syncRepository.uploadSingleEvent(
                                deviceId = deviceId,
                                appName = appName,
                                appPackage = pkg,
                                category = category.name.lowercase(),
                                timestamp = currentTimestamp
                            )
                            if (uploaded) {
                                Log.d(TAG, "uploaded OK: $appName")
                                deviceStateManager.saveLastUploadTime(currentTimestamp)
                            } else {
                                Log.w(TAG, "upload FAILED: $appName (queued)")
                            }
                        } else {
                            Log.w(TAG, "skip upload: deviceId is null")
                            // Still queue for retry if we have a token
                            syncRepository.queueForRetry(deviceId = 0, appName, pkg, category.name.lowercase(), currentTimestamp)
                            tryRecoverDeviceId()
                        }

                        val queueSize = syncRepository.getQueueSize()
                        val notifText = if (deviceId == null) {
                            "⚠ No device | #$loopCount $appName"
                        } else if (queueSize > 10) {
                            "⚠ $queueSize queued | #$loopCount $appName"
                        } else {
                            "#$loopCount $appName ($category)"
                        }
                        updateNotification(notifText)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "trackingLoop error", e)
                }

                try {
                    val interval = deviceStateManager.recordIntervalMinutes.first()
                    delay((interval * 60 * 1000L).coerceAtLeast(30_000L))
                } catch (_: Exception) {
                    delay(3 * 60 * 1000L)
                }
            }
            Log.d(TAG, "trackingJob exiting (isActive=$isActive trackingRunning=$trackingRunning)")
        }

        flushJob = serviceScope.launch {
            while (isActive && trackingRunning) {
                delay(60 * 1000L)
                try {
                    val queueSize = syncRepository.getQueueSize()
                    if (queueSize > 0) {
                        val dId = deviceStateManager.deviceId.first()
                        val flushed = dId?.let { syncRepository.flushOfflineQueue(it) } ?: 0
                        val remaining = syncRepository.getQueueSize()
                        if (flushed > 0) Log.d(TAG, "flushOfflineQueue flushed=$flushed remaining=$remaining")
                        if (remaining > 10) {
                            updateNotification("⚠ $remaining offline events queued")
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "flushJob error", e)
                }
            }
        }

        serviceScope.launch { deviceStateManager.setTrackingEnabled(true) }
        Log.d(TAG, "startTracking complete")
    }

    private fun stopTracking() {
        trackingRunning = false
        trackingJob?.cancel()
        flushJob?.cancel()
        wakeLockRenewJob?.cancel()
        releaseWakeLock()
        lastPackage = null

        serviceScope.launch { deviceStateManager.setTrackingEnabled(false) }

        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun updateNotification(text: String) {
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_info_details)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, notification)
    }

    private fun buildNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.tracking_status))
            .setSmallIcon(android.R.drawable.ic_menu_info_details)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.tracking_channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.tracking_channel_desc)
                setShowBadge(false)
            }
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        trackingRunning = false
        trackingJob?.cancel()
        flushJob?.cancel()
        wakeLockRenewJob?.cancel()
        releaseWakeLock()
        serviceScope.cancel()
        super.onDestroy()
    }
}
