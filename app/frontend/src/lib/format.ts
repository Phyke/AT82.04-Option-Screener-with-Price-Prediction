export function formatMoney(n: number, digits = 0): string {
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatPercent(n: number, digits = 2): string {
  return `${(n * 100).toFixed(digits)}%`;
}

export function expiryLabel(isoDate: string, today: Date = new Date()): string {
  const exp = new Date(`${isoDate}T16:00:00-04:00`);
  const diffDays = Math.round((exp.getTime() - today.getTime()) / 86_400_000);
  const short = exp.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  if (diffDays <= 7) return `this Friday (${short})`;
  if (diffDays <= 14) return `next Friday (${short})`;
  return short;
}
