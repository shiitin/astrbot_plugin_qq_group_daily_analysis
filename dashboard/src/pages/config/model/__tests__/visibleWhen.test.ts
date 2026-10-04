import { describe, expect, it } from "vitest";
import { isFieldVisible, resolveDependencyValue } from "../useConfigViewModel";
import type { SchemaFieldItem } from "../../../../entities/config/model/types";

const field = (extra: Partial<SchemaFieldItem> = {}) =>
  ({ type: "string", ...extra }) as SchemaFieldItem;

describe("visible_when 条件显示", () => {
  it("未声明 visible_when 的字段恒显示", () => {
    expect(isFieldVisible(field(), { basic: { report_template: "scrapbook" } })).toBe(true);
  });

  it("条件命中（裸字段名跨分组解析）时显示", () => {
    const item = field({ visible_when: { report_template: ["HatsuneMiku"] } });
    expect(isFieldVisible(item, { basic: { report_template: "HatsuneMiku" } })).toBe(true);
  });

  it("条件未命中时隐藏", () => {
    const item = field({ visible_when: { report_template: ["HatsuneMiku"] } });
    expect(isFieldVisible(item, { basic: { report_template: "scrapbook" } })).toBe(false);
  });

  it("支持 “分组.字段” 写法", () => {
    const item = field({ visible_when: { "basic.report_template": ["HatsuneMiku"] } });
    expect(isFieldVisible(item, { basic: { report_template: "HatsuneMiku" } })).toBe(true);
    expect(isFieldVisible(item, { t2i_rendering: {} })).toBe(false);
  });

  it("依赖字段缺失时按未命中处理（隐藏）", () => {
    const item = field({ visible_when: { report_template: ["HatsuneMiku"] } });
    expect(isFieldVisible(item, {})).toBe(false);
  });

  it("invisible 优先级高于 visible_when", () => {
    const item = field({ invisible: true, visible_when: { report_template: ["HatsuneMiku"] } });
    expect(isFieldVisible(item, { basic: { report_template: "HatsuneMiku" } })).toBe(false);
  });

  it("多条件需同时命中", () => {
    const item = field({
      visible_when: { report_template: ["HatsuneMiku"], enable_web_report: [true] },
    });
    expect(
      isFieldVisible(item, { basic: { report_template: "HatsuneMiku", enable_web_report: true } }),
    ).toBe(true);
    expect(
      isFieldVisible(item, { basic: { report_template: "HatsuneMiku", enable_web_report: false } }),
    ).toBe(false);
  });

  it("允许值按字符串比较（布尔/数字也能命中）", () => {
    const item = field({ visible_when: { enable_web_report: [true] } });
    expect(isFieldVisible(item, { basic: { enable_web_report: true } })).toBe(true);
  });

  it("空的允许值数组视为不限制", () => {
    const item = field({ visible_when: { report_template: [] } });
    expect(isFieldVisible(item, { basic: { report_template: "scrapbook" } })).toBe(true);
  });
});

describe("resolveDependencyValue", () => {
  it("优先按“分组.字段”取值", () => {
    expect(resolveDependencyValue({ basic: { report_template: "ATRI" } }, "basic.report_template")).toBe(
      "ATRI",
    );
  });

  it("裸字段名跨分组查找", () => {
    expect(resolveDependencyValue({ t2i_rendering: {}, basic: { report_template: "hack" } }, "report_template")).toBe(
      "hack",
    );
  });
});
