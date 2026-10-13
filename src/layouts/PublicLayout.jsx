import React, { useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Menu, X, Bug } from 'lucide-react';
import Button from '../components/common/Button';
import Badge from '../components/common/Badge';

export default function PublicLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLinks = [
    { label: 'Features', href: '/#features' },
    { label: 'How It Works', href: '/#how-it-works' },
    { label: 'AI Agents', to: '/agents' },
    { label: 'Documentation', to: '/docs' },
    { label: 'About', to: '/about' },
    { label: 'Support', to: '/support' },
  ];

  return (
    <div className="min-h-screen bg-white text-[#0F172A] flex flex-col font-sans selection:bg-[#EFF6FF] selection:text-[#2563EB]">
      {/* Top Demo Banner */}
      <div className="bg-[#EFF6FF] border-b border-[#BFDBFE] px-4 py-1.5 text-xs text-center text-[#2563EB] font-medium flex items-center justify-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-pulse" />
        <span>Frontend Prototype Demo — All AI pipelines, logs, and pull requests run in simulated demo mode.</span>
      </div>

      {/* Main Public Navbar */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-[#E2E8F0]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-[#2563EB] text-white flex items-center justify-center shadow-sm group-hover:bg-[#1D4ED8] transition-colors">
                <Bug className="w-5 h-5" />
              </div>
              <div className="flex flex-col">
                <span className="text-lg font-bold tracking-tight text-[#0F172A] leading-tight flex items-center gap-1.5">
                  DevRescue AI
                </span>
                <span className="text-[10px] text-[#64748B] font-medium tracking-wide">
                  Autonomous Code Repair
                </span>
              </div>
            </Link>
            <Badge variant="blue" size="sm" className="hidden sm:inline-flex">
              DEMO
            </Badge>
          </div>

          {/* Desktop Nav Links */}
          <nav className="hidden lg:flex items-center gap-7 text-sm font-medium text-[#64748B]">
            {navLinks.map((link) => {
              if (link.to) {
                const isActive = location.pathname === link.to;
                return (
                  <Link
                    key={link.label}
                    to={link.to}
                    className={`transition-colors hover:text-[#0F172A] ${
                      isActive ? 'text-[#2563EB] font-semibold' : ''
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              }
              return (
                <a
                  key={link.label}
                  href={link.href}
                  className="transition-colors hover:text-[#0F172A]"
                >
                  {link.label}
                </a>
              );
            })}
          </nav>

          {/* Desktop Actions */}
          <div className="hidden sm:flex items-center gap-3">
            {user ? (
              <Button to="/dashboard" variant="primary" size="sm" arrow={true}>
                Go to Dashboard
              </Button>
            ) : (
              <>
                <Link
                  to="/login"
                  className="text-sm font-medium text-[#64748B] hover:text-[#0F172A] px-3 py-1.5 transition-colors"
                >
                  Sign In
                </Link>
                <Button to="/login" variant="primary" size="sm" arrow={true}>
                  Get Started
                </Button>
              </>
            )}
          </div>

          {/* Mobile Menu Toggle */}
          <div className="lg:hidden flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileOpen(!mobileOpen)}
              className="p-2 text-[#64748B] hover:text-[#0F172A] rounded-lg hover:bg-slate-100 cursor-pointer"
              aria-label="Toggle navigation menu"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Drawer */}
        {mobileOpen && (
          <div className="lg:hidden border-b border-[#E2E8F0] bg-white px-4 py-5 space-y-3">
            <nav className="flex flex-col space-y-2.5">
              {navLinks.map((link) => {
                if (link.to) {
                  return (
                    <Link
                      key={link.label}
                      to={link.to}
                      onClick={() => setMobileOpen(false)}
                      className="text-sm font-medium text-[#64748B] hover:text-[#0F172A] py-1.5"
                    >
                      {link.label}
                    </Link>
                  );
                }
                return (
                  <a
                    key={link.label}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className="text-sm font-medium text-[#64748B] hover:text-[#0F172A] py-1.5"
                  >
                    {link.label}
                  </a>
                );
              })}
            </nav>
            <div className="pt-4 border-t border-[#E2E8F0] flex flex-col gap-2">
              <Link
                to="/login"
                onClick={() => setMobileOpen(false)}
                className="text-center text-sm font-medium text-[#64748B] py-2"
              >
                Sign In
              </Link>
              <Button
                to="/login"
                variant="primary"
                size="md"
                onClick={() => setMobileOpen(false)}
                className="w-full justify-center"
              >
                Get Started
              </Button>
            </div>
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="flex-1 page-fade-in">
        <Outlet />
      </main>

      {/* Modern SaaS Footer */}
      <footer className="bg-[#F8FAFC] border-t border-[#E2E8F0] mt-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-10 pb-12 border-b border-[#E2E8F0]">
            {/* Brand column */}
            <div className="md:col-span-2 space-y-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[#2563EB] text-white flex items-center justify-center">
                  <Bug className="w-4 h-4" />
                </div>
                <span className="text-lg font-bold text-[#0F172A]">DevRescue AI</span>
              </div>
              <p className="text-sm text-[#64748B] leading-relaxed max-w-sm">
                DevRescue AI is an autonomous software engineering platform that investigates bugs, identifies root causes, generates minimal fixes, runs tests, performs security review, and prepares pull requests.
              </p>
              <div className="flex items-center gap-2 text-xs text-[#2563EB] font-medium pt-1">
                <span className="w-2 h-2 rounded-full bg-[#16A34A]" />
                <span>Simulated Pipeline · Ready for Human Verification</span>
              </div>
            </div>

            {/* Product Links */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-[#0F172A] mb-3">
                Product
              </h4>
              <ul className="space-y-2 text-sm text-[#64748B]">
                <li><Link to="/dashboard" className="hover:text-[#2563EB] transition-colors">Dashboard</Link></li>
                <li><Link to="/repositories" className="hover:text-[#2563EB] transition-colors">Repositories</Link></li>
                <li><Link to="/investigations/new" className="hover:text-[#2563EB] transition-colors">New Investigation</Link></li>
                <li><Link to="/investigations/1" className="hover:text-[#2563EB] transition-colors">Live Telemetry</Link></li>
                <li><Link to="/pull-requests" className="hover:text-[#2563EB] transition-colors">Pull Requests</Link></li>
              </ul>
            </div>

            {/* Agents & Architecture */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-[#0F172A] mb-3">
                AI Collective
              </h4>
              <ul className="space-y-2 text-sm text-[#64748B]">
                <li><Link to="/agents" className="hover:text-[#2563EB] transition-colors">Repository Analyzer</Link></li>
                <li><Link to="/agents" className="hover:text-[#2563EB] transition-colors">Bug Investigator</Link></li>
                <li><Link to="/agents" className="hover:text-[#2563EB] transition-colors">Code Repair Agent</Link></li>
                <li><Link to="/agents" className="hover:text-[#2563EB] transition-colors">Testing Agent</Link></li>
                <li><Link to="/agents" className="hover:text-[#2563EB] transition-colors">Security Reviewer</Link></li>
              </ul>
            </div>

            {/* Resources & Support */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-[#0F172A] mb-3">
                Resources
              </h4>
              <ul className="space-y-2 text-sm text-[#64748B]">
                <li><Link to="/docs" className="hover:text-[#2563EB] transition-colors">Documentation</Link></li>
                <li><Link to="/about" className="hover:text-[#2563EB] transition-colors">About Us</Link></li>
                <li><Link to="/support" className="hover:text-[#2563EB] transition-colors">Developer Support</Link></li>
                <li><Link to="/settings" className="hover:text-[#2563EB] transition-colors">Reset Demo Data</Link></li>
              </ul>
            </div>
          </div>

          <div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#64748B]">
            <div>
              © 2026 DevRescue AI. Autonomous Software Engineering Platform.
            </div>
            <div className="flex items-center gap-4">
              <span>Frontend Prototype Demo</span>
              <span>·</span>
              <span className="text-[#16A34A] font-medium">Verified Pull Requests</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
