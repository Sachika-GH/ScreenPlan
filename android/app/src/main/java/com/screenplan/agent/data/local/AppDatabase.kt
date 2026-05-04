package com.screenplan.agent.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.screenplan.agent.model.ActivityEntry
import com.screenplan.agent.model.OfflineQueueEntry

@Database(
    entities = [ActivityEntry::class, OfflineQueueEntry::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun activityDao(): ActivityDao
    abstract fun offlineQueueDao(): OfflineQueueDao
}
