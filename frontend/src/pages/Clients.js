import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
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
import { Textarea } from "../components/ui/textarea";
import { Plus, Trash2, Pencil } from "lucide-react";
import { toast } from "sonner";

const blank = {
  full_name: "",
  id_type: "BI",
  id_number: "",
  phone: "",
  address: "",
  municipality: "",
  posto: "",
  suco: "",
  aldeia: "",
  notes: "",
};

export default function Clients() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [editingId, setEditingId] = useState(null);
  const [q, setQ] = useState("");

  const load = () =>
    api.get("/clients").then((r) => setRows(r.data));

  useEffect(() => {
    load();
  }, []);

  const onChange = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    try {
      if (editingId) {
        await api.put(`/clients/${editingId}`, form);
        toast.success("Client updated");
      } else {
        await api.post("/clients", form);
        toast.success("Client created");
      }
      setOpen(false);
      setForm(blank);
      setEditingId(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const edit = (row) => {
    setForm(row);
    setEditingId(row.id);
    setOpen(true);
  };

  const remove = async (id) => {
    if (!window.confirm("Delete client?")) return;
    try {
      await api.delete(`/clients/${id}`);
      load();
      toast.success("Deleted");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const filtered = rows.filter((r) =>
    [r.full_name, r.id_number, r.phone, r.municipality]
      .filter(Boolean)
      .some((x) => x.toLowerCase().includes(q.toLowerCase()))
  );

  return (
    <div className="space-y-6" data-testid="clients-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("clients")}</div>
          <h1 className="font-display text-4xl font-semibold mt-1">{t("clients")}</h1>
        </div>
        <div className="flex gap-3 items-center">
          <Input
            placeholder={t("search")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-64"
            data-testid="clients-search"
          />
          <Dialog
            open={open}
            onOpenChange={(o) => {
              setOpen(o);
              if (!o) {
                setForm(blank);
                setEditingId(null);
              }
            }}
          >
            <DialogTrigger asChild>
              <Button
                className="bg-[#2F4F4F] hover:bg-[#1D3333]"
                data-testid="client-new-btn"
              >
                <Plus className="w-4 h-4 mr-1" /> {t("new")}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>{editingId ? t("edit") : t("new")} — {t("clients")}</DialogTitle>
              </DialogHeader>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Field label={t("full_name")}>
                  <Input
                    value={form.full_name}
                    onChange={(e) => onChange("full_name", e.target.value)}
                    data-testid="client-full-name"
                  />
                </Field>
                <Field label={t("id_type")}>
                  <Select
                    value={form.id_type}
                    onValueChange={(v) => onChange("id_type", v)}
                  >
                    <SelectTrigger data-testid="client-id-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="BI">BI</SelectItem>
                      <SelectItem value="Electoral">Electoral</SelectItem>
                      <SelectItem value="Passport">Passport</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label={t("id_number")}>
                  <Input
                    value={form.id_number}
                    onChange={(e) => onChange("id_number", e.target.value)}
                    data-testid="client-id-number"
                  />
                </Field>
                <Field label={t("phone")}>
                  <Input
                    value={form.phone}
                    onChange={(e) => onChange("phone", e.target.value)}
                    data-testid="client-phone"
                  />
                </Field>
                <Field label={t("address")} full>
                  <Input
                    value={form.address}
                    onChange={(e) => onChange("address", e.target.value)}
                    data-testid="client-address"
                  />
                </Field>
                <Field label={t("municipality")}>
                  <Input
                    value={form.municipality}
                    onChange={(e) => onChange("municipality", e.target.value)}
                    data-testid="client-municipality"
                  />
                </Field>
                <Field label={t("posto")}>
                  <Input
                    value={form.posto}
                    onChange={(e) => onChange("posto", e.target.value)}
                    data-testid="client-posto"
                  />
                </Field>
                <Field label={t("suco")}>
                  <Input
                    value={form.suco}
                    onChange={(e) => onChange("suco", e.target.value)}
                    data-testid="client-suco"
                  />
                </Field>
                <Field label={t("aldeia")}>
                  <Input
                    value={form.aldeia}
                    onChange={(e) => onChange("aldeia", e.target.value)}
                    data-testid="client-aldeia"
                  />
                </Field>
                <Field label={t("notes")} full>
                  <Textarea
                    value={form.notes}
                    onChange={(e) => onChange("notes", e.target.value)}
                    data-testid="client-notes"
                  />
                </Field>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setOpen(false)}
                  data-testid="client-cancel"
                >
                  {t("cancel")}
                </Button>
                <Button
                  onClick={submit}
                  className="bg-[#2F4F4F] hover:bg-[#1D3333]"
                  data-testid="client-save"
                >
                  {t("save")}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="clients-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>{t("full_name")}</Th>
              <Th>{t("id_type")}</Th>
              <Th>{t("id_number")}</Th>
              <Th>{t("phone")}</Th>
              <Th>{t("municipality")}</Th>
              <Th>{t("posto")}</Th>
              <Th>{t("suco")}</Th>
              <Th>{t("aldeia")}</Th>
              <Th right>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.id} className="border-t border-stone-100">
                <Td className="font-medium">{r.full_name}</Td>
                <Td>{r.id_type}</Td>
                <Td>{r.id_number}</Td>
                <Td>{r.phone}</Td>
                <Td>{r.municipality}</Td>
                <Td>{r.posto}</Td>
                <Td>{r.suco}</Td>
                <Td>{r.aldeia}</Td>
                <Td right>
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => edit(r)}
                      data-testid={`client-edit-${r.id}`}
                      className="p-1 hover:text-[#2F4F4F]"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => remove(r.id)}
                      data-testid={`client-delete-${r.id}`}
                      className="p-1 hover:text-[#993333]"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </Td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan="9" className="p-8 text-center text-stone-500">
                  No clients
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Field({ label, full, children }) {
  return (
    <div className={full ? "md:col-span-2 space-y-1.5" : "space-y-1.5"}>
      <Label className="text-xs uppercase tracking-wider text-stone-500">{label}</Label>
      {children}
    </div>
  );
}

function Th({ children, right }) {
  return (
    <th
      className={`px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold ${
        right ? "text-right" : ""
      }`}
    >
      {children}
    </th>
  );
}

function Td({ children, right, className = "" }) {
  return (
    <td className={`px-4 py-3 ${right ? "text-right" : ""} ${className}`}>
      {children}
    </td>
  );
}
