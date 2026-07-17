import { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import LangToggle from "../components/LangToggle";
import AppFooter from "../components/AppFooter";
import { api } from "../lib/api";

// Threshold at which the sidebar Reports nav shows a red-pulse alert badge.
// Kept in sync with TAB_ALERT_THRESHOLDS.overdue in /pages/Reports.js.
const REPORTS_ALERT_THRESHOLD = 15;
import {
  LayoutDashboard,
  Users,
  Package,
  FileText,
  Wallet,
  Gavel,
  BarChart3,
  UserCog,
  LogOut,
  Settings as SettingsIcon,
  ScrollText,
  Menu,
  X,
} from "lucide-react";

const links = [
  { to: "/dashboard", key: "dashboard", icon: LayoutDashboard, testid: "nav-dashboard", module: "dashboard" },
  { to: "/clients", key: "clients", icon: Users, testid: "nav-clients", module: "clients" },
  { to: "/items", key: "items", icon: Package, testid: "nav-items", module: "items" },
  { to: "/contracts", key: "contracts", icon: FileText, testid: "nav-contracts", module: "contracts" },
  { to: "/payments", key: "payments", icon: Wallet, testid: "nav-payments", module: "payments" },
  { to: "/auctions", key: "auctions", icon: Gavel, testid: "nav-auctions", module: "auctions" },
  { to: "/reports", key: "reports", icon: BarChart3, testid: "nav-reports", module: "reports" },
  { to: "/finance", key: "finance", icon: Wallet, testid: "nav-finance", module: "finance", adminOnly: true },
  { to: "/users", key: "users", icon: UserCog, testid: "nav-users", module: "users", adminOnly: true },
  { to: "/settings", key: "settings", icon: SettingsIcon, testid: "nav-settings", module: "settings", adminOnly: true },
  { to: "/audit-log", key: "audit_log", icon: ScrollText, testid: "nav-audit-log", module: "audit_log", adminOnly: true },
];

function SidebarBody({ onNavigate, user, t, handleLogout, alertCounts }) {
  return (
    <>
      <div className="mb-5 flex flex-col items-center gap-2">
        <div className="w-20 h-20 lg:w-24 lg:h-24 rounded-md bg-white p-2 shadow-md flex items-center justify-center">
          <img src="/brand/logo.jpg" alt="FP" className="w-full h-full object-contain" />
        </div>
        <div className="text-center">
          <div className="font-display text-lg lg:text-xl font-semibold text-white tracking-wide drop-shadow-sm">
            Fatin Penhores
          </div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-white/60 mt-0.5">
            Admin Console
          </div>
        </div>
      </div>

      <div className="h-px bg-white/10 mb-3" />

      <nav className="space-y-1.5 flex-1 overflow-y-auto min-h-0">
        {links.map((l) => {
          if (l.adminOnly && user?.role !== "admin") return null;
          const allowed = user?.role === "admin" || (user?.allowed_modules || []).includes(l.module);
          if (!allowed) return null;
          const Icon = l.icon;
          const alertCount = alertCounts?.[l.key];
          return (
            <NavLink
              key={l.to}
              to={l.to}
              onClick={onNavigate}
              data-testid={l.testid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-full text-sm font-semibold transition-all shadow-sm ${
                  isActive
                    ? "bg-[#1B2D5C] text-white shadow-md ring-1 ring-white/20"
                    : "bg-white text-[#1B2D5C] hover:bg-[#FFF8E1] hover:text-[#1B2D5C]"
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="truncate flex-1">{t(l.key)}</span>
              {alertCount != null && alertCount > 0 && (
                <span
                  className="text-[10px] font-bold bg-red-600 text-white px-1.5 py-0.5 rounded-full animate-pulse tabular-nums"
                  data-testid={`nav-alert-${l.key}`}
                  title={`${alertCount} ${l.key} needing attention`}
                >
                  {alertCount}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="pt-4 mt-4 space-y-3">
        <div className="h-px bg-white/10" />
        <LangToggle />
        <div className="text-xs text-white/70 truncate">
          {user?.name} · {user?.role}
        </div>
        <button
          onClick={handleLogout}
          data-testid="logout-btn"
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-sm font-semibold bg-[#DC2626] hover:bg-[#B91C1C] text-white transition-colors shadow-md"
        >
          <LogOut className="w-4 h-4" /> {t("logout")}
        </button>
        <div className="text-[10px] text-white/50 leading-relaxed pt-1 text-center">
          FATIN PENHORES UNIP., LDA<br />
          Caicoli, Dili, Timor-Leste<br />
          WhatsApp: +670 78372678<br />
          © 2026 All Rights Reserved.
        </div>
      </div>
    </>
  );
}

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [alertCounts, setAlertCounts] = useState({});

  // Poll report counts every 60s so the sidebar reflects fresh overdue counts
  // without users having to open the Reports page.
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const { data } = await api.get("/reports/v2-counts");
        if (!alive) return;
        const next = {};
        if ((data?.overdue || 0) > REPORTS_ALERT_THRESHOLD) {
          next.reports = data.overdue;
        }
        setAlertCounts(next);
      } catch { /* non-fatal */ }
    };
    tick();
    const id = setInterval(tick, 60000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  // Close the drawer whenever route changes (extra safety in case the NavLink onClick misses)
  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  // Prevent body scroll while drawer is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  // Try to derive a short label for the mobile topbar
  const currentLink = links.find((l) => location.pathname.startsWith(l.to));
  const topLabel = currentLink ? t(currentLink.key) : "Admin";

  return (
    <div className="min-h-screen flex bg-[#FAFAF9] text-stone-900">
      {/* -------- Desktop sidebar (md+) -------- */}
      <aside className="hidden md:flex w-64 shrink-0 bg-[#4A5568] px-4 py-6 flex-col text-white shadow-xl">
        <SidebarBody user={user} t={t} handleLogout={handleLogout} alertCounts={alertCounts} />
      </aside>

      {/* -------- Mobile: top bar + slide-out drawer -------- */}
      {/* Top bar */}
      <div className="md:hidden fixed top-0 inset-x-0 z-40 h-14 bg-[#1B2D5C] text-white flex items-center justify-between px-3 shadow-md">
        <button
          onClick={() => setMobileOpen(true)}
          className="p-2 -ml-1 rounded-md active:bg-white/10"
          aria-label="Open menu"
          data-testid="mobile-menu-btn"
        >
          <Menu className="w-6 h-6" />
        </button>
        <div className="flex items-center gap-2 min-w-0">
          <img src="/brand/logo.jpg" alt="FP" className="w-8 h-8 rounded bg-white p-0.5" />
          <div className="leading-tight min-w-0">
            <div className="text-[10px] uppercase tracking-widest text-white/60 truncate">Fatin Penhores</div>
            <div className="text-sm font-semibold truncate">{topLabel}</div>
          </div>
        </div>
        <div className="w-8 h-8" />{/* spacer to balance the hamburger */}
      </div>

      {/* Backdrop */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          className="md:hidden fixed inset-0 z-40 bg-black/50 backdrop-blur-[1px]"
          data-testid="mobile-menu-backdrop"
        />
      )}

      {/* Drawer */}
      <aside
        className={`md:hidden fixed z-50 top-0 left-0 h-full w-72 max-w-[85vw] bg-[#4A5568] text-white shadow-2xl transform transition-transform duration-300 ease-out flex flex-col px-4 py-6 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        data-testid="mobile-drawer"
      >
        <button
          onClick={() => setMobileOpen(false)}
          className="absolute top-3 right-3 p-2 rounded-md hover:bg-white/10"
          aria-label="Close menu"
          data-testid="mobile-menu-close"
        >
          <X className="w-5 h-5" />
        </button>
        <SidebarBody user={user} t={t} handleLogout={handleLogout} onNavigate={() => setMobileOpen(false)} alertCounts={alertCounts} />
      </aside>

      {/* -------- Main content -------- */}
      <main className="flex-1 overflow-x-hidden pt-14 md:pt-0">
        <div className="max-w-7xl mx-auto px-4 py-4 md:px-8 md:py-8">
          <Outlet />
          <AppFooter />
        </div>
      </main>
    </div>
  );
}
