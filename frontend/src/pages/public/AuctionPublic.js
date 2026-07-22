import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useLang } from "../../context/LangContext";
import { Car, Bike, Cpu, Truck, Lock, KeyRound, Gavel, FileDown } from "lucide-react";
import { toast } from "sonner";

const TOKEN_KEY = "fp_warehouse_token"; // shared with Warehouse — one visitor pass unlocks both
const CATEGORY_META = {
  car: { Icon: Car, color: "#1B2D5C", soft: "bg-[#1B2D5C]/10 text-[#1B2D5C]" },
  motorcycle: { Icon: Bike, color: "#C17767", soft: "bg-[#C17767]/15 text-[#A96253]" },
  electronic: { Icon: Cpu, color: "#4C7F62", soft: "bg-[#4C7F62]/15 text-[#3A6450]" },
  pezadu: { Icon: Truck, color: "#B45309", soft: "bg-amber-100 text-amber-800" },
};
const Icon = ({ kind, className }) => {
  const M = CATEGORY_META[kind] || CATEGORY_META.car;
  const C = M.Icon;
  return <C className={className} />;
};

/**
 * Human-friendly countdown to the next auction. Returns null when the date
 * is missing or already past. Bilingual EN/TET.
 *   0 days  → "Today · Ohin"
 *   1 day   → "Tomorrow · Aban"
 *   N days  → "3 days left · Loron 3 nafatin"
 */
function auctionCountdown(dateStr, lang) {
  if (!dateStr) return null;
  const target = new Date(dateStr + "T00:00:00");
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((target - today) / (1000 * 60 * 60 * 24));
  if (days < 0) return null;
  if (lang === "tet") {
    if (days === 0) return "Ohin!";
    if (days === 1) return "Aban";
    return `Loron ${days} nafatin`;
  }
  if (days === 0) return "Today!";
  if (days === 1) return "Tomorrow";
  return `${days} days left`;
}

