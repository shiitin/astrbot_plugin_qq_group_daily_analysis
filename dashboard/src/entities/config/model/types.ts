export type SchemaFieldType =
  | "string"
  | "int"
  | "float"
  | "bool"
  | "list"
  | "object"
  | "template_list"
  | "text"
  | "file"
  | string;

export interface SchemaFieldItem {
  type: SchemaFieldType;
  description?: string;
  hint?: string;
  default?: unknown;
  options?: Array<string | number>;
  /**
   * 选项的显示名：键为 `options` 里的原始值，值为面板上显示的文字。
   * 只影响显示，配置里存的仍是原始值（原生按键式表单不支持，会照旧显示原始值）。
   */
  option_labels?: Record<string, string>;
  /** 条件显示依赖：声明的字段当前值命中数组内任一值时才显示本字段（仅插件自带面板支持） */
  visible_when?: Record<string, Array<string | number | boolean>>;
  items?: SchemaFieldItem | Record<string, SchemaFieldItem>;
  templates?: Record<
    string,
    {
      name?: string;
      description?: string;
      display_item?: string;
      items?: Record<string, SchemaFieldItem>;
    }
  >;
  [key: string]: unknown;
}

export interface SchemaGroupItem {
  description: string;
  type: "object";
  hint?: string;
  items: Record<string, SchemaFieldItem>;
  [key: string]: unknown;
}

export type PluginSchema = Record<string, SchemaGroupItem>;

export interface PluginConfigData {
  config: Record<string, Record<string, unknown>>;
  schema: PluginSchema;
}
