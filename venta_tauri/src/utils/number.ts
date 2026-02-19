export function parseNumberInput(raw: string): number {
  const normalized = raw.trim().replace(",", ".");
  const parsed = Number.parseFloat(normalized);
  if (!Number.isFinite(parsed)) {
    return 0;
  }
  return parsed;
}

export function roundInteger(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.round(value);
}

export function parseIntegerInput(raw: string): number {
  return roundInteger(parseNumberInput(raw));
}

export function formatInteger(value: number): string {
  return String(roundInteger(value));
}

export function formatMoney(value: number): string {
  return `$ ${formatInteger(value)}`;
}
