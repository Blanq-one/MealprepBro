"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useOnline } from "@/components/AppShell";
import { CookHomeView } from "@/components/cook/CookHome";
import type { CookAnswers, CookHome } from "@/lib/api/types";
import { savePending } from "@/lib/cook/answers";
import { partOfDay } from "@/lib/format/dates";
import { useApi } from "@/lib/hooks/useApi";

// C0 Cook home (FLOW_SPEC §7): A meal now and Meal prep first, then Same as last time, Today and Saved.
export default function CookHomePage() {
  const [greeting, setGreeting] = useState("Hi");
  useEffect(() => setGreeting(partOfDay()), []);
  const home = useApi<CookHome>("/api/v1/cook/home");
  const online = useOnline();
  const router = useRouter();
  return (
    <CookHomeView
      greeting={greeting}
      home={home.data}
      loading={home.loading}
      error={home.error}
      online={online}
      onRetry={() => void home.reload()}
      onSameAgain={(last) => {
        // those exact answers again, with today's pantry (a meal now is instant when nothing changed)
        const run = savePending(last.answers as unknown as CookAnswers);
        router.push(last.mode === "prep" ? `/cook/plan/?run=${run}` : `/cook/results/?run=${run}`);
      }}
    />
  );
}
