package com.screenplan.agent.model

import com.google.gson.annotations.SerializedName

enum class AppCategory {
    @SerializedName("learning") LEARNING,
    @SerializedName("entertainment") ENTERTAINMENT,
    @SerializedName("other") OTHER
}

enum class Platform {
    @SerializedName("windows") WINDOWS,
    @SerializedName("macos") MACOS,
    @SerializedName("ios") IOS,
    @SerializedName("android") ANDROID
}

data class AuthResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("token_type") val tokenType: String = "bearer",
    @SerializedName("user_id") val userId: Int,
    @SerializedName("family_id") val familyId: Int,
    @SerializedName("display_name") val displayName: String
)

data class DeviceResponse(
    val id: Int,
    val name: String,
    val platform: String,
    @SerializedName("registered_at") val registeredAt: String
)

data class TimelineEvent(
    @SerializedName("app_name") val appName: String,
    val category: AppCategory,
    val timestamp: String
)

data class TimelineUploadRequest(
    @SerializedName("device_id") val deviceId: Int,
    val events: List<TimelineEvent>
)

data class ScheduleResponse(
    val id: Int,
    @SerializedName("user_id") val userId: Int,
    val date: String,
    @SerializedName("plan_markdown") val planMarkdown: String,
    @SerializedName("generated_at") val generatedAt: String
)

data class HealthResponse(
    val status: String = "ok",
    val version: String,
    @SerializedName("uptime_seconds") val uptimeSeconds: Double,
    @SerializedName("user_count") val userCount: Int
)

data class ErrorResponse(
    val error: String,
    val detail: String? = null
)

data class LoginRequest(
    val email: String,
    val password: String
)

data class RegisterRequest(
    @SerializedName("family_name") val familyName: String,
    val email: String,
    val password: String,
    @SerializedName("display_name") val displayName: String
)

data class DeviceRegisterRequest(
    val name: String,
    val platform: String
)

data class ScheduleGenerateRequest(
    @SerializedName("include_calendar") val includeCalendar: Boolean = false
)
