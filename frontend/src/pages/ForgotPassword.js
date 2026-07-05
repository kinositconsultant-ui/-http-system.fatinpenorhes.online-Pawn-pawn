import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { ArrowLeft, Mail, CheckCircle2, Loader2 } from "lucide-react";
import LangToggle from "../components/LangToggle";

export default function ForgotPassword() {
  const { t } = useLang();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.post("/auth/forgot-password", { email: email.trim() });
      setSent(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Request failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F5F4F1] px-4">
      <div className="absolute top-4 left-4">
        <Link
          to="/login"
          className="inline-flex items-center gap-2 text-sm text-stone-700 hover:text-[#1B2D5C] font-medium"
          data-testid="forgot-back-to-login"
        >
          <ArrowLeft className="w-4 h-4" /> {t("back_to_login")}
        </Link>
      </div>
      <div className="absolute top-4 right-4">
        <LangToggle />
      </div>

      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg border border-stone-200 p-8" data-testid="forgot-password-card">
        <div className="text-eyebrow text-[#1B2D5C]">FATIN PENHORES</div>
        <h1 className="font-display text-2xl sm:text-3xl font-semibold mt-1 text-stone-900">
          {t("reset_password")}
        </h1>

        {!sent ? (
          <form onSubmit={onSubmit} className="space-y-4 mt-6" data-testid="forgot-form">
            <p className="text-sm text-stone-600">{t("reset_password_desc")}</p>
            <div className="space-y-1.5">
              <Label htmlFor="forgot-email" className="text-xs uppercase tracking-wider text-stone-500">
                {t("email")}
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
                <Input
                  id="forgot-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                  autoComplete="email"
                  placeholder="you@fatinpenhores.tl"
                  className="pl-10 h-11"
                  data-testid="forgot-email"
                />
              </div>
            </div>
            {error && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2" data-testid="forgot-error">
                {error}
              </div>
            )}
            <Button
              type="submit"
              disabled={submitting || !email}
              className="w-full h-11 bg-[#1B2D5C] hover:bg-[#0F1B3A]"
              data-testid="forgot-submit"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> {t("login_signing_in")}
                </>
              ) : (
                t("reset_password")
              )}
            </Button>
          </form>
        ) : (
          <div className="mt-6 space-y-4 text-center" data-testid="forgot-sent">
            <CheckCircle2 className="w-14 h-14 text-emerald-600 mx-auto" />
            <p className="text-sm text-stone-700 leading-relaxed">
              {t("reset_password_sent")}
            </p>
            <p className="text-xs text-stone-500">
              The link expires in 15 minutes and can only be used once.
            </p>
            <Link
              to="/login"
              className="inline-block text-sm text-[#1B2D5C] font-medium hover:underline pt-2"
            >
              {t("back_to_login")}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
