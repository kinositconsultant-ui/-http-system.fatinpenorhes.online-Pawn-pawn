import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useLang } from "../../context/LangContext";
import { Car, Bike, Cpu } from "lucide-react";

const Icon = ({ kind, className }) =>
  kind === "car" ? (
    <Car className={className} />
  ) : kind === "motorcycle" ? (
    <Bike className={className} />
  ) : (
    <Cpu className={className} />
  );

export default function AuctionPublic() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api.get("/public/auction-items").then((r) => setRows(r.data));
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-16 space-y-10">
      <header>
        <div className="text-eyebrow">{t("auctions")}</div>
        <h1 className="font-display text-4xl sm:text-5xl mt-1">{t("auction_items")}</h1>
        <p className="text-stone-600 mt-3 max-w-xl">
          Items currently listed for public auction. Contact us to bid or visit our Dili warehouse.
        </p>
      </header>

      {rows.length === 0 ? (
        <div className="p-10 rounded-lg border border-dashed border-stone-300 text-center text-stone-500">
          {t("no_items")}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="public-auction-grid">
          {rows.map((r) => (
            <article
              key={r.id}
              className="rounded-lg border border-stone-200 bg-white overflow-hidden hover:-translate-y-1 transition"
              data-testid={`public-auction-${r.id}`}
            >
              <div className="aspect-[4/3] bg-stone-100 relative">
                {r.photo_url ? (
                  <img
                    alt=""
                    src={r.photo_url}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-stone-400">
                    <Icon kind={r.item_type} className="w-12 h-12" />
                  </div>
                )}
                <div className="absolute top-3 left-3 inline-flex items-center gap-1 px-2 py-1 rounded-full bg-white/90 text-xs uppercase tracking-wider text-stone-700">
                  <Icon kind={r.item_type} className="w-3.5 h-3.5" />
                  {r.item_type}
                </div>
              </div>
              <div className="p-5">
                <div className="font-display text-lg">
                  {r.brand} {r.model}
                </div>
                {r.description && (
                  <p className="text-sm text-stone-600 mt-1 line-clamp-2">{r.description}</p>
                )}
                <div className="mt-4 flex items-end justify-between">
                  <div>
                    <div className="text-eyebrow">{t("starting_price")}</div>
                    <div className="font-display text-xl text-[#2F4F4F] mt-1">
                      ${Number(r.starting_price || 0).toLocaleString()}
                    </div>
                  </div>
                  <div className="text-xs text-stone-500">
                    {r.manufacture_year ? `Y. ${r.manufacture_year}` : r.category || ""}
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
