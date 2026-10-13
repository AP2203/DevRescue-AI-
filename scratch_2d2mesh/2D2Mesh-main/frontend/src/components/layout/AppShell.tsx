import { NavLink, Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useTheme } from "../../hooks/useTheme";
import { initials, cn } from "../../lib/format";
import { Fragment, useState } from "react";
import { Icon, type IconName } from "../ui/Icon";

type NavItem = { to: string; label: string; icon: IconName; end?: boolean };

const primaryNav: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/generate", label: "Generate 3D", icon: "generate" },
  { to: "/projects", label: "Projects", icon: "projects" },
];

const secondaryNav: NavItem[] = [
  { to: "/profile", label: "Profile", icon: "user" },
  { to: "/settings", label: "Settings", icon: "settings" },
];

export function AppShell() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-slate-50 transition-colors duration-200 dark:bg-ink-950">
      {/* Ambient background */}
      <div className="pointer-events-none fixed inset-0 z-0 bg-aurora" aria-hidden />

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200/80 bg-white/95 backdrop-blur-2xl transition-transform duration-300 dark:border-white/8 dark:bg-ink-900/80 lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
        id="app-sidebar"
        aria-label="Primary navigation"
      >
        <SidebarContent
          isAuthenticated={isAuthenticated}
          isLoading={isLoading}
          user={user}
          onNavigate={() => setSidebarOpen(false)}
        />
      </aside>

      {/* Sidebar overlay (mobile) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-sm dark:bg-ink-950/70 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden
        />
      )}

      {/* Main column */}
      <div className="relative z-10 flex min-w-0 flex-1 flex-col lg:pl-64">
        <Topbar user={user} onMenuClick={() => setSidebarOpen(true)} />
        <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 px-4 pb-24 pt-6 sm:px-6 lg:pb-10 lg:pt-8">
          <Outlet />
        </main>
        <footer className="border-t border-slate-200/80 py-6 dark:border-white/8">
          <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-4 text-sm text-slate-500 sm:flex-row sm:px-6">
            <p>© {new Date().getFullYear()} Vision3D AI</p>
            <p className="text-xs">Turn any image into a 3D model.</p>
          </div>
        </footer>
      </div>

      {/* Mobile bottom nav */}
      <MobileNav />
    </div>
  );
}

/* ─── Sidebar content ─── */

function SidebarContent({
  user,
  isAuthenticated,
  isLoading,
  onNavigate,
}: {
  user: ReturnType<typeof useAuth>["user"];
  isAuthenticated: boolean;
  isLoading: boolean;
  onNavigate: () => void;
}) {
  return (
    <>
      <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-slate-200/80 px-5 dark:border-white/8">
        <Logo />
      </div>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5">
        {isAuthenticated && !isLoading && (
          <ul className="space-y-1">
            <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
              Workspace
            </p>
            {primaryNav.map((item) => (
              <li key={item.to}>
                <SidebarLink item={item} onNavigate={onNavigate} />
              </li>
            ))}
          </ul>
        )}
        <ul className="space-y-1">
          <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
            General
          </p>
          {secondaryNav.map((item) => (
            <li key={item.to}>
              <SidebarLink item={item} onNavigate={onNavigate} />
            </li>
          ))}
          {user?.role === "admin" && (
            <li>
              <SidebarLink item={{ to: "/admin", label: "Admin", icon: "shield" }} onNavigate={onNavigate} />
            </li>
          )}
          {!isAuthenticated && (
            <>
              <li><SidebarLink item={{ to: "/", label: "Home", icon: "logo", end: true }} onNavigate={onNavigate} /></li>
              <li><SidebarLink item={{ to: "/login", label: "Sign in", icon: "lock" }} onNavigate={onNavigate} /></li>
            </>
          )}
        </ul>
      </nav>

      <div className="shrink-0 border-t border-slate-200/80 p-4 dark:border-white/8">
        {isAuthenticated && user ? (
          <UserCard user={user} onNavigate={onNavigate} />
        ) : (
          <div className="space-y-2">
            <Link
              to="/register"
              onClick={onNavigate}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-gradient px-4 py-2.5 text-sm font-semibold text-white shadow-glow transition-all hover:brightness-110"
            >
              Get started free
            </Link>
            <Link
              to="/login"
              onClick={onNavigate}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white/80 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-white/12 dark:bg-transparent dark:text-slate-300 dark:hover:bg-white/5 dark:hover:text-white"
            >
              Sign in
            </Link>
          </div>
        )}
      </div>
    </>
  );
}

function SidebarLink({ item, onNavigate }: { item: NavItem; onNavigate: () => void }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
          isActive
            ? "bg-brand-500/10 text-brand-700 shadow-sm dark:bg-brand-500/15 dark:text-brand-200 dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_0_24px_-10px_rgba(139,92,246,0.8)]"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white",
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            name={item.icon}
            className={cn("h-5 w-5 transition-all", isActive ? "text-brand-600 dark:text-brand-300" : "text-slate-400 group-hover:text-slate-700 dark:text-slate-500 dark:group-hover:text-slate-300")}
            strokeWidth={1.8}
          />
          {item.label}
          {isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-500 shadow-glow dark:bg-brand-400" aria-hidden />}
        </>
      )}
    </NavLink>
  );
}

