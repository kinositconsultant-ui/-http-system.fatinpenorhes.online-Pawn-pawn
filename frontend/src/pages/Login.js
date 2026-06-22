import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import LangToggle from "../components/LangToggle";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login, error } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    const ok = await login(email.trim(), password);
    setSubmitting(false);
    if (ok) navigate("/dashboard");
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#FAFAF9]">
      <div className="hidden lg:block relative overflow-hidden bg-[#0F1B3A]">
        <div className="absolute inset-0 opacity-25">
          <img
            alt=""
            src="https://images.unsplash.com/photo-1591325408953-ef9298125f96?crop=entropy&cs=srgb&fm=jpg&q=85"
            className="w-full h-full object-cover"
          />
        </div>
        <div className="relative h-full p-12 flex flex-col justify-between text-white">
          <Link to="/" data-testid="login-brand" className="flex items-center gap-4">
            <img
              src="/brand/logo.jpg"
              alt=""
              className="w-16 h-16 rounded-md bg-white object-contain p-1"
            />
            <div>
              <div className="font-display text-2xl font-semibold">Fatin Penhores</div>
              <div className="text-[10px] uppercase tracking-[0.3em] opacity-80">
                Unipessoal, Lda
              </div>
            </div>
          </Link>
          <div>
            <div className="text-xs uppercase tracking-[0.3em] opacity-80 mb-3">
              {t("tagline")}
            </div>
            <h2 className="font-display text-4xl leading-tight">
              {t("hero_title")}
            </h2>
            <div className="mt-10 text-xs opacity-70 leading-relaxed">
              FATIN PENHORES UNIPESSOAL, LDA<br />
              Caicoli, Dili, Timor-Leste · Tel: 78372678<br />
              fatinpenhores@gmail.com
            </div>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center p-8 relative">
        <div className="absolute top-6 right-6">
          <LangToggle />
        </div>
        <form
          onSubmit={onSubmit}
          className="w-full max-w-md space-y-6 bg-white p-8 rounded-lg border border-stone-200 shadow-sm"
          data-testid="login-form"
        >
          <div>
            <div className="text-eyebrow mb-2">{t("welcome_back")}</div>
            <h1 className="font-display text-3xl font-semibold text-stone-900">
              {t("sign_in")}
            </h1>
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">{t("email")}</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              data-testid="login-email"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">{t("password")}</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              data-testid="login-password"
            />
          </div>
          {error ? (
            <div
              className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2"
              data-testid="login-error"
            >
              {error}
            </div>
          ) : null}
          <Button
            type="submit"
            disabled={submitting}
            className="w-full bg-[#1B2D5C] hover:bg-[#0F1B3A]"
            data-testid="login-submit"
          >
            {submitting ? "…" : t("sign_in")}
          </Button>
          <div className="text-xs text-stone-500 text-center">
            <Link to="/" className="underline">
              ← {t("home")}
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
