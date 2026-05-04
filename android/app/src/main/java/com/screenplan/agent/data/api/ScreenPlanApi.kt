package com.screenplan.agent.data.api

import com.screenplan.agent.model.*
import retrofit2.Response
import retrofit2.http.*

interface ScreenPlanApi {

    @GET("api/health")
    suspend fun healthCheck(): Response<HealthResponse>

    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<AuthResponse>

    @POST("api/auth/register")
    suspend fun register(@Body request: RegisterRequest): Response<AuthResponse>

    @POST("api/devices")
    suspend fun registerDevice(
        @Header("Authorization") token: String,
        @Body request: DeviceRegisterRequest
    ): Response<DeviceResponse>

    @GET("api/devices")
    suspend fun getDevices(
        @Header("Authorization") token: String
    ): Response<List<DeviceResponse>>

    @POST("api/usage/timeline/upload")
    suspend fun uploadTimeline(
        @Header("Authorization") token: String,
        @Body request: TimelineUploadRequest
    ): Response<Void>

    @POST("api/schedule/generate")
    suspend fun generateSchedule(
        @Header("Authorization") token: String,
        @Body request: ScheduleGenerateRequest
    ): Response<ScheduleResponse>

    @GET("api/schedule/latest")
    suspend fun getLatestSchedule(
        @Header("Authorization") token: String
    ): Response<ScheduleResponse>
}
