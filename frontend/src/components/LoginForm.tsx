"use client";

import { type FormEvent, useState } from "react";

import { ApiError, api } from "@/lib/api/client";

import styles from "./LoginForm.module.css";

export function loginMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "That password isn't right.";
    if (error.status === 429) {
      const minutes = error.retryAfterS !== null ? Math.max(1, Math.ceil(error.retryAfterS / 60)) : null;
      return minutes !== null
        ? `Too many tries. Try again in ${minutes} minute${minutes === 1 ? "" : "s"}.`
        : "Too many tries. Try again in a few minutes.";
    }
    if (error.status === 503) return `Sign-in isn't set up yet. ${error.detail}`.trim();
    return error.detail || error.title;
  }
  return "You're offline or the server can't be reached.";
}

export function LoginForm({ onSignedIn }: { onSignedIn: () => void }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!password || busy) return;
    setBusy(true);
    setMessage(null);
    try {
      await api<void>("/api/v1/auth/login", { method: "POST", json: { password } });
      onSignedIn();
    } catch (error) {
      setMessage(loginMessage(error));
      setBusy(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <h1>Mealbro</h1>
      <label htmlFor="password">Password</label>
      <input
        id="password"
        name="password"
        type="password"
        autoComplete="current-password"
        autoFocus
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {message && (
        <p className="notice notice-danger" role="alert">
          {message}
        </p>
      )}
      <button type="submit" className="btn btn-primary btn-block" disabled={busy || !password}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
