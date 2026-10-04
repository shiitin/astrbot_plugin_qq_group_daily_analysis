# 简繁判定字表 / 词表（`zh_variant_tables.py`）

本文件为**生成产物**，由 `scripts/gen_zh_variant_tables.py` 从 OpenCC 字典生成，请勿手工修改。

## 许可范围

数据来源为 [OpenCC](https://github.com/BYVoid/OpenCC)（Apache License 2.0）：

- `data/dictionary/TSCharacters.txt`（繁体→简体映射，取其中 1:1 且互不通用的字对）
- `data/dictionary/TWPhrases.txt`（大陆用词 → 台湾用词）
- `data/dictionary/HKPhrases.txt`（→ 香港用词）

依 Apache-2.0 第 4 条，本生成数据同样适用
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)（全文见 `LICENSES/Apache-2.0.txt`）。
本仓库其余代码与资源沿用项目 MIT 许可；上述条款不改变仓库其他部分的许可。

## 署名与来源

- OpenCC 项目：<https://github.com/BYVoid/OpenCC>（Copyright BYVoid 及贡献者，Apache-2.0）

## 本仓库对数据的修改

生成时做了以下加工，**已非 OpenCC 原始数据**：

1. 仅保留 1:1 的简繁特征字映射，剔除一对多歧义字与基本区以外的生僻字；
2. 抽取繁中侧 / 大陆侧用词对，并统一折算为简体形式后存储；
3. 追加生成脚本内的人工补充词表（高频 IT / 生活用词）与粤语常用字（OpenCC 未收录部分）。

生成方式：`python scripts/gen_zh_variant_tables.py`（可用 `--dict-dir` 复用本地 OpenCC 字典目录）。
