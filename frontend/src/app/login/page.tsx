"use client";

import { LoginForm } from "@/components/LoginForm";

export default function LoginPage() {
  // A full navigation (not a client route change) so the new session cookie is used everywhere at once.
  return <LoginForm onSignedIn={() => window.location.assign("/cook/")} />;
}
