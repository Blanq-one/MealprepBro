/** An emoji announced by its label (FLOW_SPEC §4.4: every icon has a text label). */
export function Emoji({ symbol, label, className }: { symbol: string; label?: string; className?: string }) {
  if (!label) {
    return (
      <span className={className} aria-hidden="true">
        {symbol}
      </span>
    );
  }
  return (
    <span className={className} role="img" aria-label={label}>
      {symbol}
    </span>
  );
}
