"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

import { useOnline } from "@/components/AppShell";
import { isStep, Onboarding, type Step } from "@/components/onboarding/Onboarding";
import { Page } from "@/components/Page";

// Each step is part of the URL (/welcome/?step=targets), so the back arrow and the back gesture both work.
let steppedWithin = false;

function Welcome() {
  const router = useRouter();
  const params = useSearchParams();
  const raw = params.get("step");
  const step: Step = isStep(raw) ? raw : "welcome";
  const online = useOnline();

  const navigate = useCallback(
    (to: Step, how: "push" | "back" = "push") => {
      const url = to === "welcome" ? "/welcome/" : `/welcome/?step=${to}`;
      if (how === "back" && steppedWithin) {
        router.back();
      } else if (how === "back") {
        router.replace(url);
      } else {
        steppedWithin = true;
        router.push(url);
      }
      window.scrollTo(0, 0);
    },
    [router],
  );
  const onDone = useCallback(() => router.replace("/cook/"), [router]);

  return <Onboarding step={step} navigate={navigate} onDone={onDone} online={online} />;
}

export default function WelcomePage() {
  return (
    <Page>
      <Welcome />
    </Page>
  );
}
