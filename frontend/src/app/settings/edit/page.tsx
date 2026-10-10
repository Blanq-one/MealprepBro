"use client";

import { useRouter, useSearchParams } from "next/navigation";

import { useOnline } from "@/components/AppShell";
import { Page } from "@/components/Page";
import { SettingsEditor } from "@/components/settings/SettingsEditor";

// S1 editors: /settings/edit/?field=daily_kcal_target (S2 is ?field=always_have).
function Edit() {
  const router = useRouter();
  const field = useSearchParams().get("field") ?? "";
  const online = useOnline();
  return <SettingsEditor key={field} field={field} online={online} onDone={() => router.push("/settings/")} />;
}

export default function SettingsEditPage() {
  return (
    <Page>
      <Edit />
    </Page>
  );
}
