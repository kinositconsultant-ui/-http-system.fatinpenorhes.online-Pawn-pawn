import { useEffect } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { ShieldAlert } from "lucide-react";

/**
 * Wraps a route element and only renders children if the user has access
 * to the given module. Admins always pass. Anyone else must have the
 * module listed in `user.allowed_modules`.
 *
 * When access is denied:
 * - Shows a toast.error explaining the missing module
 * - Renders an inline "no access" panel with a "Back to Dashboard" button
 * - Auto-redirects to /dashboard after 2.5s
 */
export default function ModuleGuard({ module, label, children }) {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";
  const allowed = isAdmin || (user?.allowed_modules || []).includes(module);

  useEffect(() => {
    if (user && !allowed) {
      toast.error(`You don't have access to the ${label || module} module`);
      const t = setTimeout(() => navigate("/dashboard", { replace: true }), 2500);
      return () => clearTimeout(t);
    }
  }, [user, allowed, label, module, navigate, location.pathname]);

  if (user === null) return null; // loading handled by parent
  if (!user) return <Navigate to="/login" replace />;
  if (allowed) return children;

  return (
    <div className="space-y-6" data-testid="module-access-denied">
      <header>
        <div className="text-eyebrow">403</div>
        <h1 className="font-display text-4xl font-semibold mt-1">Access denied</h1>
      </header>
      <div className="rounded-lg border border-red-200 bg-red-50/70 p-8 max-w-2xl">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-full bg-red-100 text-red-700 flex items-center justify-center shrink-0">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div className="flex-1 space-y-2">
            <h2 className="font-display text-lg font-semibold text-red-900">
              You don&apos;t have access to {label || module}
            </h2>
            <p className="text-sm text-red-800/80">
              This module isn&apos;t included in your role&apos;s permissions. If you believe this is
              a mistake, please contact your administrator to add the
              <code className="mx-1 px-1.5 py-0.5 rounded bg-white border border-red-200 text-red-700">
                {module}
              </code>
              module to your account.
            </p>
            <p className="text-xs text-red-700/70">
              Redirecting to dashboard in a moment…
            </p>
            <button
              type="button"
              onClick={() => navigate("/dashboard", { replace: true })}
              data-testid="module-denied-back"
              className="mt-2 inline-flex items-center px-3 py-1.5 rounded-md bg-[#1B2D5C] text-white text-sm hover:bg-[#0F1B3A] transition"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