export default function AuctionPublic() {
  const { t, lang } = useLang();
  const T = (en, tet) => (lang === "tet" ? tet : en);

  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) || "");
  const [locked, setLocked] = useState(true);
  const [password, setPassword] = useState("");
  const [unlocking, setUnlocking] = useState(false);
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [nextAuction, setNextAuction] = useState({ item_count: 0, next_auction_date: "" });

  useEffect(() => {
    api.get("/public/auction-status").then((r) => setLocked(r.data.locked)).catch(() => {});
    api.get("/public/auction-catalogue/info").then((r) => setNextAuction(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    // Skip fetch when gate is up and we don't have a token
    if (locked && !token) {
      setRows([]);
      return;
    }
    setLoading(true);
    api
      .get(`/public/auction-items${token ? `?unlock_token=${encodeURIComponent(token)}` : ""}`)
      .then((r) => setRows(r.data))
      .catch((err) => {
        if (err.response?.status === 401) {
          sessionStorage.removeItem(TOKEN_KEY);
          setToken("");
        }
      })
      .finally(() => setLoading(false));
  }, [token, locked]);

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

  if (locked && !token) {
    return (
      <section className="min-h-[70vh] bg-white flex items-center justify-center px-6 py-16">
        <div
          className="w-full max-w-md rounded-2xl border border-stone-200 bg-white shadow-lg p-8 space-y-5"
          data-testid="auction-gate"
        >
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="w-14 h-14 rounded-full bg-[#B45309] text-white flex items-center justify-center shadow-md">
              <Lock className="w-6 h-6" />
            </div>
            <h1 className="font-display text-2xl font-bold text-[#1A2A52]">
              {T("Auction Listing Locked", "Listajen Leilão Xave-hela")}
            </h1>
            <p className="text-sm text-stone-600">
              {T(
                "Enter the visitor access password to view the public auction items currently up for bidding.",
                "Tama liafuan-xave hodi haree sasán hosi leilão públiku ne'ebé daudaun ami buka komprador.",
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
                data-testid="auction-password"
                autoFocus
                className="w-full pl-10 pr-3 py-3 rounded-lg border border-stone-300 focus:border-[#B45309] focus:ring-2 focus:ring-[#B45309]/20 outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={unlocking}
              data-testid="auction-unlock-btn"
              className="w-full py-3 rounded-lg bg-[#B45309] hover:bg-[#92400E] text-white font-semibold transition-colors disabled:opacity-50"
            >
              {unlocking ? T("Checking…", "Verifika hela…") : T("Unlock", "Loke")}
            </button>
          </form>
          <p className="text-xs text-stone-500 text-center pt-2">
            {T("Contact us on WhatsApp", "Kontaktu liu husi WhatsApp")}:{" "}
            <a className="text-[#1A2A52] font-semibold" href="https://wa.me/67078372678" target="_blank" rel="noreferrer">+670 78372678</a>
          </p>
          <div className="pt-4 border-t border-stone-200 text-center space-y-2">
            {nextAuction.next_auction_date && (
              <div
                data-testid="next-auction-banner-locked"
                className="inline-flex items-center gap-2 flex-wrap justify-center px-3 py-1.5 rounded-md bg-amber-50 border border-amber-200 text-amber-900 text-sm font-medium"
              >
                <span>🗓️ {T("Next Auction", "Leilaun tuir mai")}: <b>{nextAuction.next_auction_date}</b></span>
                {auctionCountdown(nextAuction.next_auction_date, lang) && (
                  <span
                    data-testid="next-auction-countdown-locked"
                    className="px-2 py-0.5 rounded-full bg-[#B45309] text-white text-xs font-semibold"
                  >
                    {auctionCountdown(nextAuction.next_auction_date, lang)}
                  </span>
                )}
              </div>
            )}
            <div>
              <a
                href={`${process.env.REACT_APP_BACKEND_URL}/api/public/auction-catalogue/pdf`}
                target="_blank"
                rel="noopener noreferrer"
                data-testid="public-catalogue-locked-btn"
                className="inline-flex items-center gap-2 text-sm text-[#1A2A52] hover:text-[#B45309] font-medium"
              >
                <FileDown className="w-4 h-4" />
                {T("Or download the printable catalogue (no password)", "Ka baixa katálogu impressu (la presiza liafuan-xave)")}
              </a>
            </div>
          </div>
        </div>
      </section>
    );
  }

  const filtered = filter === "all" ? rows : rows.filter((r) => r.item_type === filter);

  const lock = () => {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken("");
    setRows([]);
  };

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-16 space-y-10">
      <header className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow flex items-center gap-2">
            <Gavel className="w-3.5 h-3.5" /> {t("auctions")}
          </div>
          <h1 className="font-display text-4xl sm:text-5xl mt-1 text-[#1A2A52]">
            {T("Public Auction", "Leilão Públiku")}
          </h1>
          <div className="w-20 h-1 bg-[#F0B435] mt-3 rounded-full" />
          <p className="text-stone-600 mt-4 max-w-xl">
            {T(
              "Items currently listed for public auction. Contact us to bid or visit our Dili location.",
              "Sasán ne'ebé daudaun ami buka komprador. Kontaktu mai ami atu bid ka vizita lokál Dili.",
            )}
          </p>
          {nextAuction.next_auction_date && (
            <div
              data-testid="next-auction-banner"
              className="inline-flex items-center gap-2 flex-wrap mt-4 px-3 py-1.5 rounded-md bg-amber-50 border border-amber-200 text-amber-900 text-sm font-medium"
            >
              <span>🗓️ {T("Next Auction", "Leilaun tuir mai")}: <b>{nextAuction.next_auction_date}</b></span>
              {auctionCountdown(nextAuction.next_auction_date, lang) && (
                <span
                  data-testid="next-auction-countdown"
                  className="px-2 py-0.5 rounded-full bg-[#B45309] text-white text-xs font-semibold"
                >
                  {auctionCountdown(nextAuction.next_auction_date, lang)}
                </span>
              )}
            </div>
          )}
        </div>
        {locked && (
          <button
            onClick={lock}
            data-testid="auction-lock-again"
            className="text-xs text-stone-500 hover:text-[#1A2A52] flex items-center gap-1"
          >
            <Lock className="w-3.5 h-3.5" /> {T("Lock", "Xave")}
          </button>
        )}
        <a
          href={`${process.env.REACT_APP_BACKEND_URL}/api/public/auction-catalogue/pdf`}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="public-catalogue-btn"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-[#1A2A52] text-[#1A2A52] hover:bg-[#1A2A52] hover:text-white transition text-sm font-medium"
        >
          <FileDown className="w-4 h-4" />
          {T("Download Catalogue (PDF)", "Baixa Katálogu (PDF)")}
        </a>
      </header>

      <div className="flex gap-2 flex-wrap" data-testid="auction-filters">
        {[
          { k: "all", label: T("All", "Hotu"), color: "#1A2A52" },
          { k: "car", label: t("car"), Icon: Car, color: CATEGORY_META.car.color },
          { k: "motorcycle", label: t("motorcycle"), Icon: Bike, color: CATEGORY_META.motorcycle.color },
          { k: "electronic", label: t("electronic"), Icon: Cpu, color: CATEGORY_META.electronic.color },
          { k: "pezadu", label: t("pezadu"), Icon: Truck, color: CATEGORY_META.pezadu.color },
        ].map((f) => (
          <button
            key={f.k}
            onClick={() => setFilter(f.k)}
            data-testid={`auction-filter-${f.k}`}
            style={filter === f.k ? { backgroundColor: f.color, borderColor: f.color, color: "white" } : undefined}
            className={`px-4 py-2 rounded-full text-sm border transition ${
              filter === f.k
                ? "shadow"
                : "bg-white border-stone-200 text-stone-700 hover:border-stone-400"
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
        <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-6" data-testid="public-auction-grid">
          {filtered.map((r) => {
            const meta = CATEGORY_META[r.item_type] || CATEGORY_META.car;
            return (
              <article
                key={r.id}
                className="rounded-lg border border-stone-200 bg-white overflow-hidden hover:-translate-y-1 hover:shadow-md transition"
                data-testid={`public-auction-${r.id}`}
              >
                <div className="aspect-[4/3] bg-stone-100 relative">
                  {r.photo_url ? (
                    <img
                      alt={r.name || `${r.brand} ${r.model}`}
                      src={r.photo_url}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-stone-400">
                      <Icon kind={r.item_type} className="w-12 h-12" />
                    </div>
                  )}
                  <div
                    className={`absolute top-3 left-3 inline-flex items-center gap-1 px-2 py-1 rounded-full text-[10px] uppercase tracking-wider font-semibold ${meta.soft}`}
                    style={{ borderTop: `2px solid ${meta.color}` }}
                  >
                    <Icon kind={r.item_type} className="w-3 h-3" />
                    {r.item_type}
                  </div>
                </div>
                <div className="p-5">
                  <div className="font-display text-lg">{r.name || `${r.brand} ${r.model}`}</div>
                  {r.brand && r.name && (
                    <div className="text-xs text-stone-500 mt-0.5">{r.brand} {r.model}</div>
                  )}
                  {r.description && (
                    <p className="text-sm text-stone-600 mt-2 line-clamp-2">{r.description}</p>
                  )}
                  <div className="mt-4 flex items-end justify-between">
                    <div>
                      <div className="text-eyebrow">{t("starting_price")}</div>
                      <div className="font-display text-xl mt-1" style={{ color: meta.color }}>
                        ${Number(r.starting_price || 0).toLocaleString()}
                      </div>
                    </div>
                    <div className="text-xs text-stone-500 text-right">
                      {r.manufacture_year ? `Y. ${r.manufacture_year}` : r.category || ""}
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
