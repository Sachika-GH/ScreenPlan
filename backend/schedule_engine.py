"""Prompt templates and schedule generation engine."""
from datetime import timedelta

SYSTEM_PROMPT = """你是一位专业的屏幕时间行为分析师。你的任务是根据用户多设备的使用数据和活动时间线，对用户的屏幕使用行为进行深度分析，并提供切实可行的改善建议。

你**不**负责规划用户的日程——你无法获知用户的日历、工作安排和个人偏好，因此不应替用户做决定。你的价值在于从数据中洞察用户的行为模式，像一个客观的顾问一样给予反馈。

## 核心分析维度

1. **屏幕时间与健康**：根据用户首次开始使用设备和最后一次使用设备的时间，推断大致的清醒/睡眠窗口。关注总屏幕时长是否合理。

2. **应用性质判定**：传入数据中的分类标签（learning/entertainment/other）来自客户端的自动分类，**可能存在错误**。你必须根据应用名称的常识认知，独立判断每个 App 的实际性质。例如：
   - "不背单词"是语言学习工具，应归为学习类
   - "哔哩哔哩"可能是学习（教程）也可能是娱乐，需结合使用时长和上下文判断
   - "VS Code""Xcode"是开发工具，归为学习/工作类
   - "微信"偏向通讯工具，"Safari"是浏览器，归为工具/其他类
   你需要在输出中给出你自己的分类判断。

3. **多设备使用模式**：
   - 是否存在多设备同时使用的重叠时段（可能分散注意力）
   - 每个设备的角色分工是否清晰
   - 设备切换频率是否过高

4. **专注度与时间碎片化**：
   - 应用切换频率是否过高
   - 最长连续专注时段有多久
   - 是否存在"切换疲劳"的迹象

5. **时间分布规律**：
   - 哪个时段效率最高
   - 是否有深夜使用的习惯
   - 使用时间是否集中在某些时段

## 输出格式（严格遵循）

使用 Markdown 格式，层次分明。不得使用代码块包裹。所有内容使用中文。

---

### 📊 屏幕时间概览
> 用 1-2 句话概述昨日的屏幕使用总览（总时长、主要设备、你自己判定的学习/娱乐比例），不超过 100 字。

---

### 🏷️ 应用分类（AI 判定）
根据应用名称的常识认知，对所有出现过的应用进行分类。如果你不确定某个应用的类别，标注为"待确认"并给出你的猜测。

格式：
```
**学习类**：不背单词 90min、VS Code 120min、Xcode 60min ...

**娱乐类**：哔哩哔哩 45min、Steam 30min、抖音 20min ...

**工具/其他**：微信 30min、Safari 60min、Finder 15min ...
```

基于你的自主分类，计算并给出学习/娱乐/工具的总时间及占比。

---

### 🔍 行为模式分析
分 2-3 段深入分析用户的使用模式。每段 40-80 字。

可参考的分析角度：
- 是否有明显的"报复性熬夜刷屏"模式？
- 学习时段是否真心投入，还是频繁切到娱乐应用？
- 多设备之间能否形成互补，还是互相干扰？

格式：每段以 `**小标题：**` 开头，后接分析文字。

---

### 😴 睡眠与休息推测
基于用户昨日的首次和末次设备活动时间，推测：
- 大致清醒时间窗口
- 大致睡眠时间窗口
- 睡眠时长是否充足（成人建议 7-8 小时）

如果数据不足以推断睡眠，如实说明。2-3 行即可。

---

### 💡 改善建议（2-3 条）
基于分析结果，给出具体可行的建议。每条 40-70 字。注意：
- 建议必须是用户自己做主、可以实际执行的
- 不要替用户规定具体时间段（如"每天早上 8 点做XXX"）
- 侧重于习惯养成和策略调整，而非具体任务安排

格式：
```
- **建议类别**：具体建议内容。
```

---

### ⚠️ 值得关注
1-2 条需要用户警惕的问题或趋势。这些不是批评，而是值得注意的信号。如无特别问题则写"暂无特别需要关注的问题。"

---

## 格式硬性要求
- 每个 `- ` 项独占一行，项与项之间必须有换行，严禁多个任务挤在同一行。
- 各板块标题（### xxx）上下各留一个空行。
- 各板块间用 `---` 分隔线隔开，分隔线上下也各有一个空行。
- 输出纯 Markdown，不要用 ``` 包裹。
- 使用中文。
- 语气客观、友善，像一位有经验的导师，而非命令式的说教。
"""


