import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useLang } from "../../context/LangContext";
import { Car, Bike, Cpu, Truck, Lock, KeyRound } from "lucide-react";
import { toast } from "sonner";

const TOKEN_KEY = "fp_warehouse_token";

export default function Warehouse() {
  const { t, lang } = useLang();
  const T = (en, tet) => (lang === "tet" ? tet : en);

  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) || "");
  const [locked, setLocked] = useState(true);
  const [password, setPassword] = useState("");
  const [unlocking, setUnlocking] = useState(false);
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(false);

  // Check whether a password is configured
  useEffect(() => {
    api.get("/public/warehouse-status").then((r) => setLocked(r.data.locked)).catch(() => {});
  }, []);

  // When we have a token, try fetching content; if 401 → clear and re-prompt
  useEffect(() => {
    if (!token) return;
    setLoading(true);
    api
      .get(`/public/warehouse?unlock_token=${encodeURIComponent(token)}`)
      .then((r) => setRows(r.data))
      .catch(() => {
        sessionStorage.removeItem(TOKEN_KEY);
        setToken("");
        toast.error(T("Session expired. Enter the password again.", "Sesaun hotu. Tama liafuan-xave fila fali."));
      })
      .finally(() => setLoading(false));
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const unlock = async (e) => {
    e?.preventDefault();
    if (!password.trim()) return;
    setUnlocking(true);
    try {
      const { data } = await api.post("/public/warehouse-unlock", { password });
      sessionStorage.setItem(TOKEN_KEY, data.token);
      setToken(data.token);
      setPassword("");
      toast.success(T("Unlocked", "Loke ona"));
    } catch (err) {
      toast.error(err.response?.data?.detail || T("Invalid password", "Liafuan-xave sala"));
    }
    setUnlocking(false);
  };

  // If a password is configured but we don't have a token → show gate
  if (locked && !token) {
    return (
      <section className="min-h-[70vh] bg-white flex items-center justify-center px-6 py-16">
        <div
          className="w-full max-w-md rounded-2xl border border-stone-200 bg-white shadow-lg p-8 space-y-5"
          data-testid="warehouse-gate"
        >
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="w-14 h-14 rounded-full bg-[#1A2A52] text-white flex items-center justify-center shadow-md">
              <Lock className="w-6 h-6" />
            </div>
            <h1 className="font-display text-2xl font-bold text-[#1A2A52]">
              {T("Warehouse Locked", "Warehouse Xave-hela")}
            </h1>
            <p className="text-sm text-stone-600">
              {T(
                "Enter the access password provided by the administrator to view the warehouse inventory.",
                "Tama liafuan-xave husi administradór hodi haree sasán iha warehouse.",
              )}
            </p>
          </div>
          <form onSubmit={unlock} className="space-y-3">
            <div className="relative">
              <KeyRound className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={T("Password", "Liafuan-xave")}
                data-testid="warehouse-password"
                autoFocus
                className="w-full pl-10 pr-3 py-3 rounded-lg border border-stone-300 focus:border-[#1A2A52] focus:ring-2 focus:ring-[#1A2A52]/20 outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={unlocking}
              data-testid="warehouse-unlock-btn"
              className="w-full py-3 rounded-lg bg-[#1A2A52] hover:bg-[#0F1B3A] text-white font-semibold transition-colors disabled:opacity-50"
            >
              {unlocking ? T("Checking…", "Verifika hela…") : T("Unlock", "Loke")}
            </button>
          </form>
          <p className="text-xs text-stone-500 text-center pt-2">
            {T("Contact us on WhatsApp", "Kontaktu liu husi WhatsApp")}: <a className="text-[#1A2A52] font-semibold" href="https://wa.me/67078372678" target="_blank" rel="noreferrer">+670 78372678</a>
          </p>
        </div>
      </section>
    );
  }

  const filtered = filter === "all" ? rows : rows.filter((r) => r.kind === filter);

  const lock = () => {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken("");
    setRows([]);
  };

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-16 space-y-10">
      <header className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("warehouse")}</div>
          <h1 className="font-display text-4xl sm:text-5xl mt-1 text-[#1A2A52]">
            {T("Warehouse", "Warehouse / Fatin Rai Sasán")}
          </h1>
          <div className="w-20 h-1 bg-[#F0B435] mt-3 rounded-full" />
          <p className="text-stone-600 mt-4 max-w-xl">
            {T(
              "A look at what's currently inside our Dili warehouse. Most items remain available for redemption by their owners.",
              "Iha ne'e mak fatin ne'ebé ami rai karreta, motor no sasán Penhores/lelaun.",
            )}
          </p>
        </div>
        {locked && (
          <button
            onClick={lock}
            data-testid="warehouse-lock-again"
            className="text-xs text-stone-500 hover:text-[#1A2A52] flex items-center gap-1"
          >
            <Lock className="w-3.5 h-3.5" /> {T("Lock", "Xave")}
          </button>
        )}
      </header>

      <div className="flex gap-2 flex-wrap" data-testid="warehouse-filters">
        {[
          { k: "all", label: T("All", "Hotu") },
          { k: "car", label: t("car"), Icon: Car },
          { k: "motorcycle", label: t("motorcycle"), Icon: Bike },
          { k: "electronic", label: t("electronic"), Icon: Cpu },
          { k: "pezadu", label: t("pezadu"), Icon: Truck },
        ].map((f) => (
          <button
            key={f.k}
            onClick={() => setFilter(f.k)}
            data-testid={`warehouse-filter-${f.k}`}
            className={`px-4 py-2 rounded-full text-sm border transition ${
              filter === f.k
                ? "bg-[#1A2A52] border-[#1A2A52] text-white"
                : "bg-white border-stone-200 text-stone-700 hover:border-[#1A2A52]"
            }`}
          >
            {f.Icon ? <f.Icon className="inline w-3.5 h-3.5 mr-1 -mt-0.5" /> : null}
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="p-10 text-center text-stone-500">{T("Loading…", "Karega hela…")}</div>
      ) : filtered.length === 0 ? (
        <div className="p-10 rounded-lg border border-dashed border-stone-300 text-center text-stone-500">
          {t("no_items")}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {filtered.map((r) => (
            <article
              key={r.id}
              className="rounded-lg border border-stone-200 bg-white overflow-hidden hover:shadow-md transition-shadow"
              data-testid={`warehouse-item-${r.id}`}
            >
              <div className="aspect-square bg-stone-100">
                {r.photo_url ? (
                  <img alt="" src={r.photo_url} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-stone-400">
                    {r.kind === "car" ? (
                      <Car className="w-10 h-10" />
                    ) : r.kind === "motorcycle" ? (
                      <Bike className="w-10 h-10" />
                    ) : r.kind === "pezadu" ? (
                      <Truck className="w-10 h-10" />
                    ) : (
                      <Cpu className="w-10 h-10" />
                    )}
                  </div>
                )}
              </div>
              <div className="p-4">
                <div className="text-xs uppercase tracking-wider text-stone-500">{r.kind}</div>
                <div className="font-display text-base mt-1">
                  {r.brand} {r.model}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
