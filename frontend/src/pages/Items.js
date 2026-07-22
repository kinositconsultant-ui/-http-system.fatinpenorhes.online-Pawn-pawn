import { useEffect, useState } from "react";
import { api, API_BASE } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Plus, Trash2, Pencil, Car, Bike, Cpu, Truck, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";
import FileUpload from "../components/FileUpload";

const PEZADU_CATEGORIES = ["forklift", "tractor", "loader", "heavy_duty_truck"];

const KIND_META = {
  car: { Icon: Car, fields: vehicleFields },
  motorcycle: { Icon: Bike, fields: vehicleFields },
  electronic: { Icon: Cpu, fields: electronicFields },
  pezadu: { Icon: Truck, fields: pezaduFields },
};

function vehicleFields(t) {
  return [
    { k: "name", label: t("item_name"), required: true, placeholder: "Toyota Hilux 2020 Black" },
    { k: "brand", label: t("brand"), required: true },
    { k: "model", label: t("model"), required: true },
    { k: "manufacture_year", label: t("manufacture_year"), type: "number", tableHide: true },
    { k: "engine_cc", label: t("engine_cc") || "Engine Capacity (CC)", type: "number", tableHide: true, placeholder: "1500" },
    {
      k: "transmission",
      label: t("transmission") || "Transmission",
      select: true,
      tableHide: true,
      options: [
        { value: "manual", label: t("manual") || "Manual" },
        { value: "automatic", label: t("automatic") || "Automatic" },
      ],
    },
    { k: "market_value", label: t("market_value"), type: "number", placeholder: "USD" },
    { k: "color", label: t("color"), tableHide: true },
    { k: "plate", label: t("plate") },
    { k: "machine_number", label: t("machine_number") },
    { k: "chassis", label: t("chassis"), tableHide: true },
    { k: "fuel_percent", label: t("fuel_percent"), type: "number", tableHide: true },
    { k: "location", label: t("location"), placeholder: "Warehouse A / Shop / Off-site" },
    { k: "photo_url", label: t("upload_photo"), full: true, upload: true, accept: "image/*" },
    { k: "document_url", label: t("upload_document"), full: true, upload: true, accept: ".pdf,image/*" },
    { k: "description", label: t("description"), full: true, textarea: true },
  ];
}

function electronicFields(t) {
  return [
    { k: "category", label: t("category"), required: true, placeholder: "Phone / Laptop / TV" },
    { k: "brand", label: t("brand"), required: true },
    { k: "model", label: t("model"), required: true },
    { k: "serial", label: t("serial") },
    { k: "manufacture_year", label: t("manufacture_year"), type: "number" },
    { k: "market_value", label: t("market_value"), type: "number", placeholder: "USD" },
    { k: "condition", label: t("condition"), placeholder: "Good / Fair" },
    { k: "location", label: t("location"), placeholder: "Warehouse A / Shop / Off-site" },
    { k: "photo_url", label: t("upload_photo"), full: true, upload: true, accept: "image/*" },
    { k: "document_url", label: t("upload_document"), full: true, upload: true, accept: ".pdf,image/*" },
    { k: "description", label: t("description"), full: true, textarea: true },
  ];
}

function pezaduFields(t) {
  return [
    { k: "name", label: t("item_name"), required: true, placeholder: "Komatsu Forklift FD25T" },
    {
      k: "category",
      label: t("category"),
      required: true,
      select: true,
      options: PEZADU_CATEGORIES.map((c) => ({ value: c, label: t(c) })),
    },
    { k: "brand", label: t("brand"), required: true },
    { k: "model", label: t("model"), required: true },
    { k: "manufacture_year", label: t("manufacture_year"), type: "number", tableHide: true },
    { k: "market_value", label: t("market_value"), type: "number", placeholder: "USD" },
    { k: "color", label: t("color"), tableHide: true },
    { k: "plate", label: t("plate"), tableHide: true },
    { k: "machine_number", label: t("machine_number") },
    { k: "chassis", label: t("chassis"), tableHide: true },
    { k: "serial", label: t("serial"), tableHide: true },
    { k: "operating_hours", label: t("operating_hours"), type: "number", tableHide: true },
    { k: "fuel_percent", label: t("fuel_percent"), type: "number", tableHide: true },
    { k: "location", label: t("location"), placeholder: "Warehouse A / Shop / Off-site" },
    { k: "photo_url", label: t("upload_photo"), full: true, upload: true, accept: "image/*" },
    { k: "document_url", label: t("upload_document"), full: true, upload: true, accept: ".pdf,image/*" },
    { k: "description", label: t("description"), full: true, textarea: true },
  ];
}

