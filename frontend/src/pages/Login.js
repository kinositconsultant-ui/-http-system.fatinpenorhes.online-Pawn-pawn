import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import LangToggle from "../components/LangToggle";
import {
  Eye,
  EyeOff,
  ShieldCheck,
  ArrowLeft,
  Loader2,
  Lock,
  Mail,
} from "lucide-react";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [remember, setRemember] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const { login, error } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    const ok = await login(email.trim(), password, remember);
    setSubmitting(false);
    if (ok) navigate("/dashboard");
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr,1fr] bg-[#F5F4F1] text-stone-900">
      {/* ==================== LEFT: BRAND / HERO ==================== */}
      <div className="hidden lg:flex relative overflow-hidden bg-[#0B1633]">
        {/* Background image with heavy navy overlay for readable text */}
        <img
          alt=""
          aria-hidden="true"
          src="https://images.unsplash.com/photo-1591325408953-ef9298125f96?crop=entropy&cs=srgb&fm=jpg&q=85"
          className="absolute inset-0 w-full h-full object-cover opacity-40"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-[#0B1633]/95 via-[#0F1B3A]/85 to-[#1B2D5C]/70" />

        {/* Subtle grain / noise for texture */}
        <div
          className="absolute inset-0 opacity-[0.15] mix-blend-overlay pointer-events-none"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><filter id='n'><feTurbulence baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.55'/></svg>\")",
          }}
        />

        {/* Decorative accent shapes */}
        <div className="absolute -top-32 -right-32 w-96 h-96 rounded-full bg-[#C17767]/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-40 -left-32 w-[28rem] h-[28rem] rounded-full bg-[#1B2D5C]/40 blur-3xl pointer-events-none" />

        <div className="relative w-full h-full p-10 xl:p-14 flex flex-col justify-between text-white z-10">
          {/* Top: brand */}
          <Link
            to="/"
            data-testid="login-brand"
            className="flex items-center gap-4 group w-fit"
          >
            <div className="w-14 h-14 rounded-md bg-white p-1.5 shadow-lg ring-1 ring-white/20 transition-transform group-hover:scale-[1.02]">
              <img
                src="/brand/logo.jpg"
                alt="FP"
                className="w-full h-full object-contain"
              />
            </div>
            <div className="leading-tight">
              <div className="font-display text-xl xl:text-2xl font-semibold tracking-wide">
                Fatin Penhores
              </div>
              <div className="text-[10px] uppercase tracking-[0.32em] text-white/60 mt-0.5">
                Unipessoal, Lda · Pawn Console
              </div>
            </div>
          </Link>

          {/* Middle: tagline + copy */}
          <div className="max-w-lg">
            <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.28em] text-white/70 mb-5 px-3 py-1 rounded-full border border-white/15 bg-white/5 backdrop-blur-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {t("tagline")}
            </div>
            <h2 className="font-display text-4xl xl:text-5xl leading-[1.1] tracking-tight">
              {t("hero_title")}
            </h2>
            <p className="mt-5 text-sm xl:text-base text-white/70 leading-relaxed max-w-md">
              {t("login_workspace_body")}
            </p>

            {/* Trust chips */}
            <div className="mt-8 grid grid-cols-3 gap-3 max-w-md">
              {[
                { k: "10+", v: t("login_years_label") },
                { k: "24/7", v: t("login_encrypted_label") },
                { k: "USD", v: t("login_sameday_label") },
              ].map((s) => (
                <div
                  key={s.k}
                  className="rounded-lg border border-white/10 bg-white/[0.03] backdrop-blur-sm px-3 py-3"
                >
                  <div className="font-display text-lg text-white">{s.k}</div>
                  <div className="text-[10px] uppercase tracking-widest text-white/50 mt-1">
                    {s.v}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom: company footer */}
          <div className="text-[10px] uppercase tracking-[0.28em] text-white/40 leading-relaxed">
            FATIN PENHORES UNIPESSOAL, LDA
            <br />
            Caicoli, Dili, Timor-Leste · WhatsApp +670 78372678
            <br />
            © 2026 All Rights Reserved.
          </div>
        </div>
      </div>

      {/* ==================== RIGHT: FORM ==================== */}
      <div className="relative flex items-center justify-center px-6 py-10 md:px-10 lg:px-14 bg-[#F5F4F1]">
        {/* Subtle dot-grid background pattern */}
        <div
          className="absolute inset-0 opacity-[0.35] pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(circle, rgba(15,27,58,0.08) 1px, transparent 1px)",
            backgroundSize: "22px 22px",
          }}
        />

        {/* Top controls: language + home link */}
        <div className="absolute top-5 left-5 right-5 flex items-center justify-between z-10">
          <Link
            to="/"
            className="text-xs text-stone-500 hover:text-[#1B2D5C] inline-flex items-center gap-1.5 transition-colors"
            data-testid="login-home-link"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> {t("home")}
          </Link>
          <LangToggle />
        </div>

        {/* Mobile-only compact brand (shown when hero panel hidden) */}
        <div className="lg:hidden absolute top-16 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
          <div className="w-14 h-14 rounded-md bg-white p-1.5 shadow-md ring-1 ring-stone-200">
            <img
              src="/brand/logo.jpg"
              alt="FP"
              className="w-full h-full object-contain"
            />
          </div>
          <div className="text-center">
            <div className="font-display text-lg font-semibold text-[#0F1B3A]">
              Fatin Penhores
            </div>
            <div className="text-[9px] uppercase tracking-[0.28em] text-stone-500">
              Pawn Console
            </div>
          </div>
        </div>

        <form
          onSubmit={onSubmit}
          className="relative w-full max-w-md bg-white/95 backdrop-blur-md rounded-2xl border border-stone-200 shadow-[0_10px_50px_-15px_rgba(15,27,58,0.15)] p-7 md:p-9 mt-24 lg:mt-0 z-10"
          data-testid="login-form"
        >
          <div className="mb-7">
            <div className="text-[10px] uppercase tracking-[0.32em] text-stone-500 mb-2">
              {t("welcome_back")}
            </div>
            <h1 className="font-display text-3xl md:text-[2rem] font-semibold text-stone-900 leading-tight">
              {t("sign_in")}
            </h1>
            <div className="mt-3 text-sm text-stone-500">
              {t("login_subtitle")}
            </div>
          </div>

          {/* Email */}
          <div className="space-y-1.5 mb-4">
            <Label
              htmlFor="email"
              className="text-[11px] uppercase tracking-widest text-stone-600"
            >
              {t("email")}
            </Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="username"
                placeholder="you@fatinpenhores.tl"
                className="pl-9 h-11 bg-white border-stone-200 focus-visible:ring-[#1B2D5C]/25 focus-visible:border-[#1B2D5C]"
                data-testid="login-email"
              />
            </div>
          </div>

          {/* Password */}
          <div className="space-y-1.5 mb-5">
            <Label
              htmlFor="password"
              className="text-[11px] uppercase tracking-widest text-stone-600"
            >
              {t("password")}
            </Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
              <Input
                id="password"
                type={showPwd ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
                className="pl-9 pr-11 h-11 bg-white border-stone-200 focus-visible:ring-[#1B2D5C]/25 focus-visible:border-[#1B2D5C]"
                data-testid="login-password"
              />
              <button
                type="button"
                onClick={() => setShowPwd((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-stone-400 hover:text-[#1B2D5C] hover:bg-stone-100 transition-colors"
                aria-label={showPwd ? "Hide password" : "Show password"}
                data-testid="login-toggle-password"
                tabIndex={-1}
              >
                {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {error ? (
            <div
              className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2.5 flex items-start gap-2"
              data-testid="login-error"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-red-600 mt-1.5 shrink-0" />
              <span>{error}</span>
            </div>
          ) : null}

          <div className="flex items-center justify-between mb-4 -mt-1">
            <label className="inline-flex items-center gap-2 text-sm text-stone-700 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="w-4 h-4 rounded border-stone-300 text-[#1B2D5C] focus:ring-[#1B2D5C]/40"
                data-testid="login-remember"
              />
              <span>{t("remember_me")}</span>
            </label>
            <Link
              to="/forgot-password"
              className="text-sm text-[#1B2D5C] font-medium hover:underline"
              data-testid="login-forgot-link"
            >
              {t("forgot_password")}
            </Link>
          </div>

          <Button
            type="submit"
            disabled={submitting}
            className="w-full h-11 bg-[#1B2D5C] hover:bg-[#0F1B3A] text-white font-semibold tracking-wide shadow-md hover:shadow-lg transition-all disabled:opacity-70"
            data-testid="login-submit"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> {t("login_signing_in")}
              </>
            ) : (
              t("sign_in")
            )}
          </Button>

          {/* Security note */}
          <div className="mt-6 flex items-center gap-2 text-[11px] text-stone-500 justify-center">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            {t("login_encrypted_note")}
          </div>
        </form>

        {/* Footer */}
        <div className="absolute bottom-5 left-0 right-0 text-center text-[10px] uppercase tracking-[0.28em] text-stone-400 z-10">
          © 2026 Fatin Penhores · Caicoli, Dili
        </div>
      </div>
    </div>
  );
}
