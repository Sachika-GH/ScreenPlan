package com.screenplan.agent.util

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetAddress

object GatewayDetector {

    fun getServerUrl(context: Context): String {
        val saved = context.getSharedPreferences("gateway_prefs", Context.MODE_PRIVATE)
            .getString("server_url", null)
        if (!saved.isNullOrBlank()) return saved

        val gateway = getDefaultGateway()
        return if (gateway != null) "http://$gateway:5051" else "http://45.197.150.197:5051"
    }

    fun saveServerUrl(context: Context, url: String) {
        context.getSharedPreferences("gateway_prefs", Context.MODE_PRIVATE)
            .edit()
            .putString("server_url", url)
            .apply()
    }

    private fun getDefaultGateway(): String? {
        try {
            val process = Runtime.getRuntime().exec(arrayOf("/system/bin/ip", "route", "show", "default"))
            val reader = BufferedReader(InputStreamReader(process.inputStream))
            val line = reader.readLine()
            reader.close()
            process.waitFor()

            if (line != null) {
                val parts = line.trim().split("\\s+".toRegex())
                val gatewayIndex = parts.indexOf("via")
                if (gatewayIndex >= 0 && gatewayIndex + 1 < parts.size) {
                    val gateway = parts[gatewayIndex + 1]
                    InetAddress.getByName(gateway)
                    return gateway
                }

                for (part in parts) {
                    try {
                        val addr = InetAddress.getByName(part)
                        if (!addr.isLoopbackAddress && !addr.isLinkLocalAddress) {
                            return part
                        }
                    } catch (_: Exception) {}
                }
            }
        } catch (_: Exception) {}

        try {
            val process = Runtime.getRuntime().exec(arrayOf("/system/bin/ip", "route"))
            val reader = BufferedReader(InputStreamReader(process.inputStream))
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                if (line!!.startsWith("default")) {
                    val parts = line!!.trim().split("\\s+".toRegex())
                    val viaIdx = parts.indexOf("via")
                    if (viaIdx >= 0 && viaIdx + 1 < parts.size) {
                        reader.close()
                        return parts[viaIdx + 1]
                    }
                }
            }
            reader.close()
        } catch (_: Exception) {}

        return null
    }

    fun isNetworkAvailable(context: Context): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}
