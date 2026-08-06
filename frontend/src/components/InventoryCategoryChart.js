import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../lib/api";
import { Card } from "./ui/card";
import { Car, Bike, Cpu, Truck } from "lucide-react";

// Palette matches the tab accents on the Items page.
const KIND_META = {
  car: { color: "#1B2D5C", Icon: Car, label: "Cars · Kareta" },
  motorcycle: { color: "#C17767", Icon: Bike, label: "Motorcycles · Motor" },
  electronic: { color: "#4C7F62", Icon: Cpu, label: "Electronics" },
  pezadu: { color: "#B8860B", Icon: Truck, label: "Heavy Equipment" },
};

const fmt = (n) => new Intl.NumberFormat("en-US").format(Number(n || 0));
const fmtUsd = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(n || 0));

export default function InventoryCategoryChart() {
  const [data, setData] = useState(null);
  const [hovered, setHovered] = useState(null); // { kind } while hovering a slice

  useEffect(() => {
    let cancelled = false;
    api
      .get("/inventory/category-breakdown")
      .then((r) => {
        if (!cancelled) setData(r.data);
      })
      .catch(() => {
        if (!cancelled) setData({ by_kind: [], total_count: 0, total_market_value: 0 });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!data) {
    return (
      <Card className="p-4 border border-stone-200 rounded-lg" data-testid="inv-chart-loading">
        <div className="text-sm text-stone-500">Loading category chart…</div>
      </Card>
    );
  }

  const pieData = (data.by_kind || [])
    .filter((k) => (k.count || 0) > 0)
    .map((k) => ({
      name: KIND_META[k.kind]?.label || k.kind,
      kind: k.kind,
      value: k.count,
      market_value: k.market_value,
      subcategories: k.subcategories || [],
    }));

  const focus = hovered
    ? pieData.find((p) => p.kind === hovered)
    : null;

  return (
    <Card
      className="p-4 md:p-5 border border-stone-200 rounded-lg bg-white"
      data-testid="inventory-category-chart"
    >
      <div className="flex items-baseline justify-between mb-3 flex-wrap gap-2">
        <div>
          <div className="text-eyebrow">Inventory Mix</div>
          <div className="text-sm text-stone-600">
            {fmt(data.total_count)} items · {fmtUsd(data.total_market_value)} total market value
          </div>
        </div>
        <div className="text-[11px] text-stone-500">Hover a slice for subcategory detail</div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
        {/* Donut */}
        <div className="h-56" data-testid="inv-chart-donut">
          {pieData.length === 0 ? (
            <div className="h-full flex items-center justify-center text-sm text-stone-400">
              No items yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={2}
                  onMouseEnter={(_, idx) => setHovered(pieData[idx].kind)}
                  onMouseLeave={() => setHovered(null)}
                >
                  {pieData.map((p) => (
                    <Cell key={p.kind} fill={KIND_META[p.kind]?.color || "#999"} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value, _n, ctx) => [
                    `${fmt(value)} items · ${fmtUsd(ctx.payload.market_value)}`,
                    ctx.payload.name,
                  ]}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Legend + focused detail */}
        <div className="space-y-2" data-testid="inv-chart-legend">
          {pieData.map((p) => {
            const meta = KIND_META[p.kind];
            const Icon = meta?.Icon;
            const isFocused = focus?.kind === p.kind;
            return (
              <div
                key={p.kind}
                onMouseEnter={() => setHovered(p.kind)}
                onMouseLeave={() => setHovered(null)}
                className={`rounded-md border p-2 transition-colors cursor-default ${
                  isFocused ? "border-stone-400 bg-stone-50" : "border-stone-200"
                }`}
                data-testid={`inv-chart-row-${p.kind}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="w-3 h-3 rounded-sm shrink-0"
                      style={{ background: meta?.color }}
                    />
                    {Icon && <Icon className="w-4 h-4" style={{ color: meta?.color }} />}
                    <span className="text-sm font-medium truncate">{p.name}</span>
                  </div>
                  <div className="text-sm tabular-nums shrink-0">
                    <span className="font-semibold">{fmt(p.value)}</span>
                    <span className="text-stone-400"> · {fmtUsd(p.market_value)}</span>
                  </div>
                </div>
                {isFocused && p.subcategories.length > 0 && (
                  <div className="mt-2 pl-5 space-y-1" data-testid={`inv-chart-sub-${p.kind}`}>
                    {p.subcategories.slice(0, 6).map((s) => (
                      <div
                        key={s.name}
                        className="flex justify-between text-[11px] text-stone-600"
                      >
                        <span className="capitalize">{s.name.replace(/_/g, " ")}</span>
                        <span className="tabular-nums">
                          {fmt(s.count)} · {fmtUsd(s.market_value)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
