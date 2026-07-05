import { useEffect, useState } from "react";
import { api, API_BASE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
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
import { Plus, Trash2, Pencil, Eye, FileText, IdCard, RefreshCw, Ban, Download, Copy } from "lucide-react";
import { toast } from "sonner";
import FileUpload from "../components/FileUpload";
import { shortContract, shortReceipt } from "../lib/docNumbers";

/**
 * Return a photo URL that the browser can actually GET without cookies.
 *
 * We PREFER the public per-member endpoint because `/api/files/*` requires
 * auth and browsers strip httpOnly cookies from <img src> in some cross-site
 * scenarios (e.g. deployed prod). When the client hasn't been issued a
 * Member Card yet, `member_verify_token` is absent — return null so the
 * caller renders the placeholder avatar.
 */
function clientPhotoSrc(client) {
  if (!client) return null;
  if (client.member_verify_token) {
    return `${API_BASE}/public/verify/${client.member_verify_token}/photo`;
  }
  return null;
}

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
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
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

  // --- Member ID Card actions --------------------------------------
  const refreshViewingFromServer = async (cid) => {
    try {
      const r = await api.get(`/clients/${cid}`);
      setViewing(r.data);
      // Also refresh underlying list so badge stays in sync
      load();
    } catch (_) { /* noop */ }
  };

  const issueCard = async () => {
    if (!viewing) return;
    try {
      await api.post(`/clients/${viewing.id}/issue-card`);
      toast.success("Member card issued");
      await refreshViewingFromServer(viewing.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };
  const renewCard = async () => {
    if (!viewing) return;
    try {
      await api.post(`/clients/${viewing.id}/renew-card`);
      toast.success("Card renewed for 1 year");
      await refreshViewingFromServer(viewing.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };
  const revokeCard = async () => {
    if (!viewing) return;
    if (!window.confirm("Revoke this member card? Public verify will show REVOKED.")) return;
    try {
      await api.post(`/clients/${viewing.id}/revoke-card`);
      toast.success("Card revoked");
      await refreshViewingFromServer(viewing.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };
  const downloadCardPdf = async () => {
    if (!viewing) return;
    try {
      // Authenticated fetch — cookies are automatically sent by axios (withCredentials).
      // Using `window.open` on the raw URL is unreliable across browsers/tab-restore
      // (Chrome sometimes strips SameSite cookies on new-tab GETs), so we stream the
      // PDF via the axios instance and open the resulting blob URL instead.
      const res = await api.get(`/clients/${viewing.id}/card-pdf`, {
        responseType: "blob",
      });
      const blob = new Blob([res.data], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const win = window.open(url, "_blank", "noopener,noreferrer");
      // Fallback if the popup was blocked — force a download link
      if (!win) {
        const a = document.createElement("a");
        a.href = url;
        a.download = `member-card-${viewing.member_no || viewing.id}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
      // Release the blob URL after the tab has had a moment to load it
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      const detail =
        e.response?.status === 401
          ? "Session expired — please sign in again."
          : e.response?.data?.detail || "Failed to load card PDF";
      toast.error(detail);
    }
  };
  const copyVerifyLink = async () => {
    if (!viewing?.member_verify_token) return;
    const url = `${window.location.origin}/verify/${viewing.member_verify_token}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Verify link copied");
    } catch {
      toast.error("Copy failed — link: " + url);
    }
  };

  const cardStatus = (c) => {
    if (!c?.member_no) return "none";
    if (c.member_status === "revoked") return "revoked";
    if (c.member_expires_at && c.member_expires_at < new Date().toISOString().slice(0, 10)) return "expired";
    return c.member_status || "active";
  };
  const cardStatusStyles = {
    active: "bg-emerald-50 text-emerald-800 border-emerald-200",
    expired: "bg-amber-50 text-amber-800 border-amber-200",
    revoked: "bg-rose-50 text-rose-800 border-rose-200",
    none: "bg-stone-50 text-stone-600 border-stone-200",
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
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">{t("clients")}</h1>
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
                <DialogDescription className="sr-only">
                  Create or edit a client profile including ID, address and photo.
                </DialogDescription>
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
              <tr key={r.id} className="border-t border-stone-100 hover:bg-stone-50/50">
                <Td>
                  {(() => {
                    const src = clientPhotoSrc(r);
                    return src ? (
                      <img
                        alt=""
                        src={src}
                        onError={(e) => { e.currentTarget.style.display = "none"; }}
                        className="w-10 h-10 rounded-full object-cover border border-stone-200"
                        data-testid={`client-thumb-${r.id}`}
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-stone-100 border border-stone-200" />
                    );
                  })()}
                </Td>
                <Td className="font-medium whitespace-nowrap max-w-[200px] truncate" title={r.full_name}>{r.full_name}</Td>
                <Td className="whitespace-nowrap">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200">
                    {r.id_type}
                  </span>
                </Td>
                <Td className="whitespace-nowrap">{r.id_number}</Td>
                <Td className="whitespace-nowrap">{r.phone}</Td>
                <Td className="whitespace-nowrap">{r.municipality}</Td>
                <Td right>
                  <div className="flex justify-end gap-1.5">
                    <button
                      onClick={() => openDetail(r)}
                      data-testid={`client-view-${r.id}`}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#1B2D5C] text-white hover:bg-[#0F1B3A] transition-colors"
                      title={t("view_details")}
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => edit(r)}
                      data-testid={`client-edit-${r.id}`}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#C17767] text-white hover:bg-[#A96253] transition-colors"
                      title={t("edit")}
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => remove(r.id)}
                      data-testid={`client-delete-${r.id}`}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#993333] text-white hover:bg-[#7A2828] transition-colors"
                      title={t("delete")}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
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
            <DialogDescription className="sr-only">
              Client photo, contact info, member card status and full payment history.
            </DialogDescription>
          </DialogHeader>
          {viewing && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-[160px,1fr] gap-6">
                {(() => {
                  const src = clientPhotoSrc(viewing);
                  return src ? (
                    <img
                      alt=""
                      src={src}
                      onError={(e) => { e.currentTarget.style.display = "none"; }}
                      className="w-40 h-40 rounded-md object-cover border border-stone-200"
                      data-testid="client-detail-photo"
                    />
                  ) : (
                    <div className="w-40 h-40 rounded-md bg-stone-100 border border-stone-200 flex items-center justify-center text-stone-400 text-xs text-center px-2">
                      {viewing.photo_url ? "Issue a Member Card to display the photo publicly" : t("no_items")}
                    </div>
                  );
                })()}
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

              {/* Member ID Card panel */}
              <div className="rounded-md border border-stone-200 bg-stone-50/50 p-4" data-testid="member-card-panel">
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-md bg-[#1B2D5C] text-white flex items-center justify-center">
                      <IdCard className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-eyebrow">Member ID Card</div>
                      {viewing.member_no ? (
                        <div className="text-sm text-stone-700">
                          <span className="font-mono font-semibold" data-testid="member-no">{viewing.member_no}</span>
                          <span className="text-stone-400 mx-2">·</span>
                          <span className={`inline-block text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border ${cardStatusStyles[cardStatus(viewing)]}`}
                                data-testid="member-status">
                            {cardStatus(viewing)}
                          </span>
                          {viewing.member_expires_at && (
                            <span className="text-xs text-stone-500 ml-2">Expires {viewing.member_expires_at}</span>
                          )}
                        </div>
                      ) : (
                        <div className="text-sm text-stone-500">No card issued yet</div>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {!viewing.member_no && (
                      <Button onClick={issueCard} className="bg-[#1B2D5C] hover:bg-[#0F1B3A] gap-2" data-testid="member-issue-btn">
                        <IdCard className="w-4 h-4" /> Issue Card
                      </Button>
                    )}
                    {viewing.member_no && (
                      <>
                        <Button onClick={downloadCardPdf} variant="outline" className="gap-2 border-[#DC2626] text-[#DC2626] hover:bg-[#DC2626] hover:text-white"
                                data-testid="member-download-btn">
                          <Download className="w-4 h-4" /> PDF
                        </Button>
                        <Button onClick={copyVerifyLink} variant="outline" className="gap-2" data-testid="member-copy-link-btn">
                          <Copy className="w-4 h-4" /> Verify Link
                        </Button>
                        <Button onClick={renewCard} variant="outline" className="gap-2" data-testid="member-renew-btn">
                          <RefreshCw className="w-4 h-4" /> Renew 1 yr
                        </Button>
                        {isAdmin && cardStatus(viewing) !== "revoked" && (
                          <Button onClick={revokeCard} variant="outline" className="gap-2 border-rose-300 text-rose-700 hover:bg-rose-50"
                                  data-testid="member-revoke-btn">
                            <Ban className="w-4 h-4" /> Revoke
                          </Button>
                        )}
                      </>
                    )}
                  </div>
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
                <div className="flex items-center justify-between mb-2">
                  <div className="text-eyebrow">{t("payment_summary")} · {t("payment_history")} ({viewPayments.length})</div>
                </div>
                {viewPayments.length > 0 && (
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3" data-testid="client-payment-summary">
                    {(() => {
                      const total = viewPayments.reduce((s, p) => s + Number(p.amount || 0), 0);
                      const byType = (t1) => viewPayments
                        .filter((p) => p.type === t1)
                        .reduce((s, p) => s + Number(p.amount || 0), 0);
                      const tFull = byType("full") + byType("overdue_full");
                      const tPartial = byType("partial");
                      const tInterest = byType("interest_only") + byType("overdue_interest_pen");
                      const tPenalty = byType("overdue_penalty_only");
                      const cards = [
                        { label: "Total Paid", val: total, color: "bg-emerald-50 border-emerald-200 text-emerald-900" },
                        { label: "Full / Close-out", val: tFull, color: "bg-stone-50 border-stone-200 text-stone-900" },
                        { label: "Partial", val: tPartial, color: "bg-blue-50 border-blue-200 text-blue-900" },
                        { label: "Interest", val: tInterest, color: "bg-amber-50 border-amber-200 text-amber-900" },
                        { label: "Penalty", val: tPenalty, color: "bg-red-50 border-red-200 text-red-900" },
                      ];
                      return cards.map((c) => (
                        <div key={c.label} className={`rounded-md border px-3 py-2 ${c.color}`}>
                          <div className="text-[10px] uppercase tracking-wider opacity-80">{c.label}</div>
                          <div className="font-display text-base">${Number(c.val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                        </div>
                      ));
                    })()}
                  </div>
                )}
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
                          <Td className="font-medium" title={p.receipt_number}>{shortReceipt(p.receipt_number)}</Td>
                          <Td title={p.contract_number}>{shortContract(p.contract_number)}</Td>
                          <Td>{p.type.replace("_", " ")}</Td>
                          <Td right>${Number(p.amount).toLocaleString()}</Td>
                          <Td>{p.date}</Td>
                          <Td right>
                            <a
                              href={`${API_BASE}/payments/${p.id}/pdf`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-[#DC2626] hover:text-[#B91C1C] hover:underline"
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
    <th className={`px-3 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap ${right ? "text-right" : ""}`}>
      {children}
    </th>
  );
}
function Td({ children, right, className = "", ...rest }) {
  return <td className={`px-3 py-3 ${right ? "text-right" : ""} ${className}`} {...rest}>{children}</td>;
}
