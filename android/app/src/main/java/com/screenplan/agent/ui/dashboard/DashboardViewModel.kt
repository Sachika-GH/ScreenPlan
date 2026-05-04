package com.screenplan.agent.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.screenplan.agent.data.local.DeviceStateManager
import com.screenplan.agent.data.local.TokenManager
import com.screenplan.agent.data.repository.AuthRepository
import com.screenplan.agent.data.repository.SyncRepository
import com.screenplan.agent.data.repository.TrackingRepository
import com.screenplan.agent.service.TrackingService
import com.screenplan.agent.util.UsageStatsHelper
import com.screenplan.agent.util.GatewayDetector
import android.content.Context
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import javax.inject.Inject

data class DashboardUiState(
    val isLoggedIn: Boolean = false,
    val isTracking: Boolean = false,
    val deviceId: Int? = null,
    val todayRecordCount: Int = 0,
    val learningCount: Int = 0,
    val entertainmentCount: Int = 0,
    val otherCount: Int = 0,
    val queueSize: Int = 0,
    val lastUploadOk: Boolean? = null,
    val hasUsageStatsPermission: Boolean = false,
    val backendOnline: Boolean = false,
    val serverUrl: String = "",
    val lastSyncTime: String? = null,
    val lastRecordTime: String? = null,
    val lastUploadTime: String? = null,
    val isLoading: Boolean = false
)

@HiltViewModel
class DashboardViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val trackingRepository: TrackingRepository,
    private val syncRepository: SyncRepository,
    private val authRepository: AuthRepository,
    private val tokenManager: TokenManager,
    private val deviceStateManager: DeviceStateManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        _uiState.value = _uiState.value.copy(
            isLoggedIn = tokenManager.isLoggedIn(),
            hasUsageStatsPermission = UsageStatsHelper(context).hasUsageStatsPermission(),
            serverUrl = GatewayDetector.getServerUrl(context)
        )
        loadTodayStats()
        checkBackendHealth()

        viewModelScope.launch {
            deviceStateManager.deviceId.collect { id ->
                _uiState.value = _uiState.value.copy(deviceId = id)
            }
        }

        viewModelScope.launch {
            deviceStateManager.trackingEnabled.collect { enabled ->
                _uiState.value = _uiState.value.copy(isTracking = enabled)
            }
        }

        viewModelScope.launch {
            deviceStateManager.lastSyncTime.collect { time ->
                _uiState.value = _uiState.value.copy(lastSyncTime = time)
            }
        }

        viewModelScope.launch {
            deviceStateManager.lastRecordTime.collect { time ->
                _uiState.value = _uiState.value.copy(lastRecordTime = time)
            }
        }

        viewModelScope.launch {
            deviceStateManager.lastUploadTime.collect { time ->
                _uiState.value = _uiState.value.copy(lastUploadTime = time)
            }
        }

        viewModelScope.launch {
            deviceStateManager.serverUrl.collect { url ->
                if (url != _uiState.value.serverUrl) {
                    _uiState.value = _uiState.value.copy(serverUrl = url)
                }
            }
        }
    }

    fun refresh() {
        loadTodayStats()
        checkBackendHealth()
        _uiState.value = _uiState.value.copy(
            hasUsageStatsPermission = UsageStatsHelper(context).hasUsageStatsPermission()
        )
        viewModelScope.launch {
            val queueSize = syncRepository.getQueueSize()
            _uiState.value = _uiState.value.copy(queueSize = queueSize)
        }
    }

    fun toggleTracking() {
        if (_uiState.value.isTracking) {
            TrackingService.stop(context)
            _uiState.value = _uiState.value.copy(isTracking = false)
        } else {
            TrackingService.start(context)
            _uiState.value = _uiState.value.copy(isTracking = true)
        }
    }

    fun logout() {
        TrackingService.stop(context)
        authRepository.logout()
        viewModelScope.launch {
            deviceStateManager.clearAll()
        }
        _uiState.value = _uiState.value.copy(
            isLoggedIn = false,
            isTracking = false
        )
    }

    private fun loadTodayStats() {
        viewModelScope.launch {
            val today = LocalDate.now().format(DateTimeFormatter.ISO_LOCAL_DATE)
            val entries = trackingRepository.getTodayEntries()
            _uiState.value = _uiState.value.copy(
                todayRecordCount = entries.size,
                learningCount = entries.count { it.category == "learning" },
                entertainmentCount = entries.count { it.category == "entertainment" },
                otherCount = entries.count { it.category == "other" }
            )
            val queueSize = syncRepository.getQueueSize()
            _uiState.value = _uiState.value.copy(queueSize = queueSize)
        }
    }

    private fun checkBackendHealth() {
        viewModelScope.launch {
            val result = authRepository.healthCheck()
            _uiState.value = _uiState.value.copy(
                backendOnline = result.isSuccess
            )
        }
    }
}
