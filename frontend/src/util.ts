// Pure helpers (no DOM), so they can be unit-tested with plain node.

/** The next 1 / 2 / 5 × 10^k at or above `value`, so the scale does not jump around. */
export function niceCeil(value: number): number {
  if (value <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(value)));
  for (const step of [1, 2, 5, 10]) {
    if (step * exp >= value) return step * exp;
  }
  return 10 * exp;
}
