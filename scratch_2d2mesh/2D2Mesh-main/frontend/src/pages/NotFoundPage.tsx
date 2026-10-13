import { useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/ui/Icon";
import { Logo } from "../components/layout/AppShell";

export function NotFoundPage() {
  const [hue] = useState(() => Math.floor(Math.random() * 360));
  return (
    <div className="relative flex min-h-screen flex-col bg-ink-950">
      <div className="pointer-events-none fixed inset-0 bg-aurora" aria-hidden />
      <header className="relative z-10 flex h-16 items-center px-4 sm:px-6">
        <Logo />
      </header>
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-4 pb-24 text-center">
        <div
          className="relative flex h-28 w-28 items-center justify-center rounded-3xl border border-white/10 bg-ink-900/60 font-display text-4xl font-extrabold text-white shadow-card backdrop-blur-xl"
          style={{
            boxShadow: `0 0 60px -12px hsla(${hue}, 80%, 55%, 0.55)`,
            background: `linear-gradient(135deg, hsla(${hue},80%,55%,0.18), hsla(${(hue + 60) % 360},80%,50%,0.10))`,
          }}
        >
          404
          <span className="absolute inset-0 rounded-3xl blur-2xl" aria-hidden style={{ background: `radial-gradient(60% 60% at 50% 40%, hsla(${hue},80%,55%,0.35), transparent 70%)` }} />
        </div>
        <h1 className="mt-8 font-display text-3xl font-bold tracking-tight text-white">Page not found</h1>
        <p className="mt-2 max-w-md text-sm text-slate-400">
          The page you are looking for doesn&apos;t exist or was moved.
        </p>
        <Link
          to="/"
          className="mt-8 inline-flex items-center gap-2 rounded-xl bg-brand-gradient px-6 py-3 text-sm font-semibold text-white shadow-glow transition-all hover:brightness-110"
        >
          <Icon name="arrowRight" className="h-4 w-4 rotate-180" /> Back home
        </Link>
      </main>
    </div>
  );
}