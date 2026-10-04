/**
 * 配置项选项的显示名。
 *
 * schema 里 `options` 存的是配置真实值（如 `zh-Hans`），`option_labels` 给每个值配一句人话
 * （如「简体中文」）。面板只影响显示，写回配置的仍是原始值；没配标签时照旧显示原始值，
 * 原生按键式表单不支持该键，也会照旧显示原始值。
 */
export function resolveOptionLabel(
  raw: string,
  optionLabels?: Record<string, string>
): string {
  const label = optionLabels?.[raw];
  return label && label.trim() ? label : raw;
}
