package com.screenplan.agent.data.local

data class TrackerConfig(
    val recordIntervalMinutes: Int = 3,
    val learningApps: List<String> = emptyList(),
    val entertainmentApps: List<String> = emptyList()
)

class ConfigManager {

    fun getDefaultConfig(): TrackerConfig {
        return TrackerConfig(
            recordIntervalMinutes = 3,
            learningApps = LEARNING_APPS,
            entertainmentApps = ENTERTAINMENT_APPS
        )
    }

    fun getMergedConfig(customLearning: List<String> = emptyList(),
                        customEntertainment: List<String> = emptyList(),
                        intervalOverride: Int? = null): TrackerConfig {
        val learning = if (customLearning.isNotEmpty()) customLearning else LEARNING_APPS
        val entertainment = if (customEntertainment.isNotEmpty()) customEntertainment else ENTERTAINMENT_APPS
        val interval = intervalOverride ?: 3
        return TrackerConfig(
            recordIntervalMinutes = interval,
            learningApps = learning,
            entertainmentApps = entertainment
        )
    }

    companion object {
        val LEARNING_APPS = listOf(
            "com.google.android.apps.docs", "Docs",
            "com.microsoft.office.word", "Word",
            "com.microsoft.office.excel", "Excel",
            "com.microsoft.office.powerpoint", "PowerPoint",
            "com.microsoft.office.outlook", "Outlook",
            "com.google.android.apps.docs.editors.docs", "Google Docs",
            "com.google.android.apps.docs.editors.sheets", "Google Sheets",
            "com.google.android.apps.docs.editors.slides", "Google Slides",
            "com.microsoft.onenote", "OneNote",
            "com.evernote", "Evernote",
            "com.notion.id", "Notion",
            "com.ichi2.anki", "Anki",
            "com.duolingo", "Duolingo",
            "com.zhiliaoapp.musically", "TikTok",
            "com.quora.android", "Quora",
            "com.medium.reader", "Medium",
            "com.amazon.kindle", "Kindle",
            "com.google.android.apps.books", "Google Books",
            "com.github.android", "GitHub",
            "org.mozilla.firefox", "Firefox",
            "com.android.chrome", "Chrome",
            "com.microsoft.emmx", "Edge",
            "com.brave.browser", "Brave",
            "com.opera.browser", "Opera",
            "com.opera.mini.native", "Opera Mini",
            "com.kiwibrowser.browser", "Kiwi Browser",
            "org.wikipedia", "Wikipedia",
            "com.wolfram.android.alphapro", "Wolfram Alpha",
            "com.desmos.calculator", "Desmos",
            "com.symbolab.app", "Symbolab",
            "com.mathway.android", "Mathway"
        )

        val ENTERTAINMENT_APPS = listOf(
            "com.tencent.mm", "WeChat",
            "com.tencent.mobileqq", "QQ",
            "com.zhiliaoapp.musically", "TikTok",
            "com.ss.android.ugc.aweme", "Douyin",
            "com.sina.weibo", "Weibo",
            "com.twitter.android", "X",
            "com.instagram.android", "Instagram",
            "com.reddit.frontpage", "Reddit",
            "com.discord", "Discord",
            "org.telegram.messenger", "Telegram",
            "com.facebook.katana", "Facebook",
            "com.google.android.youtube", "YouTube",
            "com.netflix.mediaclient", "Netflix",
            "com.bilibili.app.in", "bilibili",
            "com.spotify.music", "Spotify",
            "com.valvesoftware.android.steam.community", "Steam",
            "com.mojang.minecraftpe", "Minecraft",
            "com.tencent.ig", "PUBG",
            "com.dts.freefireth", "Free Fire",
            "com.supercell.clashofclans", "Clash of Clans",
            "com.nianticlabs.pokemongo", "Pokemon GO",
            "com.epicgames.fortnite", "Fortnite",
            "com.netease.cloudmusic", "NetEase Cloud Music",
            "com.kugou.android", "Kugou",
            "com.tencent.qqmusic", "QQ Music",
            "com.douyu.xl.douyutv", "Douyu",
            "air.tv.douyu.android", "Douyu TV",
            "com.douban.frodo", "Douban",
            "com.zhihu.android", "Zhihu",
            "com.xingin.xhs", "Xiaohongshu",
            "com.ss.android.article.news", "Toutiao"
        )
    }
}
