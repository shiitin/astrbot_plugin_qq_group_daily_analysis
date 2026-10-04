"""报告语言（report language）支持。

报告语言同时作用于两处：

1. **报告产物（模板）**：由渲染上下文传入 ``report_language``，模板侧自解释
   （骨架文案、页面语言声明、字体优先级）。``auto`` 时不传值，保持历史行为。
2. **LLM 输出语言**：在提交 LLM 前追加一段语言指令（本模块负责）。

设计约束（重要）：

- ``auto``（默认）表示**自动判断**：按本次分析的**群聊消息正文**判定语言（某一语言占
  有语言证据的消息数 > 70% 才判），证据不足时不干预、保持历史行为。昵称、贴纸、链接、
  @提及、CQ 码等非正文内容在判定前已被剥离，不会把整群带偏。
- 语言指令必须显式保护"引用原文"与昵称：引用群友的原话一字不改（含原有语言、
  错别字、标点、表情字符），昵称/群名/链接/JSON 字段名保持原文。
  报告语言只作用于解说文案（标题、点评、总结等），不作用于引用内容。
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable

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

#: 自动检测上下文：一次分析任务内由消息清洗层写入，供 LLM 注入与模板渲染共用
_DETECTED_LANGUAGE: ContextVar[str | None] = ContextVar(
    "report_language_detected", default=None
)

#: 判定阈值（保守优先：证据不足时返回 None，回到历史行为，不乱猜）
#: 某一语言占比必须**高于**该比例才判定——混合语群不猜。
_LANGUAGE_SHARE_THRESHOLD = 0.70
#: 参与判定的「有语言证据」消息数下限与语言字符数下限（样本太小不判）
_MIN_VOTING_MESSAGES = 3
_MIN_LANGUAGE_CHARS = 20

#: 正文里的非正文噪音：贴纸/图片等占位行、链接、@提及、CQ 码、方括号占位词。
#: 这些内容经常夹带外语（昵称是三个平假名、贴纸名是英文），必须先剥掉再判语言。
_URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_CQ_CODE_PATTERN = re.compile(r"\[CQ:[^\]]*\]", re.IGNORECASE)
_BRACKET_PLACEHOLDER_PATTERN = re.compile(r"\[[^\[\]]{1,16}\]")
_AT_MENTION_PATTERN = re.compile(
    r"@(?:[A-Za-z0-9_.\-]{1,32}|[\u3040-\u30ff\u3130-\u318f\uac00-\ud7af]{1,16})"
)
#: 整行是媒体占位（Telegram 历史里形如 "Sticker: 😋"）→ 整行丢掉
_MEDIA_LINE_PATTERN = re.compile(
    r"^\s*(?:sticker|gif|image|photo|video|audio|voice|record|file|document"
    r"|animation|emoji|contact|location)s?\s*[:：]",
    re.IGNORECASE,
)

#: 简繁特征字对（简体 繁体，均为常用高频且互不通用的字）：用于中文内部区分简繁
_SIMPLIFIED_TRADITIONAL_PAIRS = (
    "们們 这這 说說 国國 后後 么麼 会會 来來 时時 个個 为為 对對 开開 关關 书書 车車 长長 门門 问問 间間 见見"
    " 东東 风風 飞飛 马馬 鸟鳥 鱼魚 电電 话話 语語 请請 谢謝 爱愛 号號 数數 无無 应應 尔爾 头頭 发髮 让讓"
    " 点點 过過 还還 进進 运運 动動 学學 觉覺 与與 万萬 亿億 众眾 体體 军軍 农農 识識 记記 论論 读讀 谁誰"
    " 课課 买買 卖賣 钱錢 银銀 铁鐵 钢鋼 药藥 医醫 图圖 团團 员員 场場 坏壞 块塊 认認 单單 兰蘭 兴興 养養"
    " 忆憶 习習 续續 断斷 网網 织織 级級 约約 给給 结結 终終 经經 统統 绿綠 红紅 纪紀 货貨 达達 迁遷 选選"
    " 适適 针針 钟鐘 锁鎖 链鏈 镜鏡 队隊 阳陽 阴陰 际際 陆陸 陈陳 难難 雾霧 顺順 须須 顾顧 饮飲 饭飯 馆館"
    " 驾駕 验驗 麦麥 黄黃 齐齊 龙龍 龟龜 鸡雞 猪豬 猫貓 汉漢 举舉 义義 乐樂 书書 云雲 亚亞 产產 亲親 儿兒"
)
_SIMPLIFIED_ONLY = frozenset(
    pair[0] for pair in _SIMPLIFIED_TRADITIONAL_PAIRS.split() if len(pair) == 2
)
_TRADITIONAL_ONLY = frozenset(
    pair[1] for pair in _SIMPLIFIED_TRADITIONAL_PAIRS.split() if len(pair) == 2
)


def _count_scripts(text: str) -> dict[str, int]:
    """统计文本里各类文字的数量（假名/汉字/拉丁/谚文）。

    Args:
        text: 待统计文本。

    Returns:
        形如 ``{"kana": int, "cjk": int, "latin": int, "hangul": int}`` 的计数。
    """
    counts = {"kana": 0, "cjk": 0, "latin": 0, "hangul": 0}
    for ch in text:
        code = ord(ch)
        if 0x3040 <= code <= 0x30FF or 0x31F0 <= code <= 0x31FF:
            counts["kana"] += 1
        elif 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:
            counts["cjk"] += 1
        elif 0xAC00 <= code <= 0xD7AF:
            counts["hangul"] += 1
        elif ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
            counts["latin"] += 1
    return counts


def _detect_chinese_variant(text: str) -> str:
    """区分简体/繁体：按特征字计数，证据不足时按简体（历史默认）。

    Args:
        text: 中文文本。

    Returns:
        ``zh-Hant`` 或 ``zh-Hans``。
    """
    simplified = sum(1 for ch in text if ch in _SIMPLIFIED_ONLY)
    traditional = sum(1 for ch in text if ch in _TRADITIONAL_ONLY)
    if traditional >= 3 and traditional > simplified:
        return "zh-Hant"
    return "zh-Hans"


def clean_message_body(text: str) -> str:
    """剥离正文里的非正文噪音，只留用户真正写下的字。

    处理对象（这些内容常夹带外语字样，会把整群语言带偏）：

    - 媒体占位整行（Telegram 历史里的 ``Sticker: 😋``）；
    - 链接、``[CQ:...]`` 码、方括号占位词（``[图片]`` / ``[表情]``）；
    - ``@提及``（昵称可能就是三个平假名，但它不是正文语言证据）。

    Args:
        text: 消息原始文本。

    Returns:
        剥离噪音后的正文；无正文时返回空串。
    """
    if not text:
        return ""
    lines: list[str] = []
    for raw_line in text.splitlines() or [text]:
        if _MEDIA_LINE_PATTERN.match(raw_line):
            continue
        line = _URL_PATTERN.sub(" ", raw_line)
        line = _CQ_CODE_PATTERN.sub(" ", line)
        line = _BRACKET_PLACEHOLDER_PATTERN.sub(" ", line)
        line = _AT_MENTION_PATTERN.sub(" ", line)
        if line.strip():
            lines.append(line)
    return " ".join(lines).strip()


def _vote_language(counts: dict[str, int]) -> str | None:
    """按单条正文的字符构成投一票。

    Args:
        counts: ``_count_scripts`` 的计数结果。

    Returns:
        ``ja`` / ``zh`` / ``en``；不足以投票（纯表情、纯数字、谚文等）时返回 ``None``。
    """
    if counts["kana"] > 0:
        # 假名是日文独有的字，中文/英文正文里不会自然出现
        return "ja"
    if counts["hangul"] > 0 and counts["hangul"] >= counts["cjk"] + counts["latin"]:
        # 韩文：没有对应的报告语言，不投票
        return None
    if counts["latin"] > counts["cjk"]:
        return "en"
    if counts["cjk"] > 0:
        return "zh"
    return None


def detect_language_from_messages(texts: Iterable[str]) -> str | None:
    """按群聊消息**正文**自动判断报告语言。

    规则（用户定的口径，保守优先）：

    1. 先剥离非正文噪音（贴纸占位行、链接、@提及、CQ 码、方括号占位词）——昵称/贴纸名
       里的假名或英文都不算语言证据；
    2. 每条有语言证据的正文按字符构成投一票：出现假名 → 日文；拉丁多于汉字 → 英文；
       否则有汉字 → 中文；
    3. **某一语言的票数占比 > 70%** 且样本足够（≥3 条正文、≥20 个语言字符）才判定，
       否则返回 ``None``（混合语群不猜，走历史行为）；
    4. 中文再按简繁特征字区分 ``zh-Hans`` / ``zh-Hant``。

    Args:
        texts: 消息正文（可迭代）。

    Returns:
        检测到的语言代码，或 ``None``（证据不足 / 混合语群）。
    """
    votes = {"zh": 0, "en": 0, "ja": 0}
    bodies: list[str] = []
    language_chars = 0
    for text in texts:
        body = clean_message_body(text)
        if not body:
            continue
        counts = _count_scripts(body)
        chunk_chars = sum(counts.values())
        if chunk_chars == 0:
            continue
        language_chars += chunk_chars
        bodies.append(body)
        vote = _vote_language(counts)
        if vote is not None:
            votes[vote] += 1

    voting_messages = votes["zh"] + votes["en"] + votes["ja"]
    if voting_messages < _MIN_VOTING_MESSAGES or language_chars < _MIN_LANGUAGE_CHARS:
        return None

    best = max(votes, key=lambda key: votes[key])
    if votes[best] <= _LANGUAGE_SHARE_THRESHOLD * voting_messages:
        return None
    if best == "zh":
        return _detect_chinese_variant("".join(bodies))
    return best


def remember_detected_language(language: str | None) -> None:
    """把本次任务的自动检测结果写入上下文（供同一任务后续的注入与渲染读取）。

    Args:
        language: 检测到的语言代码或 ``None``。
    """
    _DETECTED_LANGUAGE.set(language)


def get_detected_language() -> str | None:
    """读取本次任务已检测到的语言（未检测或未命中时为 ``None``）。"""
    return _DETECTED_LANGUAGE.get()


def apply_auto_language_detection(texts: Iterable[str]) -> str | None:
    """按消息文本检测语言并写入上下文，返回检测结果。

    Args:
        texts: 消息文本。

    Returns:
        检测到的语言代码或 ``None``。
    """
    language = detect_language_from_messages(texts)
    remember_detected_language(language)
    return language


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

    ``auto`` 表示**自动判断**：按本次分析任务的群聊消息检测结果决定
    （消息清洗阶段由 ``apply_auto_language_detection`` 写入；未命中或证据不足时为 ``None``，
    即不干预、保持历史行为）。显式配置时直接采用该值。

    Args:
        config_manager: 配置管理器。

    Returns:
        语言代码（zh-Hans / zh-Hant / en / ja）；不干预时返回 ``None``。
    """
    try:
        value = str(config_manager.get_report_language() or "").strip()
    except Exception:  # pragma: no cover - 兼容未实现该方法的测试 Mock
        return None
    if value == AUTO:
        detected = get_detected_language()
        if detected is None or not is_language_aware_template(config_manager):
            return None
        return detected
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
