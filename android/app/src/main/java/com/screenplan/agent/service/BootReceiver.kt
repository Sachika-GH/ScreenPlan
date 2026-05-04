package com.screenplan.agent.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.screenplan.agent.data.local.DeviceStateManager
import com.screenplan.agent.data.local.TokenManager
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.*
import javax.inject.Inject

@AndroidEntryPoint
class BootReceiver : BroadcastReceiver() {

    @Inject lateinit var tokenManager: TokenManager
    @Inject lateinit var deviceStateManager: DeviceStateManager

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED ||
            intent.action == "android.intent.action.QUICKBOOT_POWERON") {

            if (tokenManager.isLoggedIn()) {
                TrackingService.start(context)
            }
        }
    }
}
