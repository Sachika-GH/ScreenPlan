package com.screenplan.agent.service

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
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

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var trackingJob: Job? = null
    private var flushJob: Job? = null
    private var lastPackage: String? = null

    private var trackingRunning = false

    companion object {
        const val CHANNEL_ID = "screenplan_tracking_channel"
        const val NOTIFICATION_ID = 1001

        const val ACTION_START_TRACKING = "com.screenplan.agent.START_TRACKING"
        const val ACTION_STOP_TRACKING = "com.screenplan.agent.STOP_TRACKING"

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
        when (intent?.action) {
            ACTION_START_TRACKING -> startTracking()
            ACTION_STOP_TRACKING -> stopTracking()
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startTracking() {
        if (trackingRunning) return
        trackingRunning = true

        val notification = buildNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        val wakeLock = (getSystemService(Context.POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ScreenPlan:TrackingLock")
        wakeLock.acquire(10 * 60 * 1000L)

        trackingJob = serviceScope.launch {
            val usageStatsHelper = UsageStatsHelper(this@TrackingService)

            while (isActive && trackingRunning) {
                try {
                    val deviceId = deviceStateManager.deviceId.first()
                    val interval = deviceStateManager.recordIntervalMinutes.first()

                    val pkg = usageStatsHelper.getCurrentForegroundPackage()
                    if (pkg != null && pkg != lastPackage && pkg != packageName) {
                        lastPackage = pkg
                        val appName = usageStatsHelper.getAppName(pkg)
                        val category = appClassifier.classify(pkg, appName)

                        trackingRepository.recordActivity(pkg, appName, category)

                        if (deviceId != null) {
                            withContext(Dispatchers.IO) {
                                syncRepository.uploadSingleEvent(
                                    deviceId = deviceId,
                                    appName = appName,
                                    appPackage = pkg,
                                    category = category.name.lowercase(),
                                    timestamp = java.time.LocalDateTime.now()
                                        .format(java.time.format.DateTimeFormatter.ISO_LOCAL_DATE_TIME)
                                )
                            }
                        }

                        updateNotification("${getString(R.string.tracking_status)}: $appName")
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }

                try {
                    val interval = deviceStateManager.recordIntervalMinutes.first()
                    delay((interval * 60 * 1000L).coerceAtLeast(30_000L))
                } catch (_: Exception) {
                    delay(3 * 60 * 1000L)
                }
            }
        }

        flushJob = serviceScope.launch {
            while (isActive && trackingRunning) {
                delay(60 * 1000L)
                try {
                    val queueSize = syncRepository.getQueueSize()
                    if (queueSize > 0) {
                        val dId = deviceStateManager.deviceId.first()
                        dId?.let { syncRepository.flushOfflineQueue(it) }
                    }
                } catch (_: Exception) {}
            }
        }

        serviceScope.launch { deviceStateManager.setTrackingEnabled(true) }
    }

    private fun stopTracking() {
        trackingRunning = false
        trackingJob?.cancel()
        flushJob?.cancel()

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
        serviceScope.cancel()
        super.onDestroy()
    }
}
