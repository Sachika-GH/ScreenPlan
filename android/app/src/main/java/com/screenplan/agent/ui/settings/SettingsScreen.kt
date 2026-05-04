package com.screenplan.agent.ui.settings

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.screenplan.agent.util.UsageStatsHelper
import com.screenplan.agent.util.PermissionHelper

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onNavigateBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    var serverUrl by remember { mutableStateOf(uiState.serverUrl) }
    var interval by remember { mutableStateOf(uiState.recordInterval.toString()) }
    var deviceName by remember { mutableStateOf(uiState.deviceName) }
    var showSaveSnackbar by remember { mutableStateOf(false) }

    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.serverUrl) { serverUrl = uiState.serverUrl }
    LaunchedEffect(uiState.recordInterval) { interval = uiState.recordInterval.toString() }
    LaunchedEffect(uiState.deviceName) { deviceName = uiState.deviceName }
    LaunchedEffect(uiState.isSaved) {
        if (uiState.isSaved) {
            showSaveSnackbar = true
            snackbarHostState.showSnackbar("Settings saved")
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            // Server Section
            Text(
                "Server Configuration",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(modifier = Modifier.height(12.dp))

            OutlinedTextField(
                value = serverUrl,
                onValueChange = { serverUrl = it; viewModel.updateServerUrl(it) },
                label = { Text("Server URL") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri)
            )
            Spacer(modifier = Modifier.height(8.dp))

            TextButton(onClick = { viewModel.resetServerToDefault() }) {
                Text("Reset to default")
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Tracking Settings
            Text(
                "Tracking",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(modifier = Modifier.height(12.dp))

            OutlinedTextField(
                value = interval,
                onValueChange = {
                    interval = it
                    it.toIntOrNull()?.let { intVal ->
                        viewModel.updateRecordInterval(intVal)
                    }
                },
                label = { Text("Record Interval (minutes)") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)
            )

            Spacer(modifier = Modifier.height(12.dp))

            OutlinedTextField(
                value = deviceName,
                onValueChange = { deviceName = it; viewModel.updateDeviceName(it) },
                label = { Text("Device Name") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Permissions Section
            Text(
                "Permissions",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(modifier = Modifier.height(12.dp))

            val usageHelper = remember { UsageStatsHelper(context) }
            val permissionHelper = remember { PermissionHelper(context) }
            var hasUsagePermission by remember { mutableStateOf(usageHelper.hasUsageStatsPermission()) }

            LaunchedEffect(Unit) {
                hasUsagePermission = usageHelper.hasUsageStatsPermission()
            }

            PermissionRow(
                label = "Usage Access",
                description = "Required to detect foreground app",
                isGranted = hasUsagePermission,
                onClick = {
                    context.startActivity(usageHelper.getUsageStatsPermissionIntent())
                }
            )

            Spacer(modifier = Modifier.height(8.dp))

            PermissionRow(
                label = "Battery Optimization",
                description = "Allow background running",
                isGranted = permissionHelper.hasBatteryOptimizationExemption(),
                onClick = {
                    context.startActivity(permissionHelper.getBatteryOptimizationIntent())
                }
            )

            Spacer(modifier = Modifier.height(8.dp))

            PermissionRow(
                label = "Auto Start",
                description = "Launch tracking on boot",
                isGranted = false,
                onClick = {
                    val intent = permissionHelper.getAutoStartIntent(uiState.manufacturer)
                    if (intent != null) {
                        try { context.startActivity(intent) } catch (_: Exception) {}
                    } else {
                        val aiIntent = Intent(Settings.ACTION_SETTINGS)
                        context.startActivity(aiIntent)
                    }
                }
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Device Info
            Text(
                "Device Info",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(modifier = Modifier.height(12.dp))

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    InfoRow("Manufacturer", uiState.manufacturer)
                    InfoRow("Model", uiState.model)
                    InfoRow("Android", uiState.androidVersion)
                    InfoRow("Device ID", uiState.deviceId?.toString() ?: "Not registered")
                }
            }

            Spacer(modifier = Modifier.height(32.dp))

            Button(
                onClick = { viewModel.saveSettings() },
                modifier = Modifier.fillMaxWidth().height(50.dp)
            ) {
                Text("Save Settings")
            }

            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Composable
fun PermissionRow(
    label: String,
    description: String,
    isGranted: Boolean,
    onClick: () -> Unit
) {
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(label, style = MaterialTheme.typography.bodyLarge)
                Text(
                    description,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Icon(
                imageVector = if (isGranted) Icons.Filled.CheckCircle else Icons.Filled.Warning,
                contentDescription = if (isGranted) "Granted" else "Not granted",
                tint = if (isGranted) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.error
            )
        }
    }
}

@Composable
fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium
        )
    }
}
