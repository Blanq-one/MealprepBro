import Link from "next/link";

import { TAB_ICONS } from "@/lib/format/icons";

import styles from "./BottomNav.module.css";

// The four tabs (FLOW_SPEC §3). Cook also covers the plan, day and recipe screens until 2b.7 replaces them.
export const TABS = [
  { href: "/cook/", label: "Cook", icon: TAB_ICONS.cook, match: ["/cook", "/plan", "/day", "/recipe"] },
  { href: "/grocery/", label: "Grocery", icon: TAB_ICONS.grocery, match: ["/grocery"] },
  { href: "/pantry/", label: "Pantry", icon: TAB_ICONS.pantry, match: ["/pantry", "/inventory"] },
  { href: "/settings/", label: "Settings", icon: TAB_ICONS.settings, match: ["/settings"] },
] as const;

export function BottomNav({ pathname }: { pathname: string }) {
  return (
    <nav className={styles.nav} aria-label="Main">
      {TABS.map((item) => {
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

/** Question flows and cooking mode show a back arrow and progress dots instead of the tabs. */
export function showsTabs(pathname: string): boolean {
  return !["/login", "/welcome", "/settings/edit", "/cook/ask", "/cook/cooking"].some((p) => pathname.startsWith(p));
}
