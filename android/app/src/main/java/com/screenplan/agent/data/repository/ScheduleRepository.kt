package com.screenplan.agent.data.repository

import com.screenplan.agent.data.api.ScreenPlanApi
import com.screenplan.agent.data.local.TokenManager
import com.screenplan.agent.model.ScheduleGenerateRequest
import com.screenplan.agent.model.ScheduleResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ScheduleRepository @Inject constructor(
    private val api: ScreenPlanApi,
    private val tokenManager: TokenManager
) {
    suspend fun generateSchedule(): Result<ScheduleResponse> {
        val token = tokenManager.loadToken()
            ?: return Result.failure(Exception("Not logged in"))
        return try {
            val resp = api.generateSchedule("Bearer $token", ScheduleGenerateRequest())
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception(resp.errorBody()?.string() ?: "Generation failed"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getLatestSchedule(): Result<ScheduleResponse> {
        val token = tokenManager.loadToken()
            ?: return Result.failure(Exception("Not logged in"))
        return try {
            val resp = api.getLatestSchedule("Bearer $token")
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception(resp.errorBody()?.string() ?: "Fetch failed"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
