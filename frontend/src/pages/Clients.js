import { useEffect, useState } from "react";
import { api, API_BASE } from "../lib/api";
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
import { Plus, Trash2, Pencil, Eye, FileText } from "lucide-react";
import { toast } from "sonner";
import FileUpload from "../components/FileUpload";

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
  photo_url: "",
  notes: "",
};

export default function Clients() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [editingId, setEditingId] = useState(null);
  const [q, setQ] = useState("");
  const [viewing, setViewing] = useState(null); // client object for detail
  const [viewContracts, setViewContracts] = useState([]);
  const [viewPayments, setViewPayments] = useState([]);

  const load = () => api.get("/clients").then((r) => setRows(r.data));
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
    setForm({ ...blank, ...row });
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

  const openDetail = async (row) => {
    setViewing(row);
    setViewContracts([]);
    setViewPayments([]);
    try {
      const [cs, ps] = await Promise.all([
        api.get(`/clients/${row.id}/contracts`),
        api.get(`/clients/${row.id}/payments`),
      ]);
      setViewContracts(cs.data);
      setViewPayments(ps.data);
    } catch (e) {
      toast.error("Failed to load history");
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
              <Button className="bg-[#1B2D5C] hover:bg-[#0F1B3A]" data-testid="client-new-btn">
                <Plus className="w-4 h-4 mr-1" /> {t("new")}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>{editingId ? t("edit") : t("new")} — {t("clients")}</DialogTitle>
              </DialogHeader>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Field label={t("full_name")}>
                  <Input value={form.full_name} onChange={(e) => onChange("full_name", e.target.value)} data-testid="client-full-name" />
                </Field>
                <Field label={t("id_type")}>
                  <Select value={form.id_type} onValueChange={(v) => onChange("id_type", v)}>
                    <SelectTrigger data-testid="client-id-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="BI">BI</SelectItem>
                      <SelectItem value="Electoral">Electoral</SelectItem>
                      <SelectItem value="Passport">Passport</SelectItem>
                      <SelectItem value="Drivers License">{t("drivers_license")}</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label={t("id_number")}>
                  <Input value={form.id_number} onChange={(e) => onChange("id_number", e.target.value)} data-testid="client-id-number" />
                </Field>
                <Field label={t("phone")}>
                  <Input value={form.phone} onChange={(e) => onChange("phone", e.target.value)} data-testid="client-phone" />
                </Field>
                <Field label={t("address")} full>
                  <Input value={form.address} onChange={(e) => onChange("address", e.target.value)} data-testid="client-address" />
                </Field>
                <Field label={t("municipality")}>
                  <Input value={form.municipality} onChange={(e) => onChange("municipality", e.target.value)} data-testid="client-municipality" />
                </Field>
                <Field label={t("posto")}>
                  <Input value={form.posto} onChange={(e) => onChange("posto", e.target.value)} data-testid="client-posto" />
                </Field>
                <Field label={t("suco")}>
                  <Input value={form.suco} onChange={(e) => onChange("suco", e.target.value)} data-testid="client-suco" />
                </Field>
                <Field label={t("aldeia")}>
                  <Input value={form.aldeia} onChange={(e) => onChange("aldeia", e.target.value)} data-testid="client-aldeia" />
                </Field>
                <Field label={t("photo")} full>
                  <FileUpload
                    value={form.photo_url}
                    onChange={(v) => onChange("photo_url", v)}
                    accept="image/*"
                    label={t("upload_photo")}
                    testid="client-photo"
                  />
                </Field>
                <Field label={t("notes")} full>
                  <Textarea value={form.notes} onChange={(e) => onChange("notes", e.target.value)} data-testid="client-notes" />
                </Field>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)} data-testid="client-cancel">
                  {t("cancel")}
                </Button>
                <Button onClick={submit} className="bg-[#1B2D5C] hover:bg-[#0F1B3A]" data-testid="client-save">
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
              <Th>{t("photo")}</Th>
              <Th>{t("full_name")}</Th>
              <Th>{t("id_type")}</Th>
              <Th>{t("id_number")}</Th>
              <Th>{t("phone")}</Th>
              <Th>{t("municipality")}</Th>
              <Th right>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.id} className="border-t border-stone-100">
                <Td>
                  {r.photo_url ? (
                    <img
                      alt=""
                      src={`${API_BASE}/files/${r.photo_url}`}
                      className="w-10 h-10 rounded-full object-cover border border-stone-200"
                    />
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-stone-100 border border-stone-200" />
                  )}
                </Td>
                <Td className="font-medium">{r.full_name}</Td>
                <Td>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200">
                    {r.id_type}
                  </span>
                </Td>
                <Td>{r.id_number}</Td>
                <Td>{r.phone}</Td>
                <Td>{r.municipality}</Td>
                <Td right>
                  <div className="flex justify-end gap-2">
                    <button onClick={() => openDetail(r)} data-testid={`client-view-${r.id}`} className="p-1 hover:text-[#1B2D5C]" title={t("view_details")}>
                      <Eye className="w-4 h-4" />
                    </button>
                    <button onClick={() => edit(r)} data-testid={`client-edit-${r.id}`} className="p-1 hover:text-[#1B2D5C]">
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => remove(r.id)} data-testid={`client-delete-${r.id}`} className="p-1 hover:text-[#993333]">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </Td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan="7" className="p-8 text-center text-stone-500">
                  No clients
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Detail dialog */}
      <Dialog open={!!viewing} onOpenChange={(o) => !o && setViewing(null)}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle data-testid="client-detail-title">
              {viewing?.full_name} · {t("view_details")}
            </DialogTitle>
          </DialogHeader>
          {viewing && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-[160px,1fr] gap-6">
                {viewing.photo_url ? (
                  <img
                    alt=""
                    src={`${API_BASE}/files/${viewing.photo_url}`}
                    className="w-40 h-40 rounded-md object-cover border border-stone-200"
                  />
                ) : (
                  <div className="w-40 h-40 rounded-md bg-stone-100 border border-stone-200 flex items-center justify-center text-stone-400">
                    {t("no_items")}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <Info label={t("id_type")} value={viewing.id_type} />
                  <Info label={t("id_number")} value={viewing.id_number} />
                  <Info label={t("phone")} value={viewing.phone} />
                  <Info label={t("address")} value={viewing.address} />
                  <Info label={t("municipality")} value={viewing.municipality} />
                  <Info label={t("posto")} value={viewing.posto} />
                  <Info label={t("suco")} value={viewing.suco} />
                  <Info label={t("aldeia")} value={viewing.aldeia} />
                </div>
              </div>

              <div>
                <div className="text-eyebrow mb-2">{t("contracts_owned")} ({viewContracts.length})</div>
                <div className="rounded-md border border-stone-200 overflow-x-auto" data-testid="client-contracts-table">
                  <table className="min-w-full text-sm">
                    <thead className="bg-stone-50 text-left">
                      <tr>
                        <Th>{t("contract_number")}</Th>
                        <Th>{t("item")}</Th>
                        <Th right>{t("loan_amount")}</Th>
                        <Th right>{t("remaining_balance")}</Th>
                        <Th>{t("due_date")}</Th>
                        <Th>{t("status")}</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {viewContracts.map((c) => (
                        <tr key={c.id} className="border-t border-stone-100">
                          <Td className="font-medium">{c.contract_number}</Td>
                          <Td>{c.item_type}</Td>
                          <Td right>${Number(c.loan_amount).toLocaleString()}</Td>
                          <Td right>${Number(c.remaining_balance || 0).toLocaleString()}</Td>
                          <Td>{c.due_date}</Td>
                          <Td>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200">
                              {c.status}
                            </span>
                          </Td>
                        </tr>
                      ))}
                      {viewContracts.length === 0 && (
                        <tr>
                          <td colSpan="6" className="p-4 text-center text-stone-500">
                            —
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <div className="text-eyebrow mb-2">{t("payment_history")} ({viewPayments.length})</div>
                <div className="rounded-md border border-stone-200 overflow-x-auto" data-testid="client-payments-table">
                  <table className="min-w-full text-sm">
                    <thead className="bg-stone-50 text-left">
                      <tr>
                        <Th>Receipt</Th>
                        <Th>{t("contract_number")}</Th>
                        <Th>{t("payment_type")}</Th>
                        <Th right>{t("amount")}</Th>
                        <Th>{t("date")}</Th>
                        <Th right>PDF</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {viewPayments.map((p) => (
                        <tr key={p.id} className="border-t border-stone-100">
                          <Td className="font-medium">{p.receipt_number}</Td>
                          <Td>{p.contract_number}</Td>
                          <Td>{p.type.replace("_", " ")}</Td>
                          <Td right>${Number(p.amount).toLocaleString()}</Td>
                          <Td>{p.date}</Td>
                          <Td right>
                            <a
                              href={`${API_BASE}/payments/${p.id}/pdf`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-[#1B2D5C] hover:underline"
                            >
                              <FileText className="w-3.5 h-3.5" /> PDF
                            </a>
                          </Td>
                        </tr>
                      ))}
                      {viewPayments.length === 0 && (
                        <tr>
                          <td colSpan="6" className="p-4 text-center text-stone-500">
                            —
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-stone-500">{label}</div>
      <div className="text-sm text-stone-900 mt-0.5">{value || "—"}</div>
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
    <th className={`px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold ${right ? "text-right" : ""}`}>
      {children}
    </th>
  );
}
function Td({ children, right, className = "" }) {
  return <td className={`px-4 py-3 ${right ? "text-right" : ""} ${className}`}>{children}</td>;
}
