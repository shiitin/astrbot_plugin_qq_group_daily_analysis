"""报告语言（report language）支持。

报告语言同时作用于两处：

1. **报告产物（模板）**：由渲染上下文传入 ``report_language``，模板侧自解释
   （骨架文案、页面语言声明、字体优先级）。``auto`` 时不传值，保持历史行为。
2. **LLM 输出语言**：在提交 LLM 前追加一段语言指令（本模块负责）。

设计约束（重要）：

- ``auto``（默认）时**不追加任何指令**，行为与历史版本完全一致。
- 语言指令必须显式保护"引用原文"与昵称：引用群友的原话一字不改（含原有语言、
  错别字、标点、表情字符），昵称/群名/链接/JSON 字段名保持原文。
  报告语言只作用于解说文案（标题、点评、总结等），不作用于引用内容。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

#: 默认值：保持历史行为（骨架简体、页面声明跟随渲染环境、LLM 自由发挥）
AUTO = "auto"


class ReportLanguageConfig(Protocol):
    """报告语言读取所需的最小配置接口（避免依赖具体 ConfigManager 实现）。"""

    def get_report_language(self) -> str:
        """返回报告语言配置值（auto/zh-Hans/zh-Hant/en）。"""
        ...


#: 允许的报告语言（与 _conf_schema.json 的 options 保持一致）
REPORT_LANGUAGE_OPTIONS: tuple[str, ...] = (AUTO, "zh-Hans", "zh-Hant", "en", "ja")

#: 已完成多语言适配的模板白名单：只有当前报告模板在此列表内，报告语言才会生效。
#: 模板骨架文案 / 页面语言声明 / 字体 / 导航短名都要随语言切换，未适配的模板套上语言
#: 只会出现「骨架中文 + 解说英文」的半成品，所以这里做门禁。
#: 新增适配模板时**两处都要加**：本常量 + `_conf_schema.json` 中 report_language 的
#: visible_when 列表（保证「设置项可见」与「设置项生效」一致）。
LANGUAGE_AWARE_TEMPLATES: tuple[str, ...] = ("HatsuneMiku",)

#: 幂等标记：同一段提示词只注入一次（重试/多段调用不会重复追加）
REPORT_LANGUAGE_MARK = "【报告语言】"

_LANGUAGE_NAMES: dict[str, str] = {
    "zh-Hans": "简体中文",
    "zh-Hant": "繁体中文",
    "en": "English",
    "ja": "日本語",
}

_LANGUAGE_INSTRUCTION = """【报告语言】
本次报告的解说文案请使用{language}（{code}）撰写，语言要求优先于提示词中的默认语言示例。

以下内容不受报告语言影响，必须原样保留（禁止翻译、转写、润色或改写）：
1. 引用群友的原话（金句等）——一字不改，包括其原有语言、错别字、标点与表情字符；
2. 群友昵称、群名、@ 提及、链接、代码——保持原文；
3. JSON 的字段名与结构——不要改动，只按上述语言书写字段值的解说文案。

报告语言只作用于你撰写的解说文案（标题、点评、总结等），不作用于上述引用内容。"""


def current_report_template(config_manager: object) -> str | None:
    """读取当前报告模板名。

    Args:
        config_manager: 配置管理器（缺少该方法时视为未知环境）。

    Returns:
        模板名；读取失败或为空时返回 ``None``，表示未知（不做语言门禁）。
    """
    getter = getattr(config_manager, "get_report_template", None)
    if not callable(getter):
        return None
    try:
        value = str(getter() or "").strip()
    except Exception:  # pragma: no cover - 兼容未实现该方法的测试 Mock
        return None
    return value or None


def is_language_aware_template(config_manager: object) -> bool:
    """当前报告模板是否已完成多语言适配。

    Args:
        config_manager: 配置管理器。

    Returns:
        模板名已知时按 ``LANGUAGE_AWARE_TEMPLATES`` 判定；模板名未知（如离线调试/单测
        Mock 未提供模板信息）时返回 ``True``，保持历史行为、不误伤既有调用方。
    """
    template = current_report_template(config_manager)
    if template is None:
        return True
    return template in LANGUAGE_AWARE_TEMPLATES


def resolve_report_language(config_manager: ReportLanguageConfig) -> str | None:
    """读取并校验报告语言配置。

    Args:
        config_manager: 配置管理器。

    Returns:
        显式选择的语言代码（zh-Hans / zh-Hant / en / ja）；
        ``auto``、空值、读取失败或当前模板未适配多语言时返回 ``None``，表示不干预（历史行为）。
    """
    try:
        value = str(config_manager.get_report_language() or "").strip()
    except Exception:  # pragma: no cover - 兼容未实现该方法的测试 Mock
        return None
    if value not in _LANGUAGE_NAMES:
        return None
    if not is_language_aware_template(config_manager):
        return None
    return value


def build_language_instruction(language: str) -> str:
    """构造追加到提示词末尾的语言指令。"""
    return _LANGUAGE_INSTRUCTION.format(
        language=_LANGUAGE_NAMES[language],
        code=language,
    )


_EN_MONTHS: tuple[str, ...] = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def format_report_date(language: str | None, moment: datetime | None = None) -> str:
    """按报告语言格式化报告日期。

    - auto / zh-Hans / zh-Hant：沿用历史格式 ``YYYY年MM月DD日``；
    - ja：``YYYY年M月D日``（日文习惯不补前导零）；
    - en：``Month D, YYYY``（不用 strftime 的 %B，避免受系统 locale 影响）。

    Args:
        language: 报告语言（``None`` 表示 auto）。
        moment: 指定时间，默认当前时间。

    Returns:
        格式化后的日期字符串。
    """
    moment = moment or datetime.now()
    if language == "en":
        return f"{_EN_MONTHS[moment.month - 1]} {moment.day}, {moment.year}"
    if language == "ja":
        # 日文习惯不补前导零
        return f"{moment.year}年{moment.month}月{moment.day}日"
    return moment.strftime("%Y年%m月%d日")


def apply_report_language(prompt: str, config_manager: ReportLanguageConfig) -> str:
    """按配置给提示词追加语言指令（幂等）。

    Args:
        prompt: 原始提示词。
        config_manager: 配置管理器。

    Returns:
        处理后的提示词；``auto``（或已注入过）时原样返回。
    """
    if not prompt or REPORT_LANGUAGE_MARK in prompt:
        return prompt
    language = resolve_report_language(config_manager)
    if language is None:
        return prompt
    return f"{prompt}\n\n{build_language_instruction(language)}"