// Resolve a value that may be an absolute URL, an /api/... path, or a bare
// storage key, into a browser-loadable URL. Same convention as Clients.js.
function resolveFileUrl(val) {
  if (!val) return null;
  if (val.startsWith("http")) return val;
  if (val.startsWith("/api/")) return `${API_BASE.replace(/\/api$/, "")}${val}`;
  return `${API_BASE}/files/${val}`;
}

// Prefer thumbnail_url (200x200) for list rendering, fall back to photo_url.
function itemThumbSrc(r, { preferOriginal = false } = {}) {
  if (!r) return null;
  if (!preferOriginal && r.thumbnail_url) return resolveFileUrl(r.thumbnail_url);
  if (r.photo_url) return resolveFileUrl(r.photo_url);
  return null;
}

function emptyFor(kind) {
  if (kind === "electronic") {
    return {
      category: "",
      brand: "",
      model: "",
      description: "",
      serial: "",
      condition: "",
      manufacture_year: "",
      market_value: 0,
      location: "",
      photo_url: "",
      thumbnail_url: "",
      document_url: "",
    };
  }
  if (kind === "pezadu") {
    return {
      category: "",
      brand: "",
      model: "",
      description: "",
      plate: "",
      chassis: "",
      serial: "",
      fuel_percent: 0,
      color: "",
      operating_hours: "",
      manufacture_year: "",
      market_value: 0,
      location: "",
      photo_url: "",
      thumbnail_url: "",
      document_url: "",
    };
  }
  return {
    brand: "",
    model: "",
    description: "",
    plate: "",
    chassis: "",
    fuel_percent: 0,
    color: "",
    manufacture_year: "",
    engine_cc: "",
    transmission: "",
    market_value: 0,
    location: "",
    photo_url: "",
    thumbnail_url: "",
    document_url: "",
  };
}

