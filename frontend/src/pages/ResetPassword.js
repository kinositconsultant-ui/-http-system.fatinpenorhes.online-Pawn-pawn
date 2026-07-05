import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { ArrowLeft, Lock, CheckCircle2, Loader2, AlertTriangle, Eye, EyeOff } from "lucide-react";
import LangToggle from "../components/LangToggle";

export default function ResetPassword() {
  const { t } = useLang();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";
  const [info, setInfo] = useState(null); // null=loading, object=valid, false=invalid
  const [pwd, setPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) {
      setInfo(false);
      return;
    }
    api
      .get(`/auth/reset-token-info?token=${encodeURIComponent(token)}`)
      .then((r) => setInfo(r.data))
      .catch(() => setInfo(false));
  }, [token]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (pwd.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (pwd !== confirm) {
      setError(t("passwords_dont_match"));
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: pwd });
      setDone(true);
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      setError(err.response?.data?.detail || "Reset failed. Please request a new link.");
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
          data-testid="reset-back-to-login"
        >
          <ArrowLeft className="w-4 h-4" /> {t("back_to_login")}
        </Link>
      </div>
      <div className="absolute top-4 right-4">
        <LangToggle />
      </div>

      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg border border-stone-200 p-8" data-testid="reset-password-card">
        <div className="text-eyebrow text-[#1B2D5C]">FATIN PENHORES</div>
        <h1 className="font-display text-2xl sm:text-3xl font-semibold mt-1 text-stone-900">
          {t("reset_password")}
        </h1>

        {info === null && (
          <div className="mt-6 flex items-center justify-center py-8" data-testid="reset-loading">
            <Loader2 className="w-6 h-6 animate-spin text-stone-400" />
          </div>
        )}

        {info === false && (
          <div className="mt-6 text-center space-y-4" data-testid="reset-invalid">
            <AlertTriangle className="w-14 h-14 text-red-500 mx-auto" />
            <p className="text-sm text-stone-700">{t("reset_link_expired")}</p>
            <Link
              to="/forgot-password"
              className="inline-block text-sm text-[#1B2D5C] font-medium hover:underline"
            >
              Request a new reset link
            </Link>
          </div>
        )}

        {info && !done && (
          <form onSubmit={onSubmit} className="space-y-4 mt-6" data-testid="reset-form">
            <p className="text-sm text-stone-600">
              Resetting password for <b>{info.email_masked}</b>. Choose a new password (min 8 chars).
            </p>

            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-stone-500">
                {t("reset_new_password")}
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
                <Input
                  type={showPwd ? "text" : "password"}
                  value={pwd}
                  onChange={(e) => setPwd(e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  className="pl-10 pr-10 h-11"
                  data-testid="reset-new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700"
                  aria-label={showPwd ? "Hide password" : "Show password"}
                  tabIndex={-1}
                >
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-stone-500">
                {t("reset_confirm")}
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
                <Input
                  type={showPwd ? "text" : "password"}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  className="pl-10 h-11"
                  data-testid="reset-confirm-password"
                />
              </div>
            </div>

            {error && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2" data-testid="reset-error">
                {error}
              </div>
            )}
            <Button
              type="submit"
              disabled={submitting || !pwd || !confirm}
              className="w-full h-11 bg-[#1B2D5C] hover:bg-[#0F1B3A]"
              data-testid="reset-submit"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Updating…
                </>
              ) : (
                t("reset_password")
              )}
            </Button>
          </form>
        )}

        {done && (
          <div className="mt-6 text-center space-y-4" data-testid="reset-done">
            <CheckCircle2 className="w-14 h-14 text-emerald-600 mx-auto" />
            <p className="text-sm text-stone-700">{t("reset_password_success")}</p>
            <p className="text-xs text-stone-500">Redirecting to sign in…</p>
          </div>
        )}
      </div>
    </div>
  );
}
