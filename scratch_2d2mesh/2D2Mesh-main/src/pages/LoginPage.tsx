import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { validateLogin } from "../lib/validators";
import { extractApiError } from "../api/client";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Field";
import { Alert } from "../components/ui/Feedback";
import { Icon } from "../components/ui/Icon";
import { Logo } from "../components/layout/AppShell";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setServerError(null);
    const validation = validateLogin({ email, password });
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;

    setLoading(true);
    try {
      await login({ email, password });
      navigate(params.get("redirect") || "/dashboard", { replace: true });
    } catch (error) {
      setServerError(extractApiError(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left: form */}
      <div className="relative flex flex-col bg-ink-950 px-6 py-8 sm:px-12">
        <div className="pointer-events-none absolute inset-0 bg-aurora opacity-60" aria-hidden />
        <div className="relative z-10">
          <Logo />
        </div>
        <div className="relative z-10 mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <div className="mb-8">
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-200">
              <Icon name="lock" className="h-3.5 w-3.5" /> Secure sign in
            </span>
            <h1 className="mt-4 font-display text-3xl font-bold tracking-tight text-white">Welcome back</h1>
            <p className="mt-1.5 text-sm text-slate-400">Sign in to continue generating 3D models.</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {serverError && <Alert tone="error" title="Sign in failed">{serverError}</Alert>}
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              error={errors.email}
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              error={errors.password}
            />
            <Button type="submit" fullWidth loading={loading} size="lg">
              Sign in
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Don&apos;t have an account?{" "}
            <Link to="/register" className="font-semibold text-brand-300 hover:underline">
              Create one
            </Link>
          </p>
        </div>
        <p className="relative z-10 text-center text-xs text-slate-600">
          © {new Date().getFullYear()} Vision3D AI
        </p>
      </div>

      {/* Right: visual */}
      <AuthSidePanel
        eyebrow="Your workspace awaits"
        title="Every model you've ever generated, one click away."
        points={[
          "Real-time generation tracking with live progress",
          "Interactive 3D viewer with full camera controls",
          "One-click GLB / GLTF exports for any engine",
        ]}
      />
    </div>
  );
}

export function AuthSidePanel({
  eyebrow,
  title,
  points,
}: {
  eyebrow: string;
  title: string;
  points: string[];
}) {
  return (
    <div className="relative hidden overflow-hidden border-l border-white/8 bg-ink-900/60 lg:flex lg:flex-col lg:items-center lg:justify-center lg:px-16">
      <div className="absolute inset-0 bg-aurora" aria-hidden />
      <div className="relative z-10 max-w-md">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-300">{eyebrow}</p>
        <h2 className="mt-3 font-display text-3xl font-bold leading-tight tracking-tight text-white">
          {title}
        </h2>
        <ul className="mt-8 space-y-4">
          {points.map((point) => (
            <li key={point} className="flex items-start gap-3 text-sm text-slate-300">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300">
                <Icon name="check" className="h-4 w-4" strokeWidth={2.4} />
              </span>
              {point}
            </li>
          ))}
        </ul>
      </div>
      <div className="relative z-10 mt-12 h-56 w-56 animate-float">
        <span className="absolute inset-0 rounded-3xl bg-brand-gradient opacity-40 blur-3xl" aria-hidden />
        <span className="absolute inset-4 flex items-center justify-center rounded-3xl border border-white/10 bg-ink-950/60 backdrop-blur-xl">
          <Icon name="cube" className="h-24 w-24 text-brand-300/70 drop-shadow-[0_0_30px_rgba(124,58,237,0.5)]" strokeWidth={1} />
        </span>
      </div>
    </div>
  );
}