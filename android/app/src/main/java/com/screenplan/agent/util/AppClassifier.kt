package com.screenplan.agent.util

import com.screenplan.agent.model.AppCategory
import com.screenplan.agent.data.local.ConfigManager
import com.screenplan.agent.data.local.TrackerConfig

class AppClassifier @javax.inject.Inject constructor(private val configManager: ConfigManager) {

    fun classify(packageName: String, appName: String, config: TrackerConfig? = null): AppCategory {
        val cfg = config ?: configManager.getDefaultConfig()
        val nameLower = appName.lowercase()
        val pkgLower = packageName.lowercase()

        for (learnApp in cfg.learningApps) {
            val la = learnApp.lowercase()
            if (pkgLower.contains(la) || nameLower.contains(la) || la in pkgLower || la in nameLower) {
                return AppCategory.LEARNING
            }
        }

        for (entApp in cfg.entertainmentApps) {
            val ea = entApp.lowercase()
            if (pkgLower.contains(ea) || nameLower.contains(ea) || ea in pkgLower || ea in nameLower) {
                return AppCategory.ENTERTAINMENT
            }
        }

        return AppCategory.OTHER
    }
}
