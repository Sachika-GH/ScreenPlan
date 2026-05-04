package com.screenplan.agent.ui.dashboard

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.screenplan.agent.util.UsageStatsHelper
import androidx.compose.ui.platform.LocalContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onNavigateToSchedule: () -> Unit,
    onNavigateToSettings: () -> Unit,
    onLogout: () -> Unit,
    viewModel: DashboardViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(Unit) {
        viewModel.refresh()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("ScreenPlan") },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
                    }
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(Icons.Filled.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            // Status Card
            StatusCard(
                isTracking = uiState.isTracking,
                backendOnline = uiState.backendOnline,
                lastSync = uiState.lastSyncTime,
                queueSize = uiState.queueSize
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Tracking Toggle
            Button(
                onClick = {
                    if (!uiState.hasUsageStatsPermission) {
                        val intent = UsageStatsHelper(context).getUsageStatsPermissionIntent()
                        context.startActivity(intent)
                    } else {
                        viewModel.toggleTracking()
                    }
                },
                modifier = Modifier.fillMaxWidth().height(56.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (uiState.isTracking)
                        MaterialTheme.colorScheme.error
                    else
                        MaterialTheme.colorScheme.primary
                ),
                enabled = uiState.hasUsageStatsPermission
            ) {
                Icon(
                    imageVector = if (uiState.isTracking) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(if (uiState.isTracking) "Stop Tracking" else "Start Tracking")
            }

            if (!uiState.hasUsageStatsPermission) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Usage access permission required. Tap to enable.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Stats
            Text(
                "Today's Activity",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                StatCard(
                    label = "Total",
                    value = uiState.todayRecordCount.toString(),
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.weight(1f)
                )
                StatCard(
                    label = "Learning",
                    value = uiState.learningCount.toString(),
                    color = Color(0xFF238636),
                    modifier = Modifier.weight(1f)
                )
                StatCard(
                    label = "Entertainment",
                    value = uiState.entertainmentCount.toString(),
                    color = Color(0xFFDA3633),
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Quick Actions
            Text(
                "Quick Actions",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(modifier = Modifier.height(12.dp))

            OutlinedButton(
                onClick = onNavigateToSchedule,
                modifier = Modifier.fillMaxWidth().height(48.dp)
            ) {
                Icon(Icons.Filled.CalendarMonth, contentDescription = null, modifier = Modifier.size(20.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text("View Schedule")
            }

            Spacer(modifier = Modifier.height(12.dp))

            OutlinedButton(
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth().height(48.dp),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = MaterialTheme.colorScheme.error
                )
            ) {
                Icon(Icons.Filled.Logout, contentDescription = null, modifier = Modifier.size(20.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text("Logout")
            }
        }
    }
}

@Composable
fun StatusCard(
    isTracking: Boolean,
    backendOnline: Boolean,
    lastSync: String?,
    queueSize: Int
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                val dotColor = if (isTracking) Color(0xFF238636) else Color(0xFF8B949E)
                Surface(
                    modifier = Modifier.size(10.dp),
                    shape = MaterialTheme.shapes.extraLarge,
                    color = dotColor
                ) {}
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = if (isTracking) "Tracking Active" else "Tracking Inactive",
                    style = MaterialTheme.typography.titleSmall
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    modifier = Modifier.size(10.dp),
                    shape = MaterialTheme.shapes.extraLarge,
                    color = if (backendOnline) Color(0xFF238636) else Color(0xFFDA3633)
                ) {}
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = if (backendOnline) "Backend Online" else "Backend Offline",
                    style = MaterialTheme.typography.bodySmall
                )
            }
            if (lastSync != null) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Last sync: $lastSync",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            if (queueSize > 0) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Offline queue: $queueSize events",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
    }
}

@Composable
fun StatCard(
    label: String,
    value: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = value,
                style = MaterialTheme.typography.headlineMedium,
                color = color
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
