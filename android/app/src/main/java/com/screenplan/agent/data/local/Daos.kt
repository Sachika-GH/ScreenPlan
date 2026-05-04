package com.screenplan.agent.data.local

import androidx.room.*
import com.screenplan.agent.model.ActivityEntry
import com.screenplan.agent.model.OfflineQueueEntry

@Dao
interface ActivityDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entry: ActivityEntry): Long

    @Query("SELECT * FROM activity_log WHERE date = :date ORDER BY timestamp ASC")
    suspend fun getByDate(date: String): List<ActivityEntry>

    @Query("SELECT * FROM activity_log WHERE date = :date AND category = :category")
    suspend fun getByDateAndCategory(date: String, category: String): List<ActivityEntry>

    @Query("SELECT COUNT(*) FROM activity_log WHERE date = :date")
    suspend fun getCountByDate(date: String): Int

    @Query("SELECT * FROM activity_log WHERE is_synced = 0 LIMIT :limit")
    suspend fun getUnsynced(limit: Int = 100): List<ActivityEntry>

    @Query("UPDATE activity_log SET is_synced = 1 WHERE id IN (:ids)")
    suspend fun markSynced(ids: List<Long>)

    @Query("DELETE FROM activity_log WHERE date < :before")
    suspend fun deleteOlderThan(before: String)

    @Query("DELETE FROM activity_log")
    suspend fun deleteAll()
}

@Dao
interface OfflineQueueDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entry: OfflineQueueEntry): Long

    @Query("SELECT * FROM offline_queue ORDER BY timestamp ASC")
    suspend fun getAll(): List<OfflineQueueEntry>

    @Query("SELECT COUNT(*) FROM offline_queue")
    suspend fun getCount(): Int

    @Query("DELETE FROM offline_queue WHERE id IN (:ids)")
    suspend fun deleteByIds(ids: List<Long>)

    @Query("DELETE FROM offline_queue")
    suspend fun deleteAll()
}
