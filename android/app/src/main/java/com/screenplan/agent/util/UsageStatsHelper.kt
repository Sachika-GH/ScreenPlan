package com.screenplan.agent.util

import android.app.AppOpsManager
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build
import android.os.Process
import android.provider.Settings

class UsageStatsHelper(private val context: Context) {

    fun hasUsageStatsPermission(): Boolean {
        val appOpsManager = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            appOpsManager.unsafeCheckOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                context.packageName
            )
        } else {
            @Suppress("DEPRECATION")
            appOpsManager.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                context.packageName
            )
        }
        return mode == AppOpsManager.MODE_ALLOWED
    }

    fun getUsageStatsPermissionIntent(): Intent {
        return Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)
    }

    fun getCurrentForegroundPackage(): String? {
        if (!hasUsageStatsPermission()) return null

        val endTime = System.currentTimeMillis()
        val beginTime = endTime - 10000

        val usageStatsManager = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val usageStats = usageStatsManager.queryUsageStats(
            UsageStatsManager.INTERVAL_DAILY,
            beginTime,
            endTime
        )

        var recentPkg: String? = null
        var recentTime = 0L

        for (stat in usageStats) {
            if (stat.lastTimeUsed > recentTime) {
                recentPkg = stat.packageName
                recentTime = stat.lastTimeUsed
            }
        }

        return recentPkg
    }

    fun getAppName(packageName: String): String {
        return try {
            val packageManager = context.packageManager
            val appInfo = packageManager.getApplicationInfo(packageName, 0)
            packageManager.getApplicationLabel(appInfo).toString()
        } catch (e: PackageManager.NameNotFoundException) {
            packageName
        }
    }

    fun getInstalledApps(): List<Pair<String, String>> {
        val pm = context.packageManager
        return pm.getInstalledApplications(0).map { appInfo ->
            appInfo.packageName to pm.getApplicationLabel(appInfo).toString()
        }
    }
}
