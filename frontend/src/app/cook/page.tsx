"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { TodayCard } from "@/components/cook/TodayCard";
import { Pottle } from "@/components/ui/Pottle";
import { partOfDay } from "@/lib/format/dates";

import styles from "./cook.module.css";

// Cook home (C0). Until step 2b.4 adds "A meal now" and "Meal prep", it shows the Today card and the way to
// your existing plan view.
export default function CookHome() {
  const [greeting, setGreeting] = useState("Hi");
  useEffect(() => setGreeting(partOfDay()), []);
  return (
    <>
      <header className={styles.greeting}>
        <Pottle state="idle" size={32} />
        <h1 className={styles.title}>{greeting}! What are we making?</h1>
      </header>
      <TodayCard />
      <section className={styles.links} aria-label="Plans">
        <Link href="/plan/" className="btn btn-block">
          Your plans
        </Link>
        <Link href="/plan/new/" className="btn btn-block">
          Plan a week
        </Link>
      </section>
    </>
  );
}
