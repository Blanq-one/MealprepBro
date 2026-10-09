"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

// The installed app starts at /plan/; anyone opening "/" goes there too.
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/plan/");
  }, [router]);
  return (
    <main>
      <p>
        <Link href="/plan/">Open your week</Link>
      </p>
    </main>
  );
}
