import type { InventoryLot } from "@/lib/api/types";
import { daysUntil, shortDate } from "@/lib/format/dates";

const USE_SOON_DAYS = 3;

export function ExpiryBadge({ lot }: { lot: InventoryLot }) {
  if (!lot.expires_on) return null;
  const days = daysUntil(lot.expires_on);
  const estimate = lot.expiry_is_estimate ? " (est.)" : "";
  if (days < 0) return <span className="badge badge-danger">Past use-by {shortDate(lot.expires_on)}</span>;
  if (days <= USE_SOON_DAYS) return <span className="badge badge-warn">Use soon: {shortDate(lot.expires_on)}{estimate}</span>;
  return <span className="badge">Use by {shortDate(lot.expires_on)}{estimate}</span>;
}

/** A lot's badges: open, use-by, an estimated amount ("Not sure"), and its diet state when it isn't plainly
 * allowed. */
export function LotBadges({ lot }: { lot: InventoryLot }) {
  return (
    <>
      {lot.opened_on && <span className="badge badge-accent">Open</span>}
      <ExpiryBadge lot={lot} />
      {lot.quantity_is_estimate && <span className="badge">est. amount</span>}
      {lot.state === "held" && <span className="badge badge-warn">Held</span>}
      {lot.state === "excluded" && <span className="badge badge-danger">Off your list</span>}
    </>
  );
}
