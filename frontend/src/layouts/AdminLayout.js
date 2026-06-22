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
  { to: "/dashboard", key: "dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/clients", key: "clients", icon: Users, testid: "nav-clients" },
  { to: "/items", key: "items", icon: Package, testid: "nav-items" },
  { to: "/contracts", key: "contracts", icon: FileText, testid: "nav-contracts" },
  { to: "/payments", key: "payments", icon: Wallet, testid: "nav-payments" },
  { to: "/auctions", key: "auctions", icon: Gavel, testid: "nav-auctions" },
  { to: "/reports", key: "reports", icon: BarChart3, testid: "nav-reports" },
  { to: "/users", key: "users", icon: UserCog, testid: "nav-users", adminOnly: true },
  { to: "/settings", key: "settings", icon: SettingsIcon, testid: "nav-settings", adminOnly: true },
  { to: "/audit-log", key: "audit_log", icon: ScrollText, testid: "nav-audit-log", adminOnly: true },
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
      <aside className="w-64 shrink-0 border-r border-stone-200 bg-white px-5 py-7 flex flex-col">
        <div className="mb-8 flex items-center gap-3">
          <img
            src="/brand/logo.jpg"
            alt="FP"
            className="w-12 h-12 rounded-md object-contain bg-white border border-stone-200"
          />
          <div>
            <div className="text-eyebrow text-stone-500 mb-0.5">Admin Console</div>
            <div className="font-display text-lg font-semibold text-[#1B2D5C] leading-tight">
              Fatin Penhores
            </div>
          </div>
        </div>
        <nav className="space-y-1 flex-1">
          {links.map((l) => {
            if (l.adminOnly && user?.role !== "admin") return null;
            const Icon = l.icon;
            return (
              <NavLink
                key={l.to}
                to={l.to}
                data-testid={l.testid}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition ${
                    isActive
                      ? "bg-[#1B2D5C] text-white"
                      : "text-stone-600 hover:bg-stone-100"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {t(l.key)}
              </NavLink>
            );
          })}
        </nav>
        <div className="pt-4 border-t border-stone-200 mt-4 space-y-3">
          <LangToggle />
          <div className="text-xs text-stone-500">
            {user?.name} · {user?.role}
          </div>
          <button
            onClick={handleLogout}
            data-testid="logout-btn"
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm bg-stone-100 hover:bg-stone-200 transition"
          >
            <LogOut className="w-4 h-4" /> {t("logout")}
          </button>
          <div className="text-[10px] text-stone-400 leading-relaxed pt-1">
            FATIN PENHORES UNIP., LDA<br />
            Caicoli, Dili, Timor-Leste<br />
            Tel: 78372678<br />
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
