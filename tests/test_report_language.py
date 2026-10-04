"""报告语言（report_language）单元测试。

覆盖：配置解析、模板门禁、提示词注入幂等、日期格式化。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.shared.report_language import (
    LANGUAGE_AWARE_TEMPLATES,
    apply_auto_language_detection,
    apply_report_language,
    current_report_template,
    detect_language_from_messages,
    format_report_date,
    get_detected_language,
    is_language_aware_template,
    remember_detected_language,
    resolve_report_language,
)


class FakeConfigManager:
    """最小配置管理器替身。"""

    def __init__(
        self, language: str = "auto", template: str | None = "HatsuneMiku"
    ) -> None:
        self.language = language
        self.template = template

    def get_report_language(self) -> str:
        return self.language

    def get_report_template(self) -> str:
        if self.template is None:
            raise RuntimeError("模板读取失败")
        return self.template


class NoTemplateGetter(FakeConfigManager):
    """未实现 get_report_template 的旧 Mock（模拟未知环境）。"""

    get_report_template = None  # type: ignore[assignment]


class NoLanguageGetter:
    """未实现 get_report_language 的旧 Mock。"""


@pytest.mark.parametrize("language", ["zh-Hans", "zh-Hant", "en", "ja"])
def test_resolve_explicit_language(language: str) -> None:
    assert resolve_report_language(FakeConfigManager(language=language)) == language


def test_resolve_auto_returns_none() -> None:
    assert resolve_report_language(FakeConfigManager(language="auto")) is None


def test_resolve_invalid_returns_none() -> None:
    assert resolve_report_language(FakeConfigManager(language="fr")) is None
    assert resolve_report_language(FakeConfigManager(language="")) is None


def test_resolve_without_language_getter_returns_none() -> None:
    assert resolve_report_language(NoLanguageGetter()) is None  # type: ignore[arg-type]


def test_gate_skips_language_for_unadapted_template() -> None:
    """未适配多语言的模板即使配了语言也不生效（避免骨架中文 + 解说英文）。"""
    cfg = FakeConfigManager(language="en", template="scrapbook")
    assert resolve_report_language(cfg) is None
    assert is_language_aware_template(cfg) is False


def test_gate_allows_language_aware_template() -> None:
    cfg = FakeConfigManager(language="en", template=LANGUAGE_AWARE_TEMPLATES[0])
    assert resolve_report_language(cfg) == "en"
    assert is_language_aware_template(cfg) is True


def test_gate_unknown_template_environment_is_permissive() -> None:
    """模板名未知（旧 Mock / 读取异常）时不做门禁，保持历史行为。"""
    assert is_language_aware_template(NoTemplateGetter()) is True
    assert resolve_report_language(NoTemplateGetter(language="en")) == "en"
    assert current_report_template(FakeConfigManager(template=None)) is None


def test_apply_injects_once_and_is_idempotent() -> None:
    cfg = FakeConfigManager(language="en")
    once = apply_report_language("原文", cfg)
    assert "【报告语言】" in once and "English" in once
    assert apply_report_language(once, cfg) == once


def test_apply_keeps_prompt_for_auto_and_unadapted_template() -> None:
    assert apply_report_language("原文", FakeConfigManager(language="auto")) == "原文"
    unadapted = FakeConfigManager(language="en", template="ATRI")
    assert apply_report_language("原文", unadapted) == "原文"


def test_apply_empty_prompt_untouched() -> None:
    assert apply_report_language("", FakeConfigManager(language="en")) == ""


def test_instruction_protects_quotes_and_nicknames() -> None:
    """语言指令必须显式保护引用原文与昵称（金句/昵称不得被翻译）。"""
    text = apply_report_language("原文", FakeConfigManager(language="ja"))
    assert "禁止翻译" in text
    assert "昵称" in text
    assert "JSON" in text


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (None, "2026年10月04日"),
        ("auto", "2026年10月04日"),
        ("zh-Hans", "2026年10月04日"),
        ("zh-Hant", "2026年10月04日"),
        ("ja", "2026年10月4日"),
        ("en", "October 4, 2026"),
    ],
)
def test_format_report_date(language: str | None, expected: str) -> None:
    assert format_report_date(language, datetime(2026, 10, 4)) == expected


# ---------------------------------------------------------------- auto 自动判断


def test_detect_simplified_chinese() -> None:
    texts = [
        "今天群里好热闹，大家都聊新出的游戏",
        "我也来说两句，这个画风真好看",
        "推荐大家一起玩，晚上联机",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_detect_traditional_chinese() -> None:
    texts = [
        "我們來說說這個新遊戲吧，你們覺得好玩嗎",
        "這裡的畫風真的很美，請大家推薦更多",
        "謝謝大家，我們明天再來討論這個",
    ]
    assert detect_language_from_messages(texts) == "zh-Hant"


def test_detect_japanese() -> None:
    texts = [
        "こんにちは、今日はいい天気ですね",
        "みんなでゲームをしましょう！",
        "このイラスト、とても可愛いと思うよ",
    ]
    assert detect_language_from_messages(texts) == "ja"


def test_detect_english() -> None:
    texts = [
        "Hello everyone, today we played a new game",
        "It was really fun, see you tomorrow",
        "Anyone wants to join the next session tonight?",
    ]
    assert detect_language_from_messages(texts) == "en"


def test_detect_insufficient_evidence_returns_none() -> None:
    assert detect_language_from_messages(["你好", "在吗"]) is None
    assert detect_language_from_messages([]) is None
    # 单一长消息也不够（样本消息数下限）
    assert (
        detect_language_from_messages(
            [
                "今天群里好热闹，大家都聊新出的游戏，我也来说两句，这个画风真好看，推荐一起玩"
            ]
        )
        is None
    )


def test_sticker_line_is_ignored() -> None:
    """Telegram 历史里的「Sticker: 😋」这类占位行没有语言证据，不该投票。"""
    texts = [
        "Sticker: 😋",
        "今天群里好热闹，大家都聊新出的游戏",
        "我也来说两句，这个画风真好看",
        "推荐大家一起玩，晚上联机",
        "Sticker: 🎉",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_kana_nickname_in_mention_does_not_flip_to_japanese() -> None:
    """群友昵称是三个平假名（@みく）时，整群不能被判成日文。"""
    texts = [
        "@みく 你今天怎么不说话",
        "大家都在等你呢，快点回来",
        "刚刚那个活动你参加了吗",
        "回来记得说一声，我们继续聊",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_url_and_cq_noise_is_ignored() -> None:
    texts = [
        "https://example.com/news/hello-world",
        "[CQ:image,file=abc.jpg]",
        "今天群里好热闹，大家都聊新出的游戏",
        "我也来说两句，这个画风真好看",
        "推荐大家一起玩，晚上联机",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_latin_nickname_does_not_flip_to_english() -> None:
    texts = [
        "@MikuFan 你今天怎么不说话",
        "大家都在等你呢，快点回来",
        "刚刚那个活动你参加了吗",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_chinese_group_with_one_japanese_quote_stays_chinese() -> None:
    """汉字为主的群夹一条日文引用（歌名/歌词）仍按中文处理——占比不够 70% 就不换语言。"""
    texts = [
        "今天听了夜に駆ける，感觉不错",
        "大家都在讨论编曲和调教，推荐去听一遍",
        "我觉得这首歌的副歌特别好听",
        "你们平时都听什么歌，说两个来",
        "晚上一起联机吗，我这边有空",
        "刚下班，等下就上来",
        "这个画风确实很好看",
        "我先把作业写完再玩",
        "群里最近好热闹啊",
        "明天见，大家早点睡",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_mixed_group_below_threshold_returns_none() -> None:
    """达不到 70% 的混合语群不猜（返回 None = 不干预，走历史行为）。"""
    texts = [
        "今天群里好热闹啊",
        "我也来说两句",
        "推荐大家一起玩",
        "こんにちは、今日はいい天気ですね",
        "みんなでゲームをしましょう",
        "このイラスト、とても可愛いと思うよ",
    ]
    assert detect_language_from_messages(texts) is None
    # 恰好 70% 也不判（要求「大于 70%」）
    exactly_seventy = [
        "中文消息一",
        "中文消息二",
        "中文消息三",
        "中文消息四",
        "中文消息五",
        "中文消息六",
        "中文消息七",
        *[
            "こんにちは、今日はいい天気ですね",
            "みんなでゲームをしましょう",
            "このイラスト、とても可愛いと思うよ",
        ],
    ]
    assert detect_language_from_messages(exactly_seventy) is None


def test_english_group_with_chinese_smattering_stays_english() -> None:
    texts = [
        "Hello everyone, today we played a new game",
        "It was really fun, see you tomorrow",
        "Anyone wants to join the next session tonight?",
        "I will bring some snacks for the group",
        "我来晚了，抱歉",
    ]
    assert detect_language_from_messages(texts) == "en"


def test_resolve_auto_uses_detected_language() -> None:
    cfg = FakeConfigManager(language="auto")
    remember_detected_language("en")
    assert resolve_report_language(cfg) == "en"
    remember_detected_language("ja")
    assert resolve_report_language(cfg) == "ja"


def test_resolve_auto_without_detection_is_noop() -> None:
    remember_detected_language(None)
    assert resolve_report_language(FakeConfigManager(language="auto")) is None


def test_explicit_language_overrides_detection() -> None:
    remember_detected_language("en")
    assert resolve_report_language(FakeConfigManager(language="zh-Hant")) == "zh-Hant"


def test_apply_auto_detection_writes_context() -> None:
    english = [
        "Hello everyone, today we played a new game",
        "It was really fun, see you tomorrow",
        "Anyone wants to join the next session tonight?",
    ]
    assert apply_auto_language_detection(english) == "en"
    assert get_detected_language() == "en"
    assert apply_auto_language_detection(["你好"]) is None
    assert get_detected_language() is None


def test_detected_language_still_gated_by_template() -> None:
    """自动判断出来的语言同样受模板白名单约束。"""
    remember_detected_language("en")
    assert (
        resolve_report_language(
            FakeConfigManager(language="auto", template="scrapbook")
        )
        is None
    )
