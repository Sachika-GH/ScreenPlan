"""Prompt templates and schedule generation engine."""
from datetime import timedelta

SYSTEM_PROMPT = """你是一位专业的时间管理与学习规划助手。你的任务是根据用户多设备的使用数据和日历安排，生成一份切实可行的每日计划。

## 核心原则

1. **根据日历安排规划时间**：必须优先避开已有的日历事件时间段，在空闲时间段安排任务。
2. **根据用户习惯调整任务强度**：
   - 如果娱乐时间过多（>40%），应适当减少任务量，增加缓冲时间。
   - 如果学习时间充足且专注度高，可适当增加挑战性任务。
3. **避免理想化计划**：
   - 不要安排过于密集的任务（连续工作时间不超过用户最长专注时长）。
   - 每个任务之间应留 5-15 分钟缓冲。
   - 实际可用的空闲时间不要填满超过 80%。
4. **区分工作日与周末**：
   - 工作日：以日历事件为中心，穿插学习任务。
   - 周末：降低任务强度，以自主学习、复习总结为主。
5. **提供具体可执行的番茄钟建议**。

## 输出格式（严格遵循）

使用 Markdown 格式，层次分明、适合阅读。不得使用代码块包裹。

---
### 📋 今日总览
> 用 1-2 句话概述今天的核心节奏和重点，不超过 100 字。

---
### ⏱ 时间安排
使用可勾选的复选框格式，每行一个时段。日历事件标 ⏰，学习任务标 📖，休息标 ☕。

```
- [ ] HH:MM-HH:MM  ⏰ 日历事件名称
- [ ] HH:MM-HH:MM  📖 学习任务 | 具体建议
- [ ] HH:MM-HH:MM  ☕ 休息/缓冲
```

---
### 🎯 学习重点（2-4条）
使用复选框，每条 30-50 字。列出最重要的学习目标，按优先级排列。

```
- [ ] 具体可执行的学习目标1
- [ ] 具体可执行的学习目标2
```

---
### 💡 行为建议
基于昨日的多设备使用数据给出 2-3 条建议，每条 50-80 字。格式：

```
- 建议类别：具体问题 → 改进方法。
```

---
### 🍅 番茄钟建议
给出具体配置，3-4 行，固定格式：

```
- 单次时长：XX 分钟
- 休息间隔：XX 分钟
- 今日轮次：X 轮
- 执行时段：HH:MM-HH:MM
```

## 格式硬性要求
- 每个 `- [ ]` 项独占一行，项与项之间必须有换行，严禁多个任务挤在同一行。
- 各板块标题（### xxx）上下各留一个空行。
- 各板块间用 `---` 分隔线隔开，分隔线上下也各有一个空行。
- 输出纯 Markdown，不要用 ``` 包裹。
- 使用中文。
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
    """Build a text summary of multi-device usage data for the prompt."""
    if not devices:
        return "（暂无使用数据）"

    lines = ["## 昨日多设备使用情况"]
    if union_total is not None:
        total_all = union_total
    else:
        total_all = round(sum(d["total_minutes"] for d in devices), 1)
    lines.append(f"总计使用时间: {total_all} 分钟 ({round(total_all/60, 1)} 小时)")

    for d in devices:
        lines.append(f"\n### {d['device_name']} ({d['platform']})")
        lines.append(f"- 使用时长: {d['total_minutes']} 分钟")
        lines.append(f"- 学习占比: {d['learning_pct']}%")
        lines.append(f"- 娱乐占比: {d['entertainment_pct']}%")
        lines.append(f"- 其他占比: {d['other_pct']}%")

        if d.get("top_apps"):
            lines.append("- 最常用应用:")
            for app in d["top_apps"][:5]:
                lines.append(f"  * {app['app_name']}: {app['total_minutes']}分钟 ({app['category']})")

    return "\n".join(lines)


def build_user_prompt(
    usage_context: str,
    calendar_text: str = "",
    is_workday: bool = True,
    learning_hours_goal: int = 4,
) -> str:
    """Build the complete user prompt for LLM schedule generation."""
    from datetime import date

    day_type = "工作日" if is_workday else "周末/休息日"
    today = date.today()

    calendar_block = ""
    if calendar_text:
        calendar_block = f"""
## 今日日历安排
{calendar_text}
"""

    prompt = f"""今天日期：{today.isoformat()} ({day_type})

{usage_context}
{calendar_block}
## 用户设置
- 今日类型：{day_type}
- 目标学习时长：{learning_hours_goal} 小时

请根据以上信息，生成今日的完整计划。"""
    return prompt