export default function Items() {
  const { t } = useLang();
  const [kind, setKind] = useState("car");

  return (
    <div className="space-y-6" data-testid="items-root">
      <header>
        <div className="text-eyebrow">{t("items")}</div>
        <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">{t("items")}</h1>
        <p className="text-stone-600 text-sm mt-1">
          Separate tables for {t("car")} · {t("motorcycle")} · {t("electronic")}.
        </p>
      </header>

      <Tabs value={kind} onValueChange={setKind}>
        <TabsList
          className="bg-stone-100 border border-stone-200 p-1 rounded-lg gap-1 h-auto"
          data-testid="items-tabs"
        >
          <TabsTrigger
            value="car"
            data-testid="items-tab-car"
            className="data-[state=active]:bg-[#1B2D5C] data-[state=active]:text-white data-[state=active]:shadow-md text-stone-600 hover:text-[#1B2D5C] px-4 py-2 rounded-md font-medium transition-colors"
          >
            <Car className="w-4 h-4 mr-2" />
            {t("car")}
          </TabsTrigger>
          <TabsTrigger
            value="motorcycle"
            data-testid="items-tab-motorcycle"
            className="data-[state=active]:bg-[#C17767] data-[state=active]:text-white data-[state=active]:shadow-md text-stone-600 hover:text-[#C17767] px-4 py-2 rounded-md font-medium transition-colors"
          >
            <Bike className="w-4 h-4 mr-2" />
            {t("motorcycle")}
          </TabsTrigger>
          <TabsTrigger
            value="electronic"
            data-testid="items-tab-electronic"
            className="data-[state=active]:bg-[#4C7F62] data-[state=active]:text-white data-[state=active]:shadow-md text-stone-600 hover:text-[#4C7F62] px-4 py-2 rounded-md font-medium transition-colors"
          >
            <Cpu className="w-4 h-4 mr-2" />
            {t("electronic")}
          </TabsTrigger>
          <TabsTrigger
            value="pezadu"
            data-testid="items-tab-pezadu"
            className="data-[state=active]:bg-[#B8860B] data-[state=active]:text-white data-[state=active]:shadow-md text-stone-600 hover:text-[#B8860B] px-4 py-2 rounded-md font-medium transition-colors"
          >
            <Truck className="w-4 h-4 mr-2" />
            {t("pezadu")}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="car">
          <ItemTable kind="car" />
        </TabsContent>
        <TabsContent value="motorcycle">
          <ItemTable kind="motorcycle" />
        </TabsContent>
        <TabsContent value="electronic">
          <ItemTable kind="electronic" />
        </TabsContent>
        <TabsContent value="pezadu">
          <ItemTable kind="pezadu" />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// Per-kind accent: subtle banner above the table and color hint for the kind badge
const KIND_THEME = {
  car: { bar: "bg-[#1B2D5C]", soft: "bg-[#1B2D5C]/5", border: "border-[#1B2D5C]/20", text: "text-[#1B2D5C]", label: "Car" },
  motorcycle: { bar: "bg-[#C17767]", soft: "bg-[#C17767]/5", border: "border-[#C17767]/20", text: "text-[#C17767]", label: "Motorcycle" },
  electronic: { bar: "bg-[#4C7F62]", soft: "bg-[#4C7F62]/5", border: "border-[#4C7F62]/20", text: "text-[#4C7F62]", label: "Electronic" },
  pezadu: { bar: "bg-[#B8860B]", soft: "bg-[#B8860B]/5", border: "border-[#B8860B]/20", text: "text-[#B8860B]", label: "Pezadu" },
};

function ItemTable({ kind }) {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyFor(kind));
  const meta = KIND_META[kind];
  const fields = meta.fields(t);
  const KindIcon = meta.Icon;
  const theme = KIND_THEME[kind];

  const load = () => api.get(`/items/${kind}`).then((r) => setRows(r.data));

  useEffect(() => {
    load();
    setForm(emptyFor(kind));
    setEditingId(null);
  }, [kind]);

  const onChange = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    const payload = { ...form };
    if ("fuel_percent" in payload && payload.fuel_percent !== "")
      payload.fuel_percent = Number(payload.fuel_percent);
    if ("manufacture_year" in payload)
      payload.manufacture_year = payload.manufacture_year ? Number(payload.manufacture_year) : null;
    if ("engine_cc" in payload)
      payload.engine_cc = payload.engine_cc ? Number(payload.engine_cc) : null;
    if ("market_value" in payload && payload.market_value !== "")
      payload.market_value = Number(payload.market_value);
    try {
      if (editingId) {
        await api.put(`/items/${kind}/${editingId}`, payload);
        toast.success("Updated");
      } else {
        await api.post(`/items/${kind}`, payload);
        toast.success("Created");
      }
      setOpen(false);
      setEditingId(null);
      setForm(emptyFor(kind));
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const edit = (row) => {
    setForm({ ...emptyFor(kind), ...row });
    setEditingId(row.id);
    setOpen(true);
  };

  const remove = async (id) => {
    if (!window.confirm("Delete item?")) return;
    try {
      await api.delete(`/items/${kind}/${id}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="space-y-4 mt-4">
      {/* Kind banner + new button */}
      <div className={`rounded-lg border ${theme.border} ${theme.soft} flex items-center justify-between px-5 py-4`}>
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-md ${theme.bar} text-white flex items-center justify-center shadow-sm`}>
            <KindIcon className="w-5 h-5" />
          </div>
          <div>
            <div className={`text-xs uppercase tracking-wider font-semibold ${theme.text}`}>{theme.label}</div>
            <div className="text-sm text-stone-600">
              <span className="font-semibold text-stone-900">{rows.length}</span> {t("items").toLowerCase()} ·{" "}
              <span className="text-stone-500">in stock {rows.filter((r) => !r.status || r.status === "in_stock").length}</span>
            </div>
          </div>
        </div>
        <Dialog
          open={open}
          onOpenChange={(o) => {
            setOpen(o);
            if (!o) {
              setEditingId(null);
              setForm(emptyFor(kind));
            }
          }}
        >
          <DialogTrigger asChild>
            <Button
              className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
              data-testid={`item-new-${kind}`}
            >
              <Plus className="w-4 h-4 mr-1" /> {t("new")} {t(kind)}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>
                {editingId ? t("edit") : t("new")} — {t(kind)}
              </DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {fields.map((f) => (
                <div
                  key={f.k}
                  className={f.full ? "md:col-span-2 space-y-1.5" : "space-y-1.5"}
                >
                  <Label className="text-xs uppercase tracking-wider text-stone-500">
                    {f.label}
                    {f.required ? " *" : ""}
                  </Label>
                  {f.upload ? (
                    <FileUpload
                      value={form[f.k] ?? ""}
                      onChange={(v) => {
                        onChange(f.k, v);
                        if (f.k === "photo_url" && !v) onChange("thumbnail_url", "");
                      }}
                      onThumbnail={
                        f.k === "photo_url"
                          ? (v) => onChange("thumbnail_url", v)
                          : undefined
                      }
                      accept={f.accept}
                      label={f.label}
                      testid={`item-${kind}-${f.k}`}
                    />
                  ) : f.textarea ? (
                    <Textarea
                      value={form[f.k] ?? ""}
                      onChange={(e) => onChange(f.k, e.target.value)}
                      data-testid={`item-${kind}-${f.k}`}
                    />
                  ) : f.select ? (
                    <Select
                      value={form[f.k] || ""}
                      onValueChange={(v) => onChange(f.k, v)}
                    >
                      <SelectTrigger data-testid={`item-${kind}-${f.k}`}>
                        <SelectValue placeholder={t("select") || "Select"} />
                      </SelectTrigger>
                      <SelectContent>
                        {f.options.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      type={f.type || "text"}
                      placeholder={f.placeholder}
                      value={form[f.k] ?? ""}
                      onChange={(e) => onChange(f.k, e.target.value)}
                      data-testid={`item-${kind}-${f.k}`}
                    />
                  )}
                </div>
              ))}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                {t("cancel")}
              </Button>
              <Button
                onClick={submit}
                className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
                data-testid={`item-${kind}-save`}
              >
                {t("save")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto shadow-sm">
        <table className="min-w-full text-[13px]" data-testid={`items-table-${kind}`}>
          <thead className={`${theme.soft} text-left border-b ${theme.border}`}>
            <tr>
              <th className="px-2 py-2.5 text-[10px] uppercase tracking-wider text-stone-600 font-semibold whitespace-nowrap w-12">
                {t("photo") || "Photo"}
              </th>
              {fields
                .filter((f) => !f.full && !f.tableHide)
                .map((f) => (
                  <th
                    key={f.k}
                    className="px-2 py-2.5 text-[10px] uppercase tracking-wider text-stone-600 font-semibold whitespace-nowrap"
                  >
                    {f.label}
                  </th>
                ))}
              <th className="px-2 py-2.5 text-[10px] uppercase tracking-wider text-stone-600 font-semibold whitespace-nowrap">
                {t("status")}
              </th>
              <th className="px-2 py-2.5 text-[10px] uppercase tracking-wider text-stone-600 font-semibold text-right whitespace-nowrap">
                {t("actions")}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100 hover:bg-stone-50/60">
                <td className="px-2 py-1.5 w-12">
                  {(() => {
                    const thumbSrc = itemThumbSrc(r);
                    const fullSrc = itemThumbSrc(r, { preferOriginal: true });
                    return thumbSrc ? (
                      <a
                        href={fullSrc || thumbSrc}
                        target="_blank"
                        rel="noreferrer"
                        data-testid={`item-${kind}-thumb-${r.id}`}
                        className="block w-10 h-10 rounded-md overflow-hidden border border-stone-200 hover:ring-2 hover:ring-[#1B2D5C]/30 transition"
                        title="Open full image"
                      >
                        <img
                          src={thumbSrc}
                          alt={r.name || r.brand || "item"}
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => {
                            e.currentTarget.style.display = "none";
                          }}
                        />
                      </a>
                    ) : (
                      <div className={`w-10 h-10 rounded-md border border-dashed border-stone-300 ${theme.soft} flex items-center justify-center`}>
                        <ImageIcon className="w-4 h-4 text-stone-400" />
                      </div>
                    );
                  })()}
                </td>
                {fields
                  .filter((f) => !f.full && !f.tableHide)
                  .map((f) => (
                    <td key={f.k} className="px-2 py-2 whitespace-nowrap text-stone-800 max-w-[180px] truncate">
                      {f.k === "market_value" && r[f.k] != null
                        ? `$${Number(r[f.k]).toLocaleString()}`
                        : f.select && r[f.k]
                        ? f.options.find((o) => o.value === r[f.k])?.label || r[f.k]
                        : r[f.k] ?? "—"}
                    </td>
                  ))}
                <td className="px-2 py-2 whitespace-nowrap">
                  <span
                    className={`text-[11px] px-1.5 py-0.5 rounded-full border ${
                      r.status === "in_stock"
                        ? "bg-stone-100 text-stone-700 border-stone-200"
                        : r.status === "pawned"
                        ? "bg-amber-50 text-amber-800 border-amber-200"
                        : r.status === "redeemed"
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                        : r.status === "auction"
                        ? "bg-orange-50 text-orange-800 border-orange-200"
                        : r.status === "sold"
                        ? "bg-blue-50 text-blue-800 border-blue-200"
                        : "bg-stone-100 text-stone-700 border-stone-200"
                    }`}
                  >
                    {r.status || "in_stock"}
                  </span>
                </td>
                <td className="px-2 py-2 text-right">
                  <div className="flex justify-end gap-1">
                    <button
                      onClick={() => edit(r)}
                      data-testid={`item-${kind}-edit-${r.id}`}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#C17767] text-white hover:bg-[#A96253] transition-colors"
                      title={t("edit")}
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => remove(r.id)}
                      data-testid={`item-${kind}-delete-${r.id}`}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#993333] text-white hover:bg-[#7A2828] transition-colors"
                      title={t("delete")}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td
                  colSpan={fields.filter((f) => !f.full && !f.tableHide).length + 3}
                  className="p-10 text-center text-stone-500"
                >
                  <KindIcon className="w-8 h-8 mx-auto mb-2 text-stone-300" />
                  No {theme.label.toLowerCase()} items yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
