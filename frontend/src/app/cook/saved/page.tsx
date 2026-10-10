"use client";

import { useRouter, useSearchParams } from "next/navigation";

import { type SavedList, SavedLists } from "@/components/cook/SavedLists";
import { Page } from "@/components/Page";

// C7 Saved lists: /cook/saved/?list=favorites or ?list=later.
function Saved() {
  const params = useSearchParams();
  const router = useRouter();
  const list: SavedList = params.get("list") === "later" ? "later" : "favorites";
  return <SavedLists list={list} onList={(next) => router.replace(`/cook/saved/?list=${next}`)} />;
}

export default function SavedPage() {
  return (
    <Page>
      <Saved />
    </Page>
  );
}
