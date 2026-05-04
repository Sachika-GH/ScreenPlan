package com.screenplan.agent.ui.settings

import android.os.Build
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.screenplan.agent.data.local.DeviceStateManager
import com.screenplan.agent.util.GatewayDetector
import android.content.Context
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val serverUrl: String = "",
    val recordInterval: Int = 3,
    val deviceName: String = "Android",
    val deviceId: Int? = null,
    val manufacturer: String = Build.MANUFACTURER,
    val model: String = Build.MODEL,
    val androidVersion: String = Build.VERSION.RELEASE,
    val isSaved: Boolean = false
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val deviceStateManager: DeviceStateManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            deviceStateManager.serverUrl.collect { url ->
                _uiState.value = _uiState.value.copy(serverUrl = url)
            }
        }
        viewModelScope.launch {
            deviceStateManager.recordIntervalMinutes.collect { interval ->
                _uiState.value = _uiState.value.copy(recordInterval = interval)
            }
        }
        viewModelScope.launch {
            deviceStateManager.deviceName.collect { name ->
                _uiState.value = _uiState.value.copy(deviceName = name)
            }
        }
        viewModelScope.launch {
            deviceStateManager.deviceId.collect { id ->
                _uiState.value = _uiState.value.copy(deviceId = id)
            }
        }
    }

    fun updateServerUrl(url: String) {
        _uiState.value = _uiState.value.copy(serverUrl = url)
    }

    fun updateRecordInterval(interval: Int) {
        _uiState.value = _uiState.value.copy(recordInterval = interval)
    }

    fun updateDeviceName(name: String) {
        _uiState.value = _uiState.value.copy(deviceName = name)
    }

    fun saveSettings() {
        viewModelScope.launch {
            deviceStateManager.saveServerUrl(_uiState.value.serverUrl)
            deviceStateManager.saveRecordInterval(_uiState.value.recordInterval)
            deviceStateManager.saveDeviceName(_uiState.value.deviceName)
            GatewayDetector.saveServerUrl(context, _uiState.value.serverUrl)
            _uiState.value = _uiState.value.copy(isSaved = true)
        }
    }

    fun resetServerToDefault() {
        _uiState.value = _uiState.value.copy(serverUrl = DeviceStateManager.DEFAULT_SERVER_URL)
    }
}
