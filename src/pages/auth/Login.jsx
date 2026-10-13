import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Bug } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { PrimaryButton } from '../../components/common/Button';
import Badge from '../../components/common/Badge';

function GithubIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
      />
    </svg>
  );
}

export default function Login() {
  const [email, setEmail] = useState('ansh@devrescue.ai');
  const [password, setPassword] = useState('••••••••••••');
  const [loading, setLoading] = useState(false);
  const { login, loginWithGithub, loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    await login(email, password);
    setLoading(false);
    navigate('/dashboard');
  };

  const handleGithub = async () => {
    setLoading(true);
    await loginWithGithub();
    setLoading(false);
    navigate('/dashboard');
  };

  const handleGoogle = async () => {
    setLoading(true);
    await loginWithGoogle();
    setLoading(false);
    navigate('/dashboard');
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md bg-white border border-[#E2E8F0] rounded-2xl shadow-card p-8 sm:p-10 space-y-6">
        {/* Top: Logo & DEMO ENVIRONMENT Badge */}
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-[#2563EB] text-white flex items-center justify-center shadow-xs">
            <Bug className="w-6 h-6" />
          </div>

          <Badge variant="demo" size="sm">
            DEMO MODE
          </Badge>

          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            Sign in to DevRescue AI
          </h1>

          <p className="text-xs sm:text-sm text-[#64748B] leading-relaxed max-w-xs">
            Enter the developer console and explore autonomous bug resolution.
          </p>
        </div>

        {/* Demo Notice Banner */}
        <div className="p-3 bg-[#EFF6FF] border border-[#BFDBFE] rounded-lg text-center space-y-1">
          <p className="text-xs text-[#2563EB] font-semibold">
            Demo authentication — no real authentication connected
          </p>
          <p className="text-[11px] text-[#64748B]">
            Click below to instantly access the DevRescue console as demo user Ansh.
          </p>
        </div>

        {/* Quick Demo Access Button */}
        <PrimaryButton
          type="button"
          onClick={handleGithub}
          loading={loading}
          arrow={true}
          size="md"
          className="w-full justify-center text-sm py-2.5 shadow-sm"
        >
          Enter Demo Console
        </PrimaryButton>

        {/* Social Buttons */}
        <div className="space-y-2.5">
          <button
            type="button"
            onClick={handleGithub}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2.5 px-4 py-2.5 rounded-lg border border-[#E2E8F0] bg-white hover:bg-[#F8FAFC] text-xs font-semibold text-[#0F172A] shadow-xs transition-all active:scale-[0.98] cursor-pointer disabled:opacity-50"
          >
            <GithubIcon className="w-4 h-4" />
            <span>Continue with GitHub</span>
          </button>

          <button
            type="button"
            onClick={handleGoogle}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2.5 px-4 py-2.5 rounded-lg border border-[#E2E8F0] bg-white hover:bg-[#F8FAFC] text-xs font-semibold text-[#0F172A] shadow-xs transition-all active:scale-[0.98] cursor-pointer disabled:opacity-50"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            <span>Continue with Google</span>
          </button>
        </div>

        <div className="relative flex py-1 items-center">
          <div className="flex-grow border-t border-[#E2E8F0]" />
          <span className="flex-shrink mx-3 text-[11px] text-[#94A3B8] uppercase font-semibold">
            or continue with email
          </span>
          <div className="flex-grow border-t border-[#E2E8F0]" />
        </div>

        {/* Email & Password Form */}
        <form onSubmit={handleEmailSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#0F172A] mb-1.5 uppercase tracking-wider">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ansh@devrescue.ai"
              required
              className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2.5 text-sm text-[#0F172A] placeholder-[#94A3B8] transition-colors focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider">
                Password
              </label>
              <span className="text-[11px] text-[#64748B]">Demo auto-filled</span>
            </div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2.5 text-sm text-[#0F172A] placeholder-[#94A3B8] transition-colors focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
            />
          </div>

          <PrimaryButton
            type="submit"
            size="md"
            loading={loading}
            arrow={true}
            className="w-full justify-center text-sm py-2.5 shadow-sm"
          >
            Sign In
          </PrimaryButton>
        </form>

        <div className="text-center pt-2">
          <Link
            to="/"
            className="text-xs text-[#64748B] hover:text-[#0F172A] transition-colors"
          >
            ← Back to DevRescue AI Homepage
          </Link>
        </div>
      </div>
    </div>
  );
}
