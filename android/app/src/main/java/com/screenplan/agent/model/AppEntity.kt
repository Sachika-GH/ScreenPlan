package com.screenplan.agent.model

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "activity_log")
data class ActivityEntry(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    @ColumnInfo(name = "date") val date: String,
    @ColumnInfo(name = "timestamp") val timestamp: String,
    @ColumnInfo(name = "app_package") val appPackage: String,
    @ColumnInfo(name = "app_name") val appName: String,
    @ColumnInfo(name = "category") val category: String,
    @ColumnInfo(name = "is_synced") val isSynced: Boolean = false,
    @ColumnInfo(name = "device_id") val deviceId: Int? = null
)

@Entity(tableName = "offline_queue")
data class OfflineQueueEntry(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    @ColumnInfo(name = "device_id") val deviceId: Int,
    @ColumnInfo(name = "timestamp") val timestamp: String,
    @ColumnInfo(name = "app_name") val appName: String,
    @ColumnInfo(name = "app_package") val appPackage: String,
    @ColumnInfo(name = "category") val category: String,
    @ColumnInfo(name = "retry_count") val retryCount: Int = 0
)
