"use client";

import { SettingsList } from "@/components/settings/SettingsList";
import { SyncNote } from "@/components/Status";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api/client";
import type { SettingsOut } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";

export default function SettingsPage() {
  const loaded = useApi<SettingsOut>("/api/v1/settings");

  async function signOut() {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
      navigator.serviceWorker?.controller?.postMessage("clear-api-cache"); // no offline copy once signed out
    } finally {
      window.location.assign("/login/");
    }
  }

  return (
    <>
      <h1>Settings</h1>
      <SyncNote syncedAt={loaded.syncedAt} fromCache={loaded.fromCache} />
      {loaded.data ? (
        <SettingsList out={loaded.data} onSignOut={() => void signOut()} />
      ) : loaded.error ? (
        <ErrorState error={loaded.error} onRetry={() => void loaded.reload()} />
      ) : (
        <Skeleton cards={4} label="Loading your settings" />
      )}
    </>
  );
}
