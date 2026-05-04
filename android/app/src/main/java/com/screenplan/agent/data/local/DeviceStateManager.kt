package com.screenplan.agent.data.local

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore("device_state")

class DeviceStateManager(private val context: Context) {

    val deviceId: Flow<Int?> = context.dataStore.data.map { prefs ->
        prefs[KEY_DEVICE_ID]
    }

    val deviceName: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[KEY_DEVICE_NAME] ?: "Android"
    }

    val trackingEnabled: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_TRACKING_ENABLED] ?: false
    }

    val serverUrl: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[KEY_SERVER_URL] ?: DEFAULT_SERVER_URL
    }

    val recordIntervalMinutes: Flow<Int> = context.dataStore.data.map { prefs ->
        prefs[KEY_RECORD_INTERVAL] ?: DEFAULT_INTERVAL_MINUTES
    }

    val lastSyncTime: Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[KEY_LAST_SYNC]
    }

    suspend fun saveDeviceId(id: Int) {
        context.dataStore.edit { it[KEY_DEVICE_ID] = id }
    }

    suspend fun saveDeviceName(name: String) {
        context.dataStore.edit { it[KEY_DEVICE_NAME] = name }
    }

    suspend fun setTrackingEnabled(enabled: Boolean) {
        context.dataStore.edit { it[KEY_TRACKING_ENABLED] = enabled }
    }

    suspend fun saveServerUrl(url: String) {
        context.dataStore.edit { it[KEY_SERVER_URL] = url }
    }

    suspend fun saveRecordInterval(minutes: Int) {
        context.dataStore.edit { it[KEY_RECORD_INTERVAL] = minutes }
    }

    suspend fun saveLastSyncTime(time: String) {
        context.dataStore.edit { it[KEY_LAST_SYNC] = time }
    }

    suspend fun clearAll() {
        context.dataStore.edit { it.clear() }
    }

    companion object {
        private val KEY_DEVICE_ID = intPreferencesKey("device_id")
        private val KEY_DEVICE_NAME = stringPreferencesKey("device_name")
        private val KEY_TRACKING_ENABLED = booleanPreferencesKey("tracking_enabled")
        private val KEY_SERVER_URL = stringPreferencesKey("server_url")
        private val KEY_RECORD_INTERVAL = intPreferencesKey("record_interval")
        private val KEY_LAST_SYNC = stringPreferencesKey("last_sync_time")

        const val DEFAULT_SERVER_URL = "http://45.197.150.197:5051"
        const val DEFAULT_INTERVAL_MINUTES = 3
    }
}
