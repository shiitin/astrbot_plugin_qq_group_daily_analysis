#!/usr/bin/env python3
"""把「支持报告语言的模板名单」从唯一真源同步到 _conf_schema.json。

**唯一真源**：`src/shared/report_language.py` 的 `LANGUAGE_AWARE_TEMPLATES`。
设置项 `report_language` 的 `visible_when.report_template` 由本脚本写入，避免两边各改一次
（漏改的后果：设置项不显示但生效，或显示了却不生效）。

新增一个支持报告语言的模板时：
1. 模板自己内建语言字典（骨架文案 / 页面语言声明 / 字体优先级随 REPORT_LANG 切换）；
2. 把模板名加进 `LANGUAGE_AWARE_TEMPLATES`；
3. 跑本脚本（`python scripts/sync_report_language_templates.py`），或直接跑测试——
   `tests/test_report_language.py::test_schema_visible_when_matches_code` 会提示你跑。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.report_language import LANGUAGE_AWARE_TEMPLATES  # noqa: E402

SCHEMA = ROOT / "_conf_schema.json"


def main() -> int:
    """同步 visible_when 名单；返回 0 表示（同步后）一致，1 表示读取失败。"""
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:  # pragma: no cover - 只在文件损坏时触发
        print(f"读取 {SCHEMA} 失败：{exc}")
        return 1

    item = schema.get("basic", {}).get("items", {}).get("report_language")
    if item is None:
        print("_conf_schema.json 里找不到 basic.items.report_language")
        return 1

    wanted = list(LANGUAGE_AWARE_TEMPLATES)
    visible_when = item.setdefault("visible_when", {})
    current = list(visible_when.get("report_template") or [])
    if current == wanted:
        print(f"已是最新：visible_when.report_template = {current}")
        return 0

    visible_when["report_template"] = wanted
    SCHEMA.write_text(
        json.dumps(schema, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
    )
    print(f"已同步：{current} -> {wanted}（写入 {SCHEMA}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
