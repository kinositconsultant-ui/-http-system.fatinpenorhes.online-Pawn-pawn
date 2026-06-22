import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useLang } from "../../context/LangContext";
import { Car, Bike, Cpu } from "lucide-react";

export default function Warehouse() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    api.get("/public/warehouse").then((r) => setRows(r.data));
  }, []);

  const filtered = filter === "all" ? rows : rows.filter((r) => r.kind === filter);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-16 space-y-10">
      <header>
        <div className="text-eyebrow">{t("warehouse")}</div>
        <h1 className="font-display text-4xl sm:text-5xl mt-1">{t("warehouse")}</h1>
        <p className="text-stone-600 mt-3 max-w-xl">
          A look at what's currently inside our Dili warehouse. Most items remain available for redemption by their owners.
        </p>
      </header>

      <div className="flex gap-2" data-testid="warehouse-filters">
        {[
          { k: "all", label: "All" },
          { k: "car", label: t("car"), Icon: Car },
          { k: "motorcycle", label: t("motorcycle"), Icon: Bike },
          { k: "electronic", label: t("electronic"), Icon: Cpu },
        ].map((f) => (
          <button
            key={f.k}
            onClick={() => setFilter(f.k)}
            data-testid={`warehouse-filter-${f.k}`}
            className={`px-4 py-2 rounded-full text-sm border transition ${
              filter === f.k
                ? "bg-[#2F4F4F] border-[#2F4F4F] text-white"
                : "bg-white border-stone-200 text-stone-700 hover:border-[#2F4F4F]"
            }`}
          >
            {f.Icon ? <f.Icon className="inline w-3.5 h-3.5 mr-1 -mt-0.5" /> : null}
            {f.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="p-10 rounded-lg border border-dashed border-stone-300 text-center text-stone-500">
          {t("no_items")}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {filtered.map((r) => (
            <article
              key={r.id}
              className="rounded-lg border border-stone-200 bg-white overflow-hidden"
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