function UserCard({ user, onNavigate }: { user: NonNullable<ReturnType<typeof useAuth>["user"]>; onNavigate: () => void }) {
  const navigate = useNavigate();
  const { logout } = useAuth();
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={onNavigate}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-gradient text-sm font-bold text-white shadow-glow"
        aria-label="Open profile"
      >
        {initials(user.username)}
      </button>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{user.username}</p>
        <p className="truncate text-xs text-slate-500 dark:text-slate-400">{user.email}</p>
      </div>
      <button
        type="button"
        onClick={() => {
          logout();
          navigate("/");
        }}
        aria-label="Sign out"
        className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-slate-500 dark:hover:bg-white/5 dark:hover:text-red-400"
      >
        <Icon name="external" className="h-4 w-4 -rotate-45" />
      </button>
    </div>
  );
}

/* ─── Topbar ─── */

function Topbar({ user, onMenuClick }: { user: ReturnType<typeof useAuth>["user"]; onMenuClick: () => void }) {
  const { resolvedTheme, toggleTheme } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200/80 bg-white/80 px-4 backdrop-blur-xl dark:border-white/8 dark:bg-ink-950/70 sm:px-6">
      <button
        type="button"
        aria-label="Open menu"
        onClick={onMenuClick}
        className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white lg:hidden"
      >
        <Icon name="menu" />
      </button>

      {/* Breadcrumbs / page context */}
      <div className="hidden min-w-0 items-center gap-2 text-sm text-slate-500 dark:text-slate-400 md:flex">
        <span className="font-medium text-slate-800 dark:text-slate-300">Vision3D AI</span>
        <span aria-hidden>/</span>
        <span className="truncate">Workspace</span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {/* Theme toggle */}
        <TopbarButton label={resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"} onClick={toggleTheme}>
          <Icon name={resolvedTheme === "dark" ? "sun" : "moon"} className="h-5 w-5" />
        </TopbarButton>

        {user ? (
          <div className="relative">
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-2 py-1 transition-colors hover:bg-slate-50 dark:border-white/10 dark:bg-white/[0.04] dark:hover:bg-white/[0.08]"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-gradient text-xs font-bold text-white">
                {initials(user.username)}
              </span>
              <span className="hidden text-sm font-medium text-slate-800 dark:text-slate-200 sm:block">{user.username}</span>
              <Icon name="chevronDown" className="h-4 w-4 text-slate-400" />
            </button>
            {menuOpen && (
              <Fragment>
                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 z-20 mt-2 w-56 animate-scale-in rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl dark:border-white/10 dark:bg-slate-900">
                  <div className="border-b border-slate-100 px-3 py-2.5 dark:border-white/8">
                    <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{user.username}</p>
                    <p className="truncate text-xs text-slate-500 dark:text-slate-400">{user.email}</p>
                  </div>
                  <MenuLink to="/profile" onClose={() => setMenuOpen(false)}>Profile</MenuLink>
                  <MenuLink to="/settings" onClose={() => setMenuOpen(false)}>Settings</MenuLink>
                  {user.role === "admin" && <MenuLink to="/admin" onClose={() => setMenuOpen(false)}>Admin Dashboard</MenuLink>}
                  <div className="my-1 border-t border-slate-100 dark:border-white/8" />
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="block w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
                  >
                    Sign out
                  </button>
                </div>
              </Fragment>
            )}
          </div>
        ) : (
          <Link
            to="/login"
            className="rounded-xl bg-brand-gradient px-4 py-2 text-sm font-semibold text-white shadow-glow transition-all hover:brightness-110"
          >
            Sign in
          </Link>
        )}
      </div>
    </header>
  );
}

function TopbarButton({
  children,
  onClick,
  label,
}: {
  children: React.ReactNode;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white"
    >
      {children}
    </button>
  );
}

function MenuLink({ to, children, onClose }: { to: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <Link
      to={to}
      onClick={onClose}
      className="block rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-white/5 dark:hover:text-white"
    >
      {children}
    </Link>
  );
}

/* ─── Shared logo ─── */

export function Logo({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn("flex items-center gap-2.5", className)}>
      <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-glow">
        <Icon name="logo" className="h-5 w-5" strokeWidth={1.9} />
        <span className="absolute inset-0 rounded-xl bg-brand-gradient opacity-40 blur-lg" aria-hidden />
      </span>
      <span className="font-display text-lg font-bold tracking-tight text-slate-900 dark:text-white">
        Vision<span className="text-gradient">3D</span> AI
      </span>
    </Link>
  );
}

/* ─── Mobile bottom nav ─── */

function MobileNav() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return null;
  return (
    <nav
      aria-label="Mobile navigation"
      className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-around border-t border-slate-200 bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] backdrop-blur-2xl dark:border-white/8 dark:bg-ink-900/90 lg:hidden"
    >
      {primaryNav.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "flex flex-col items-center gap-1 rounded-xl px-4 py-2.5 text-[11px] font-medium transition-colors",
              isActive ? "text-brand-600 dark:text-brand-300" : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300",
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon name={item.icon} className={cn("h-5 w-5", isActive && "drop-shadow-[0_0_8px_rgba(139,92,246,0.8)]")} />
              {item.label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}