"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** An old route that moved (static export: no server redirects). Keeps the query string, so bookmarks and the
 * offline shell keep working. */
export function Redirect({ to, label }: { to: string; label: string }) {
  const router = useRouter();
  useEffect(() => {
    router.replace(`${to}${window.location.search}`);
  }, [router, to]);
  return (
    <p>
      <Link href={to}>{label}</Link>
    </p>
  );
}
