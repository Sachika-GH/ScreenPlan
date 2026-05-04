package com.screenplan.agent.data.repository

import com.screenplan.agent.data.api.ScreenPlanApi
import com.screenplan.agent.data.local.DeviceStateManager
import com.screenplan.agent.data.local.TokenManager
import com.screenplan.agent.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: ScreenPlanApi,
    private val tokenManager: TokenManager,
    private val deviceStateManager: DeviceStateManager
) {
    suspend fun healthCheck(): Result<HealthResponse> {
        return try {
            val resp = api.healthCheck()
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception(resp.errorBody()?.string() ?: "Health check failed"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun login(email: String, password: String): Result<AuthResponse> {
        return try {
            val resp = api.login(LoginRequest(email, password))
            if (resp.isSuccessful && resp.body() != null) {
                val auth = resp.body()!!
                tokenManager.saveToken(auth.accessToken)
                Result.success(auth)
            } else {
                val error = parseError(resp.errorBody()?.string())
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun register(
        familyName: String,
        email: String,
        password: String,
        displayName: String
    ): Result<AuthResponse> {
        return try {
            val resp = api.register(RegisterRequest(familyName, email, password, displayName))
            if (resp.isSuccessful && resp.body() != null) {
                val auth = resp.body()!!
                tokenManager.saveToken(auth.accessToken)
                Result.success(auth)
            } else {
                val error = parseError(resp.errorBody()?.string())
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun registerDevice(name: String): Result<Int> {
        val token = tokenManager.loadToken() ?: return Result.failure(Exception("Not logged in"))
        return try {
            val resp = api.registerDevice("Bearer $token", DeviceRegisterRequest(name, "android"))
            if (resp.isSuccessful && resp.body() != null) {
                val id = resp.body()!!.id
                deviceStateManager.saveDeviceId(id)
                deviceStateManager.saveDeviceName(name)
                Result.success(id)
            } else if (resp.code() == 409) {
                findExistingDevice(token)
            } else {
                Result.failure(Exception(resp.errorBody()?.string() ?: "Device registration failed"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private suspend fun findExistingDevice(token: String): Result<Int> {
        return try {
            val resp = api.getDevices("Bearer $token")
            if (resp.isSuccessful && resp.body() != null) {
                val device = resp.body()!!.firstOrNull { it.platform == "android" }
                if (device != null) {
                    deviceStateManager.saveDeviceId(device.id)
                    Result.success(device.id)
                } else {
                    Result.failure(Exception("No existing Android device found"))
                }
            } else {
                Result.failure(Exception("Failed to fetch devices"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun isLoggedIn(): Boolean = tokenManager.isLoggedIn()

    fun getToken(): String? = tokenManager.loadToken()

    fun logout() {
        tokenManager.deleteToken()
    }

    private fun parseError(errorBody: String?): String {
        if (errorBody == null) return "Unknown error"
        return try {
            val gson = com.google.gson.Gson()
            val err = gson.fromJson(errorBody, ErrorResponse::class.java)
            err.error
        } catch (e: Exception) {
            "Server error"
        }
    }
}
