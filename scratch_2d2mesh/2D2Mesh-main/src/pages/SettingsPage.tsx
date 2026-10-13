import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";
import { useToast } from "../hooks/useToast";
import { usersApi } from "../api/auth";
import { extractApiError } from "../api/client";
import { Button } from "../components/ui/Button";
import { Card, CardBody } from "../components/ui/Card";
import { Input } from "../components/ui/Field";
import { Modal } from "../components/ui/Modal";
import { Alert } from "../components/ui/Feedback";
import { Icon } from "../components/ui/Icon";
import type { ThemePreference } from "../types/api";

export function SettingsPage() {
  const { user, updateUser, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const { toast } = useToast();
  const navigate = useNavigate();

  if (!user) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-8 animate-fade-in">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-white">Settings</h1>
        <p className="mt-1 text-slate-400">Manage your account preferences and model defaults.</p>
      </div>

      <AppearanceSection theme={theme} setTheme={setTheme} />

      <DefaultModelSection
        currentModel={user.preferences?.default_model ?? "auto"}
        onSave={async (model) => {
          try {
            await updateUser({ preferences: { ...user.preferences, default_model: model } });
            toast("success", "Default model updated");
          } catch (err) {
            toast("error", "Failed to update", { description: extractApiError(err) });
          }
        }}
      />

      <ChangePasswordSection />

      <DangerZone
        onDeleteAccount={async (password) => {
          try {
            await usersApi.deleteAccount(password);
            logout();
            navigate("/");
            toast("success", "Account deleted");
          } catch (err) {
            toast("error", "Delete failed", { description: extractApiError(err) });
          }
        }}
      />
    </div>
  );
}

function SectionTitle({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-white">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300">
        {icon}
      </span>
      {children}
    </h2>
  );
}

/* ─── Appearance ─── */

function AppearanceSection({
  theme,
  setTheme,
}: {
  theme: ThemePreference;
  setTheme: (t: ThemePreference) => void;
}) {
  const themes: { value: ThemePreference; label: string; icon: React.ReactNode }[] = [
    { value: "system", label: "System", icon: <Icon name="cpu" className="h-6 w-6" /> },
    { value: "light", label: "Light", icon: <Icon name="sun" className="h-6 w-6" /> },
    { value: "dark", label: "Dark", icon: <Icon name="moon" className="h-6 w-6" /> },
  ];

  return (
    <Card>
      <CardBody className="space-y-4">
        <SectionTitle icon={<Icon name="sun" className="h-4 w-4" />}>Appearance</SectionTitle>
        <div className="grid grid-cols-3 gap-3">
          {themes.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTheme(t.value)}
              className={`flex flex-col items-center gap-2 rounded-xl border-2 p-4 transition-all duration-200 ${
                theme === t.value
                  ? "border-brand-400/60 bg-brand-500/10 shadow-glow"
                  : "border-white/10 hover:border-white/20 hover:bg-white/[0.03]"
              }`}
            >
              <span className={theme === t.value ? "text-brand-300" : "text-slate-500"}>{t.icon}</span>
              <span className="text-sm font-medium text-white">{t.label}</span>
            </button>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

/* ─── Default Model ─── */

function DefaultModelSection({
  currentModel,
  onSave,
}: {
  currentModel: string;
  onSave: (model: string) => Promise<void>;
}) {
  const [model, setModel] = useState(currentModel);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(model);
    } finally {
      setSaving(false);
    }
  };

  const options = [
    { value: "auto", label: "Auto (server default)" },
    { value: "mock", label: "Mock (dev, no GPU)" },
    { value: "stable-fast-3d", label: "Stable Fast 3D" },
    { value: "hunyuan3d", label: "Hunyuan3D-2" },
  ];

  return (
    <Card>
      <CardBody className="space-y-4">
        <SectionTitle icon={<Icon name="cpu" className="h-4 w-4" />}>Default AI model</SectionTitle>
        <p className="text-sm text-slate-400">
          Choose which model is pre-selected when you create a new generation.
        </p>
        <div className="flex gap-3">
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="flex-1 cursor-pointer rounded-xl border border-white/12 bg-ink-800/70 px-3 py-2.5 text-sm text-slate-200 outline-none transition-colors focus:border-brand-400/60 dark:[&>option]:bg-ink-800"
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <Button onClick={handleSave} loading={saving} disabled={model === currentModel}>
            Save
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

/* ─── Change Password ─── */

function ChangePasswordSection() {
  const { toast } = useToast();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await usersApi.changePassword(currentPassword, newPassword);
      toast("success", "Password changed successfully");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardBody>
        <SectionTitle icon={<Icon name="lock" className="h-4 w-4" />}>Change password</SectionTitle>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {error && <Alert tone="error" title="Error">{error}</Alert>}
          <Input
            label="Current Password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
          />
          <Input
            label="New Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            hint="Minimum 8 characters with uppercase, lowercase, and a digit."
          />
          <Input
            label="Confirm New Password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
          />
          <Button type="submit" loading={loading} disabled={!currentPassword || !newPassword}>
            Update Password
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

/* ─── Danger Zone ─── */

function DangerZone({ onDeleteAccount }: { onDeleteAccount: (password: string) => Promise<void> }) {
  const [showModal, setShowModal] = useState(false);
  const [password, setPassword] = useState("");
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!password) return;
    setDeleting(true);
    try {
      await onDeleteAccount(password);
    } finally {
      setDeleting(false);
      setShowModal(false);
    }
  };

  return (
    <>
      <Card className="border-red-500/30">
        <CardBody className="space-y-3">
          <SectionTitle icon={<Icon name="alert" className="h-4 w-4" />}>Danger zone</SectionTitle>
          <p className="text-sm text-slate-400">
            Permanently delete your account and all associated data. This cannot be undone.
          </p>
          <Button
            variant="outline"
            onClick={() => setShowModal(true)}
            className="border-red-500/30 text-red-300 hover:bg-red-500/10"
          >
            Delete Account
          </Button>
        </CardBody>
      </Card>

      <Modal open={showModal} onClose={() => setShowModal(false)} title="Delete Account">
        <div className="space-y-4">
          <Alert tone="error" title="This action is irreversible">
            All your projects, models, and data will be permanently deleted.
          </Alert>
          <Input
            label="Enter your password to confirm"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleDelete} loading={deleting} disabled={!password} variant="danger">
              Delete My Account
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}