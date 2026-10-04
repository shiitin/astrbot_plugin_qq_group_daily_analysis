import { describe, expect, it } from "vitest";

import { resolveOptionLabel } from "../optionLabels";

describe("resolveOptionLabel", () => {
  it("配了标签就显示标签（配置值仍是原始值）", () => {
    const labels = { "zh-Hans": "简体中文", ja: "日本語" };
    expect(resolveOptionLabel("zh-Hans", labels)).toBe("简体中文");
    expect(resolveOptionLabel("ja", labels)).toBe("日本語");
  });

  it("没配标签、标签为空、或整份标签缺失时回退到原始值", () => {
    expect(resolveOptionLabel("zh-Hant", { "zh-Hans": "简体中文" })).toBe("zh-Hant");
    expect(resolveOptionLabel("en", { en: "   " })).toBe("en");
    expect(resolveOptionLabel("auto", undefined)).toBe("auto");
  });
});
