import { useEffect, useState } from "react";
import { api } from "../lib/api";
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
import { Plus, Trash2, Pencil, Car, Bike, Cpu } from "lucide-react";
import { toast } from "sonner";

const KIND_META = {
  car: { Icon: Car, fields: vehicleFields },
  motorcycle: { Icon: Bike, fields: vehicleFields },
  electronic: { Icon: Cpu, fields: electronicFields },
};

function vehicleFields(t) {
  return [
    { k: "brand", label: t("brand"), required: true },
    { k: "model", label: t("model"), required: true },
    { k: "year", label: t("year"), type: "number" },
    { k: "color", label: t("color") },
    { k: "plate", label: t("plate") },
    { k: "chassis", label: t("chassis") },
    { k: "fuel_percent", label: t("fuel_percent"), type: "number" },
    { k: "photo_url", label: t("photo_url"), full: true },
    { k: "document_url", label: t("document_url"), full: true },
    { k: "description", label: t("description"), full: true, textarea: true },
  ];
}

function electronicFields(t) {
  return [
    { k: "category", label: t("category"), required: true, placeholder: "Phone / Laptop / TV" },
    { k: "brand", label: t("brand"), required: true },
    { k: "model", label: t("model"), required: true },
    { k: "serial", label: t("serial") },
    { k: "condition", label: t("condition"), placeholder: "Good / Fair" },
    { k: "photo_url", label: t("photo_url"), full: true },
    { k: "document_url", label: t("document_url"), full: true },
    { k: "description", label: t("description"), full: true, textarea: true },
  ];
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
      photo_url: "",
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
    year: "",
    photo_url: "",
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
        <h1 className="font-display text-4xl font-semibold mt-1">{t("items")}</h1>
        <p className="text-stone-600 text-sm mt-1">
          Separate tables for {t("car")} · {t("motorcycle")} · {t("electronic")}.
        </p>
      </header>

      <Tabs value={kind} onValueChange={setKind}>
        <TabsList data-testid="items-tabs">
          <TabsTrigger value="car" data-testid="items-tab-car">
            <Car className="w-4 h-4 mr-2" />
            {t("car")}
          </TabsTrigger>
          <TabsTrigger value="motorcycle" data-testid="items-tab-motorcycle">
            <Bike className="w-4 h-4 mr-2" />
            {t("motorcycle")}
          </TabsTrigger>
          <TabsTrigger value="electronic" data-testid="items-tab-electronic">
            <Cpu className="w-4 h-4 mr-2" />
            {t("electronic")}
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
      </Tabs>
    </div>
  );
}

function ItemTable({ kind }) {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyFor(kind));
  const meta = KIND_META[kind];
  const fields = meta.fields(t);

  const load = () => api.get(`/items/${kind}`).then((r) => setRows(r.data));

  useEffect(() => {
    load();
    setForm(emptyFor(kind));
    setEditingId(null);
  }, [kind]);

  const onChange = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    const payload = { ...form };
    // coerce numbers
    if ("fuel_percent" in payload && payload.fuel_percent !== "")
      payload.fuel_percent = Number(payload.fuel_percent);
    if ("year" in payload && payload.year !== "")
      payload.year = payload.year ? Number(payload.year) : null;
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
      <div className="flex justify-end">
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
              className="bg-[#2F4F4F] hover:bg-[#1D3333]"
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
                  {f.textarea ? (
                    <Textarea
                      value={form[f.k] ?? ""}
                      onChange={(e) => onChange(f.k, e.target.value)}
                      data-testid={`item-${kind}-${f.k}`}
                    />
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
                className="bg-[#2F4F4F] hover:bg-[#1D3333]"
                data-testid={`item-${kind}-save`}
              >
                {t("save")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid={`items-table-${kind}`}>
          <thead className="bg-stone-50 text-left">
            <tr>
              {fields
                .filter((f) => !f.full)
                .map((f) => (
                  <th
                    key={f.k}
                    className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold"
                  >
                    {f.label}
                  </th>
                ))}
              <th className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold">
                {t("status")}
              </th>
              <th className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold text-right">
                {t("actions")}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100">
                {fields
                  .filter((f) => !f.full)
                  .map((f) => (
                    <td key={f.k} className="px-4 py-3">
                      {r[f.k] ?? "—"}
                    </td>
                  ))}
                <td className="px-4 py-3">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full border ${
                      r.status === "in_stock"
                        ? "bg-stone-100 text-stone-700 border-stone-200"
                        : r.status === "pawned"
                        ? "bg-amber-50 text-amber-800 border-amber-200"
                        : r.status === "redeemed"
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                        : r.status === "auction"
                        ? "bg-orange-50 text-orange-800 border-orange-200"
                        : "bg-stone-100 text-stone-700 border-stone-200"
                    }`}
                  >
                    {r.status || "in_stock"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => edit(r)}
                      data-testid={`item-${kind}-edit-${r.id}`}
                      className="p-1 hover:text-[#2F4F4F]"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => remove(r.id)}
                      data-testid={`item-${kind}-delete-${r.id}`}
                      className="p-1 hover:text-[#993333]"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td
                  colSpan={fields.filter((f) => !f.full).length + 2}
                  className="p-8 text-center text-stone-500"
                >
                  No items
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
