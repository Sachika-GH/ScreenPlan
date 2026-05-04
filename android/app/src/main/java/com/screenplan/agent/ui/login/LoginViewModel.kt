package com.screenplan.agent.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.screenplan.agent.data.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val isLoading: Boolean = false,
    val isLoggedIn: Boolean = false,
    val error: String? = null,
    val successMessage: String? = null
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    init {
        _uiState.value = _uiState.value.copy(isLoggedIn = authRepository.isLoggedIn())
    }

    fun login(email: String, password: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = authRepository.login(email, password)
            result.fold(
                onSuccess = {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isLoggedIn = true,
                        successMessage = "Login successful"
                    )
                },
                onFailure = {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = it.message ?: "Login failed"
                    )
                }
            )
        }
    }

    fun register(familyName: String, email: String, password: String, displayName: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = authRepository.register(familyName, email, password, displayName)
            result.fold(
                onSuccess = {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isLoggedIn = true,
                        successMessage = "Registration successful"
                    )
                },
                onFailure = {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = it.message ?: "Registration failed"
                    )
                }
            )
        }
    }

    fun registerDevice(name: String) {
        viewModelScope.launch {
            val result = authRepository.registerDevice(name)
            result.fold(
                onSuccess = { deviceId ->
                    _uiState.value = _uiState.value.copy(
                        successMessage = "Device registered (ID: $deviceId)"
                    )
                },
                onFailure = {
                    _uiState.value = _uiState.value.copy(
                        error = it.message ?: "Device registration failed"
                    )
                }
            )
        }
    }

    fun checkLogin() {
        _uiState.value = _uiState.value.copy(isLoggedIn = authRepository.isLoggedIn())
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