def compute_union_duration(timestamps: list, interval_minutes: float) -> tuple:
    """
    Compute union (non-overlapping) duration across all device events.
    Each timestamp represents a time window of interval_minutes.
    
    Returns (union_minutes, sum_minutes)
    """
    if not timestamps:
        return 0.0, 0.0

    interval_seconds = interval_minutes * 60
    intervals = [(ts.timestamp(), ts.timestamp() + interval_seconds) for ts in timestamps]
    intervals.sort(key=lambda x: x[0])

    merged = []
    cur_start, cur_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))

    union_seconds = sum(end - start for start, end in merged)
    union_minutes = round(union_seconds / 60, 1)
    sum_minutes = round(len(timestamps) * interval_minutes, 1)

    return union_minutes, sum_minutes


def build_usage_context(devices: list[dict], union_total: float = None) -> str:
    """Build a text summary of multi-device usage data for the prompt.
    
    Important: Does NOT include client-side category labels (learning/entertainment/other).
    The LLM is expected to classify apps independently based on name alone.
    """
    if not devices:
        return "（暂无使用数据）"

    lines = ["## 昨日多设备使用数据"]
    if union_total is not None:
        total_all = union_total
    else:
        total_all = round(sum(d["total_minutes"] for d in devices), 1)
    lines.append(f"总计使用时间: {total_all} 分钟 ({round(total_all/60, 1)} 小时)")
    lines.append(f"设备数量: {len(devices)} 台")

    for d in devices:
        lines.append(f"\n### {d['device_name']} ({d['platform']})")
        lines.append(f"- 使用时长: {d['total_minutes']} 分钟")

        if d.get("top_apps"):
            lines.append("- 最常用应用及使用时长:")
            for app in d["top_apps"][:5]:
                lines.append(f"  * {app['app_name']}: {app['total_minutes']}分钟")

    return "\n".join(lines)


def build_multi_day_usage_context(multi_day_data: dict) -> str:
    """Build a comprehensive usage summary across multiple days.
    multi_day_data: {date_iso: (devices_list, union_total)} for each day.
    
    Important: Does NOT include client-side category labels. The LLM is expected
    to classify apps independently based on name alone.
    """
    if not multi_day_data:
        return "（暂无使用数据）"

    lines = ["## 近期多设备使用数据"]

    sorted_dates = sorted(multi_day_data.keys())

    for i, day in enumerate(sorted_dates):
        devices, union_total = multi_day_data[day]
        if not devices:
            continue
        label = "昨日" if i == len(sorted_dates) - 1 else f"{day}"
        if union_total is not None:
            total_all = union_total
        else:
            total_all = round(sum(d["total_minutes"] for d in devices), 1)
        lines.append(f"\n### {label}")
        lines.append(f"- 总使用时间: {total_all} 分钟 ({round(total_all/60, 1)} 小时)")
        lines.append(f"- 活跃设备: {len(devices)} 台")
        for d in devices:
            lines.append(f"  * {d['device_name']} ({d['platform']}): {d['total_minutes']}分钟")

    # Most recent day's detailed apps
    if sorted_dates:
        latest_date = sorted_dates[-1]
        latest_devices, _ = multi_day_data[latest_date]
        if latest_devices:
            lines.append("\n### 最近一日（昨日）详细数据")
            for d in latest_devices:
                lines.append(f"\n**{d['device_name']}** ({d['platform']})")
                lines.append(f"- 使用时长: {d['total_minutes']} 分钟")
                if d.get("top_apps"):
                    lines.append("- 最常用应用及使用时长:")
                    for app in d["top_apps"][:5]:
                        lines.append(f"  * {app['app_name']}: {app['total_minutes']}分钟")

    return "\n".join(lines)


def build_user_prompt(
    usage_context: str,
    calendar_text: str = "",
    is_workday: bool = True,
    learning_hours_goal: int = 4,
) -> str:
    """Build the complete user prompt for LLM behavior analysis."""
    from datetime import date

    day_type = "工作日" if is_workday else "周末/休息日"
    today = date.today()

    prompt = f"""今天日期：{today.isoformat()} ({day_type})

{usage_context}

## 分析要求
- 今天类型：{day_type}
- 请**不要**规划用户的今日日程——你没有用户的日历和工作安排信息。
- 传入数据中的分类标签来自客户端自动匹配，**可能不准确**。你必须根据应用名称的常识认知，自主判定每个 App 的性质（学习/娱乐/工具），并在输出中给出你自己的分类和占比计算。
- 如果数据不足（如数据量很少），请如实说明，不要编造结论。

请根据以上信息，生成本次屏幕时间行为分析报告。"""
    return prompt
