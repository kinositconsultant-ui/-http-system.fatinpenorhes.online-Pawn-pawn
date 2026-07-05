import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import { API_BASE, fileUrl } from "../../lib/api";
import { CheckCircle2, XCircle, ShieldAlert, Clock, IdCard, ExternalLink } from "lucide-react";

/**
 * Public "Verify Member" page — reached from the QR on a physical member ID card.
 * Anyone (no login) can scan and see whether the card is currently valid.
 * We deliberately show minimal PII: name + photo + expiry + status.
 */
export default function VerifyMember() {
  const { token } = useParams();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/public/verify/${token}`);
        if (alive) setData(r.data);
      } catch (e) {
        if (alive) setErr(e.response?.data?.detail || "Network error");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [token]);

  const status = data?.status || "unknown";
  const valid = data?.valid === true;

  const badge =
    status === "active" ? {
      Icon: CheckCircle2,
      label: "Valid Member",
      sub: "This ID card is active and issued by Fatin Penhores.",
      tone: "bg-emerald-50 border-emerald-200 text-emerald-800",
      ring: "ring-emerald-500/20",
      dot: "bg-emerald-500",
    } : status === "expired" ? {
      Icon: Clock,
      label: "Expired",
      sub: "This card has passed its expiry date.",
      tone: "bg-amber-50 border-amber-200 text-amber-800",
      ring: "ring-amber-500/20",
      dot: "bg-amber-500",
    } : status === "revoked" ? {
      Icon: ShieldAlert,
      label: "Revoked",
      sub: "This card was revoked by Fatin Penhores.",
      tone: "bg-rose-50 border-rose-200 text-rose-800",
      ring: "ring-rose-500/20",
      dot: "bg-rose-500",
    } : {
      Icon: XCircle,
      label: "Not Found",
      sub: "No member matches this code. The card may be invalid or altered.",
      tone: "bg-stone-100 border-stone-200 text-stone-700",
      ring: "ring-stone-400/20",
      dot: "bg-stone-500",
    };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0F1B3A] via-[#1B2D5C] to-[#0F1B3A] flex flex-col" data-testid="verify-page">
      {/* Top brand strip */}
      <header className="px-6 py-5 flex items-center justify-between border-b border-white/10">
        <Link to="/" className="flex items-center gap-3 text-white hover:opacity-90">
          <div className="w-9 h-9 rounded-md bg-white/10 flex items-center justify-center">
            <IdCard className="w-5 h-5" />
          </div>
          <div className="leading-tight">
            <div className="font-semibold">FATIN PENHORES</div>
            <div className="text-[10px] uppercase tracking-widest text-white/60">Unipessoal, LDA</div>
          </div>
        </Link>
        <Link to="/" className="text-xs text-white/70 hover:text-white flex items-center gap-1">
          <ExternalLink className="w-3 h-3" /> Home
        </Link>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className={`w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl ring-4 ${badge.ring}`}>
          {loading ? (
            <div className="p-10 text-center text-stone-500">Verifying…</div>
          ) : err ? (
            <div className="p-6 text-center text-rose-700 bg-rose-50 rounded-md border border-rose-200">
              {err}
            </div>
          ) : (
            <>
              {/* Status header */}
              <div className={`flex items-center gap-3 p-4 rounded-xl border ${badge.tone}`} data-testid={`verify-status-${status}`}>
                <badge.Icon className="w-8 h-8 shrink-0" />
                <div>
                  <div className="text-lg font-semibold leading-tight">{badge.label}</div>
                  <div className="text-xs opacity-80">{badge.sub}</div>
                </div>
              </div>

              {/* Member panel */}
              {data?.member_no && (
                <div className="mt-6 flex items-start gap-4">
                  {data.photo_url ? (
                    <img
                      alt=""
                      src={fileUrl(data.photo_url)}
                      className="w-24 h-28 rounded-md object-cover border border-stone-200"
                    />
                  ) : (
                    <div className="w-24 h-28 rounded-md bg-[#1B2D5C] text-white flex items-center justify-center text-2xl font-bold">
                      {(data.full_name || "?").split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase()}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] uppercase tracking-widest text-stone-500">Member</div>
                    <div className="text-lg font-semibold text-stone-900 truncate" data-testid="verify-name">{data.full_name || "—"}</div>
                    <div className="text-xs text-stone-500 mt-2">Member No.</div>
                    <div className="font-mono text-sm text-stone-800" data-testid="verify-member-no">{data.member_no}</div>
                    <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                      <div>
                        <div className="text-stone-500">Issued</div>
                        <div className="text-stone-800" data-testid="verify-issued">{data.issued_at || "—"}</div>
                      </div>
                      <div>
                        <div className="text-stone-500">Expires</div>
                        <div className="text-stone-800" data-testid="verify-expires">{data.expires_at || "—"}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div className="mt-6 pt-4 border-t border-stone-100 text-[10px] uppercase tracking-widest text-stone-400 text-center">
                Verified by Fatin Penhores · <span className="text-stone-500">{new Date().toLocaleDateString()}</span>
              </div>
            </>
          )}
        </div>
      </main>

      <footer className="px-6 py-4 text-center text-xs text-white/60 border-t border-white/10">
        © 2026 Fatin Penhores Unipessoal, Lda · Caicoli, Dili · Timor-Leste
      </footer>
    </div>
  );
}
