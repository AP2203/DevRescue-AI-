import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { validateRegister } from "../lib/validators";
import { extractApiError } from "../api/client";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Field";
import { Alert } from "../components/ui/Feedback";
import { Icon } from "../components/ui/Icon";
import { Logo } from "../components/layout/AppShell";
import { AuthSidePanel } from "./LoginPage";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", username: "", password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const updateField = (field: keyof typeof form) => (value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setServerError(null);
    const validation = validateRegister(form);
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;

    setLoading(true);
    try {
      await register(form);
      navigate("/dashboard", { replace: true });
    } catch (error) {
      setServerError(extractApiError(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left: form */}
      <div className="relative flex flex-col bg-slate-50 px-6 py-8 transition-colors duration-200 dark:bg-ink-950 sm:px-12">
        <div className="pointer-events-none absolute inset-0 bg-aurora opacity-60" aria-hidden />
        <div className="relative z-10">
          <Logo />
        </div>
        <div className="relative z-10 mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <div className="mb-8">
            <span className="inline-flex items-center gap-2 rounded-full border border-accent-500/30 bg-accent-500/10 px-3 py-1 text-xs font-medium text-accent-700 dark:text-accent-200">
              <Icon name="sparkles" className="h-3.5 w-3.5" /> Free to start
            </span>
            <h1 className="mt-4 font-display text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Create your account</h1>
            <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
              Start converting images into 3D models in minutes.
            </p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {serverError && <Alert tone="error" title="Registration failed">{serverError}</Alert>}
            <Input
              label="Email"
              type="email"
              value={form.email}
              onChange={(event) => updateField("email")(event.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              error={errors.email}
            />
            <Input
              label="Username"
              value={form.username}
              onChange={(event) => updateField("username")(event.target.value)}
              placeholder="visionary3d"
              autoComplete="username"
              error={errors.username}
              hint="Letters, numbers and underscores only."
            />
            <Input
              label="Password"
              type="password"
              value={form.password}
              onChange={(event) => updateField("password")(event.target.value)}
              placeholder="At least 8 characters"
              autoComplete="new-password"
              error={errors.password}
              hint="Use uppercase, lowercase and a digit."
            />
            <Button type="submit" fullWidth loading={loading} size="lg">
              Create account
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-brand-300 hover:underline">
              Sign in
            </Link>
          </p>
        </div>
        <p className="relative z-10 text-center text-xs text-slate-600">
          © {new Date().getFullYear()} Vision3D AI
        </p>
      </div>

      {/* Right: visual */}
      <AuthSidePanel
        eyebrow="From photo to production"
        title="Upload an image. Watch it become a 3D model."
        points={[
          "Free account with 10 generations monthly",
          "Full commercial rights on every export",
          "No GPU, no installs — it all runs in the browser",
        ]}
      />
    </div>
  );
}