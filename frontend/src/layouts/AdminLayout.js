import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import LangToggle from "../components/LangToggle";
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

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-[#FAFAF9] text-stone-900">
      <aside className="w-64 shrink-0 bg-[#4A5568] px-4 py-6 flex flex-col text-white shadow-xl">
        <div className="mb-5 flex flex-col items-center gap-2">
          <div className="w-24 h-24 rounded-md bg-white p-2 shadow-md flex items-center justify-center">
            <img
              src="/brand/logo.jpg"
              alt="FP"
              className="w-full h-full object-contain"
            />
          </div>
          <div className="text-center">
            <div className="font-display text-xl font-semibold text-white tracking-wide drop-shadow-sm">
              Fatin Penhores
            </div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-white/60 mt-0.5">
              Admin Console
            </div>
          </div>
        </div>

        <div className="h-px bg-white/10 mb-3" />

        <nav className="space-y-2 flex-1">
          {links.map((l) => {
            if (l.adminOnly && user?.role !== "admin") return null;
            // Module-level visibility: admin sees everything; others must have the module in allowed_modules
            const allowed = user?.role === "admin" || (user?.allowed_modules || []).includes(l.module);
            if (!allowed) return null;
            const Icon = l.icon;
            return (
              <NavLink
                key={l.to}
                to={l.to}
                data-testid={l.testid}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-2.5 rounded-full text-sm font-semibold transition-all shadow-sm ${
                    isActive
                      ? "bg-[#1B2D5C] text-white shadow-md ring-1 ring-white/20"
                      : "bg-white text-[#1B2D5C] hover:bg-[#FFF8E1] hover:text-[#1B2D5C]"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {t(l.key)}
              </NavLink>
            );
          })}
        </nav>

        <div className="pt-4 mt-4 space-y-3">
          <div className="h-px bg-white/10" />
          <LangToggle />
          <div className="text-xs text-white/70">
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
      </aside>
      <main className="flex-1 overflow-x-hidden">
        <div className="max-w-7xl mx-auto px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
