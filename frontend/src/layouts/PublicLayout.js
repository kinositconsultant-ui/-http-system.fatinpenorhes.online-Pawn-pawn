import { Link, NavLink, Outlet } from "react-router-dom";
import { useLang } from "../context/LangContext";
import LangToggle from "../components/LangToggle";

const linkClass = ({ isActive }) =>
  `text-sm transition ${
    isActive ? "text-[#1B2D5C] font-semibold" : "text-stone-600 hover:text-[#1B2D5C]"
  }`;

export default function PublicLayout() {
  const { t } = useLang();
  return (
    <div className="min-h-screen flex flex-col bg-[#FAFAF9]">
      <header className="sticky top-0 z-30 glass border-b border-stone-200">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-4 flex items-center justify-between">
          <Link to="/" data-testid="public-brand" className="flex items-center gap-3">
            <img
              src="/brand/logo.jpg"
              alt="Fatin Penhores"
              className="w-12 h-12 rounded-md object-contain bg-white border border-stone-200"
            />
            <div className="leading-tight">
              <div className="font-display text-lg font-semibold text-stone-900">
                Fatin Penhores
              </div>
              <div className="text-[10px] tracking-[0.2em] uppercase text-stone-500">
                Unipessoal, Lda · Pawn & Auction
              </div>
            </div>
          </Link>
          <nav className="hidden md:flex items-center gap-8">
            <NavLink to="/" end className={linkClass} data-testid="public-nav-home">
              {t("home")}
            </NavLink>
            <NavLink to="/auction" className={linkClass} data-testid="public-nav-auction">
              {t("auction_items")}
            </NavLink>
            <NavLink to="/warehouse" className={linkClass} data-testid="public-nav-warehouse">
              {t("warehouse")}
            </NavLink>
            <NavLink to="/about" className={linkClass} data-testid="public-nav-about">
              {t("about")}
            </NavLink>
            <NavLink to="/contact" className={linkClass} data-testid="public-nav-contact">
              {t("contact")}
            </NavLink>
          </nav>
          <div className="flex items-center gap-3">
            <LangToggle />
            <Link
              to="/login"
              data-testid="public-admin-login"
              className="hidden md:inline-flex px-4 py-2 rounded-md text-sm bg-[#1B2D5C] hover:bg-[#0F1B3A] text-white transition"
            >
              {t("admin_login")}
            </Link>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-stone-200 bg-white">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-10 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <img
                src="/brand/logo.jpg"
                alt=""
                className="w-12 h-12 rounded-md object-contain bg-white border border-stone-200"
              />
              <div>
                <div className="font-display text-lg font-semibold text-[#1B2D5C]">
                  FATIN PENHORES
                </div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-stone-500">
                  Unipessoal, Lda
                </div>
              </div>
            </div>
            <p className="text-sm text-stone-600 mt-2 max-w-xs">{t("tagline")}</p>
          </div>
          <div>
            <div className="text-eyebrow mb-3">{t("contact")}</div>
            <p className="text-sm text-stone-600">Caicoli, Dili, Timor-Leste</p>
            <p className="text-sm text-stone-600">Tel: 78372678</p>
            <p className="text-sm text-stone-600">fatinpenhores@gmail.com</p>
          </div>
          <div>
            <div className="text-eyebrow mb-3">Quick Links</div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <Link to="/auction" className="text-stone-600 hover:text-[#1B2D5C]">
                {t("auction_items")}
              </Link>
              <Link to="/warehouse" className="text-stone-600 hover:text-[#1B2D5C]">
                {t("warehouse")}
              </Link>
              <Link to="/about" className="text-stone-600 hover:text-[#1B2D5C]">
                {t("about")}
              </Link>
              <Link to="/contact" className="text-stone-600 hover:text-[#1B2D5C]">
                {t("contact")}
              </Link>
            </div>
          </div>
        </div>
        <div className="border-t border-stone-200 py-4 text-center text-xs text-stone-500">
          © {new Date().getFullYear()} Fatin Penhores. All Rights Reserved.
        </div>
      </footer>
    </div>
  );
}
