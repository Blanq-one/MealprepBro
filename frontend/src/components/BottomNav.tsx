import Link from "next/link";

import styles from "./BottomNav.module.css";

const ITEMS = [
  { href: "/plan/", label: "Week", icon: "▦", match: ["/plan", "/day", "/recipe"] },
  { href: "/inventory/", label: "Inventory", icon: "◫", match: ["/inventory"] },
  { href: "/grocery/", label: "Grocery", icon: "✓", match: ["/grocery"] },
  { href: "/settings/", label: "Settings", icon: "⚙", match: ["/settings"] },
];

export function BottomNav({ pathname }: { pathname: string }) {
  return (
    <nav className={styles.nav} aria-label="Main">
      {ITEMS.map((item) => {
        const active = item.match.some((m) => pathname.startsWith(m));
        return (
          <Link
            key={item.href}
            href={item.href}
            className={active ? `${styles.item} ${styles.active}` : styles.item}
            aria-current={active ? "page" : undefined}
          >
            <span className={styles.icon} aria-hidden="true">
              {item.icon}
            </span>
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
