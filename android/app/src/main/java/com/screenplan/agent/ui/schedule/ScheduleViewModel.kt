package com.screenplan.agent.ui.schedule

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.screenplan.agent.data.repository.ScheduleRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ScheduleUiState(
    val isLoading: Boolean = false,
    val isGenerating: Boolean = false,
    val planMarkdown: String? = null,
    val error: String? = null,
    val generatedDate: String? = null,
    val generatedTime: String? = null
)

@HiltViewModel
class ScheduleViewModel @Inject constructor(
    private val scheduleRepository: ScheduleRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ScheduleUiState())
    val uiState: StateFlow<ScheduleUiState> = _uiState.asStateFlow()

    init {
        loadLatestSchedule()
    }

    fun loadLatestSchedule() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = scheduleRepository.getLatestSchedule()
            result.fold(
                onSuccess = { schedule ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        planMarkdown = schedule.planMarkdown,
                        generatedDate = schedule.date,
                        generatedTime = schedule.generatedAt
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.message
                    )
                }
            )
        }
    }

    fun generateSchedule() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isGenerating = true, error = null)
            val result = scheduleRepository.generateSchedule()
            result.fold(
                onSuccess = { schedule ->
                    _uiState.value = _uiState.value.copy(
                        isGenerating = false,
                        planMarkdown = schedule.planMarkdown,
                        generatedDate = schedule.date,
                        generatedTime = schedule.generatedAt
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isGenerating = false,
                        error = e.message
                    )
                }
            )
        }
    }
}
