import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useLang } from "../context/LangContext";
import LangToggle from "../components/LangToggle";
import { Phone } from "lucide-react";

const navItemClass = ({ isActive }) =>
  `text-sm font-semibold tracking-wider uppercase transition-colors px-1 py-2 border-b-2 ${
    isActive
      ? "text-[#F0B435] border-[#F0B435]"
      : "text-white/90 hover:text-[#F0B435] border-transparent hover:border-[#F0B435]/40"
  }`;

export default function PublicLayout() {
  const { t } = useLang();
  const location = useLocation();
  const showWA = !location.pathname.startsWith("/login");

  return (
    <div className="min-h-screen flex flex-col bg-[#FAFAF9]">
      {/* Top navy bar */}
      <header
        className="sticky top-0 z-30 bg-[#1A2A52] shadow-md"
        data-testid="public-header"
      >
        <div className="max-w-7xl mx-auto px-4 lg:px-8">
          <div className="flex items-center justify-between gap-4 min-h-[88px]">
            {/* Logo card — overlaps below header */}
            <Link
              to="/"
              data-testid="public-brand"
              className="flex items-center gap-3 relative"
            >
              <div className="absolute -bottom-5 left-0 w-[78px] h-[78px] rounded-md bg-white shadow-md border border-white/40 p-1 hidden sm:block">
                <img
                  src="/brand/logo.jpg"
                  alt="FP"
                  className="w-full h-full object-contain"
                />
              </div>
              <div className="sm:ml-[92px] leading-tight">
                <div className="font-display text-xl font-bold text-white tracking-wide">
                  FATIN PENHORES
                </div>
                <div className="text-[10px] tracking-[0.25em] uppercase text-white/70">
                  Unipessoal, Lda
                </div>
              </div>
            </Link>

            {/* Nav */}
            <nav className="hidden lg:flex items-center gap-7">
              <NavLink to="/" end className={navItemClass} data-testid="public-nav-home">
                {t("home")}
              </NavLink>
              <NavLink to="/about" className={navItemClass} data-testid="public-nav-about">
                {t("about")}
              </NavLink>
              <NavLink to="/services" className={navItemClass} data-testid="public-nav-services">
                {t("services")}
              </NavLink>
              <NavLink to="/auction" className={navItemClass} data-testid="public-nav-auction">
                {t("auction_items")}
              </NavLink>
              <NavLink to="/warehouse" className={navItemClass} data-testid="public-nav-warehouse">
                {t("warehouse")}
              </NavLink>
              <NavLink to="/simulasaun" className={navItemClass} data-testid="public-nav-simulasaun">
                {t("simulator")}
              </NavLink>
              <NavLink to="/faq" className={navItemClass} data-testid="public-nav-faq">
                {t("faq")}
              </NavLink>
              <NavLink to="/contact" className={navItemClass} data-testid="public-nav-contact">
                {t("contact")}
              </NavLink>
            </nav>

            <div className="flex items-center gap-3">
              <LangToggle />
              <Link
                to="/login"
                data-testid="public-admin-login"
                className="hidden md:inline-flex px-3 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider border border-white/30 text-white hover:bg-white hover:text-[#1A2A52] transition"
              >
                {t("admin_login")}
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      {/* Floating WhatsApp button */}
      {showWA && (
        <a
          href="https://wa.me/67078372678"
          target="_blank"
          rel="noopener noreferrer"
          data-testid="public-whatsapp-fab"
          className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full bg-[#25D366] hover:bg-[#1EA952] text-white shadow-xl flex items-center justify-center transition-colors"
          title="WhatsApp +670 78372678"
        >
          <Phone className="w-6 h-6" />
        </a>
      )}

      <footer className="border-t border-stone-200 bg-[#1A2A52] text-white/90 mt-12">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-10 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <img
                src="/brand/logo.jpg"
                alt=""
                className="w-12 h-12 rounded-md object-contain bg-white p-1"
              />
              <div>
                <div className="font-display text-lg font-bold text-white">
                  FATIN PENHORES
                </div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-white/60">
                  Unipessoal, Lda
                </div>
              </div>
            </div>
            <p className="text-sm text-white/80 mt-2 max-w-xs">{t("tagline")}</p>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-[#F0B435] mb-3 font-semibold">
              {t("contact")}
            </div>
            <p className="text-sm text-white/80">Caicoli, Dili, Timor-Leste</p>
            <p className="text-sm text-white/80">WhatsApp: +670 78372678</p>
            <p className="text-sm text-white/80">fatinpenhores@gmail.com</p>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-[#F0B435] mb-3 font-semibold">
              Quick Links
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <Link to="/auction" className="text-white/80 hover:text-[#F0B435]">
                {t("auction_items")}
              </Link>
              <Link to="/warehouse" className="text-white/80 hover:text-[#F0B435]">
                {t("warehouse")}
              </Link>
              <Link to="/about" className="text-white/80 hover:text-[#F0B435]">
                {t("about")}
              </Link>
              <Link to="/contact" className="text-white/80 hover:text-[#F0B435]">
                {t("contact")}
              </Link>
              <Link to="/simulasaun" className="text-white/80 hover:text-[#F0B435]">
                {t("simulator")}
              </Link>
              <Link to="/faq" className="text-white/80 hover:text-[#F0B435]">
                {t("faq")}
              </Link>
            </div>
          </div>
        </div>
        <div className="border-t border-white/10 py-4 text-center text-xs text-white/60">
          © {new Date().getFullYear()} FATIN PENHORES UNIPESSOAL, LDA. All Rights Reserved.
        </div>
      </footer>
    </div>
  );
}
