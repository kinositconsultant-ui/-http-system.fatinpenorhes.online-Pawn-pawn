import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Warehouse as WarehouseIcon,
  Car,
  Bike,
  Truck,
  CheckCircle2,
  Camera,
  Search,
  Fuel,
  Gauge,
  ClipboardCheck,
} from "lucide-react";
import { toast } from "sonner";

const KIND_ICON = { car: Car, motorcycle: Bike, pezadu: Truck };

export default function WarehouseReceipts() {
  const [pending, setPending] = useState([]);
  const [receipts, setReceipts] = useState([]);
  const [tab, setTab] = useState("pending");
  const [q, setQ] = useState("");
  const [receiveFor, setReceiveFor] = useState(null);
  const [form, setForm] = useState({
    condition: "good",
    fuel_percent: "",
    mileage_km: "",
    notes: "",
    photo_url: "",
    thumbnail_url: "",
  });
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const [p, r] = await Promise.all([
      api.get("/warehouse/pending"),
      api.get("/warehouse/receipts"),
    ]);
    setPending(p.data);
    setReceipts(r.data);
  };
  useEffect(() => { load(); }, []);

  const filteredPending = useMemo(() => {
    if (!q.trim()) return pending;
    const s = q.toLowerCase();
    return pending.filter((r) =>
      [r.contract_number, r.client_name, r.item?.brand, r.item?.model, r.item?.plate]
        .filter(Boolean)
        .some((v) => v.toLowerCase().includes(s))
    );
  }, [pending, q]);

  const openReceive = (row) => {
    setReceiveFor(row);
    setForm({
      condition: "good",
      fuel_percent: row.item?.fuel_percent ?? "",
      mileage_km: row.item?.mileage_km ?? "",
      notes: "",
      photo_url: "",
      thumbnail_url: "",
    });
  };

  const uploadPhoto = async (file) => {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setForm((f) => ({
        ...f,
        photo_url: data.storage_path,
        thumbnail_url: data.thumbnail_storage_path || "",
      }));
      toast.success("Photo attached");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const confirm = async () => {
    if (!receiveFor) return;
    setSaving(true);
    try {
      const payload = {
        condition: form.condition,
        fuel_percent: form.fuel_percent === "" ? null : Number(form.fuel_percent),
        mileage_km: form.mileage_km === "" ? null : Number(form.mileage_km),
        notes: form.notes,
        photo_url: form.photo_url,
        thumbnail_url: form.thumbnail_url,
      };
      await api.post(`/warehouse/receipts/${receiveFor.id}`, payload);
      toast.success("Receipt confirmed");
      setReceiveFor(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="warehouse-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">Warehouse Operations</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">
            Warehouse Receipts
          </h1>
          <p className="text-sm text-stone-600 mt-1 max-w-2xl">
            After the office signs a contract, physical assets (car, motorcycle,
            pezadu) are delivered here. Confirm receipt, record condition, fuel
            level and mileage, and attach a photo for the audit trail.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={tab === "pending" ? "default" : "outline"}
            onClick={() => setTab("pending")}
            data-testid="wh-tab-pending"
            className={tab === "pending" ? "bg-[#1B2D5C] hover:bg-[#0F1B3A]" : ""}
          >
            <WarehouseIcon className="w-4 h-4 mr-1" />
            Pending ({pending.length})
          </Button>
          <Button
            variant={tab === "history" ? "default" : "outline"}
            onClick={() => setTab("history")}
            data-testid="wh-tab-history"
            className={tab === "history" ? "bg-[#1B2D5C] hover:bg-[#0F1B3A]" : ""}
          >
            <CheckCircle2 className="w-4 h-4 mr-1" />
            History ({receipts.length})
          </Button>
        </div>
      </header>

      {tab === "pending" && (
        <>
          <Card className="p-3 border border-stone-200 shadow-none rounded-lg bg-white">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 w-4 h-4 text-stone-400" />
              <Input
                className="pl-8"
                placeholder="Search contract / client / plate…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                data-testid="wh-search"
              />
            </div>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredPending.length === 0 && (
              <div className="col-span-full text-center text-stone-400 py-10 text-sm">
                Nothing waiting to be received.
              </div>
            )}
            {filteredPending.map((r) => {
              const Icon = KIND_ICON[r.item_type] || Car;
              const label = r.item?.name ||
                `${r.item?.brand || ""} ${r.item?.model || ""}`.trim();
              return (
                <Card
                  key={r.id}
                  className="p-4 border border-stone-200 hover:border-[#1B2D5C]/40 hover:shadow-md transition-all"
                  data-testid={`wh-pending-${r.id}`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-[#1B2D5C]/10 flex items-center justify-center">
                      <Icon className="w-5 h-5 text-[#1B2D5C]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-xs text-stone-500">
                        {r.contract_number}
                      </div>
                      <div className="font-semibold truncate">
                        {label || "—"}
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 text-xs text-stone-600 space-y-1">
                    <div>Client: <span className="font-medium">{r.client_name || "—"}</span></div>
                    {r.item?.plate && (
                      <div>Plate: <span className="font-mono">{r.item.plate}</span></div>
                    )}
                    <div>Signed: {r.contract_date}</div>
                  </div>
                  <Button
                    className="mt-3 w-full bg-[#1B2D5C] hover:bg-[#0F1B3A]"
                    onClick={() => openReceive(r)}
                    data-testid={`wh-receive-${r.id}`}
                  >
                    <ClipboardCheck className="w-4 h-4 mr-1" />
                    Confirm receipt
                  </Button>
                </Card>
              );
            })}
          </div>
        </>
      )}

      {tab === "history" && (
        <Card className="p-0 border border-stone-200 shadow-none rounded-lg bg-white overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="wh-history-table">
            <thead className="bg-stone-50 text-left">
              <tr>
                <Th>When</Th>
                <Th>Contract</Th>
                <Th>Client</Th>
                <Th>Kind</Th>
                <Th>Received by</Th>
                <Th>Condition</Th>
                <Th right>Fuel %</Th>
                <Th right>km</Th>
                <Th>Notes</Th>
              </tr>
            </thead>
            <tbody>
              {receipts.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center py-6 text-stone-400">
                    No receipts recorded yet.
                  </td>
                </tr>
              )}
              {receipts.map((r) => (
                <tr key={r.id} className="border-t border-stone-100 hover:bg-stone-50/60">
                  <Td className="whitespace-nowrap">
                    {new Date(r.warehouse_received_at).toLocaleString()}
                  </Td>
                  <Td className="font-mono text-xs">{r.contract_number}</Td>
                  <Td>{r.client_name || "—"}</Td>
                  <Td>{r.item_type}</Td>
                  <Td>{r.warehouse_received_by_name || "—"}</Td>
                  <Td>{r.warehouse_receipt_condition || "—"}</Td>
                  <Td right>{r.warehouse_receipt_fuel_percent ?? "—"}</Td>
                  <Td right>{r.warehouse_receipt_mileage_km?.toLocaleString?.() ?? "—"}</Td>
                  <Td>
                    <div className="max-w-[240px] truncate" title={r.warehouse_receipt_notes}>
                      {r.warehouse_receipt_notes || "—"}
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Confirm dialog */}
      <Dialog open={!!receiveFor} onOpenChange={(o) => !o && setReceiveFor(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ClipboardCheck className="w-5 h-5 text-[#1B2D5C]" />
              Confirm warehouse receipt
            </DialogTitle>
          </DialogHeader>
          {receiveFor && (
            <div className="space-y-3">
              <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm">
                <div className="font-mono text-xs text-stone-500">
                  {receiveFor.contract_number}
                </div>
                <div className="font-semibold">
                  {receiveFor.item?.name ||
                    `${receiveFor.item?.brand || ""} ${receiveFor.item?.model || ""}`.trim()}
                </div>
                <div className="text-xs text-stone-500">
                  Client: {receiveFor.client_name || "—"}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs uppercase tracking-wide text-stone-500">
                    Condition
                  </Label>
                  <select
                    className="mt-1 w-full border border-stone-300 rounded-md px-2 py-2 text-sm"
                    value={form.condition}
                    onChange={(e) => setForm({ ...form, condition: e.target.value })}
                    data-testid="wh-form-condition"
                  >
                    <option value="good">Good</option>
                    <option value="minor damage">Minor damage</option>
                    <option value="damaged">Damaged</option>
                    <option value="not operational">Not operational</option>
                  </select>
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wide text-stone-500 inline-flex items-center gap-1">
                    <Fuel className="w-3 h-3" /> Fuel %
                  </Label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={form.fuel_percent}
                    onChange={(e) => setForm({ ...form, fuel_percent: e.target.value })}
                    data-testid="wh-form-fuel"
                  />
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wide text-stone-500 inline-flex items-center gap-1">
                    <Gauge className="w-3 h-3" /> Mileage (km)
                  </Label>
                  <Input
                    type="number"
                    value={form.mileage_km}
                    onChange={(e) => setForm({ ...form, mileage_km: e.target.value })}
                    data-testid="wh-form-km"
                  />
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wide text-stone-500 inline-flex items-center gap-1">
                    <Camera className="w-3 h-3" /> Photo at receipt (optional)
                  </Label>
                  <input
                    type="file"
                    accept="image/*"
                    className="mt-1 w-full text-xs"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) uploadPhoto(f);
                    }}
                    data-testid="wh-form-photo"
                  />
                  {form.photo_url && (
                    <div className="text-[10px] text-emerald-700 mt-0.5">
                      ✓ attached
                    </div>
                  )}
                </div>
                <div className="md:col-span-2">
                  <Label className="text-xs uppercase tracking-wide text-stone-500">
                    Notes / damage log
                  </Label>
                  <Input
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    placeholder="e.g. small scratch on rear bumper, missing spare tyre"
                    data-testid="wh-form-notes"
                  />
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setReceiveFor(null)} disabled={saving}>
              Cancel
            </Button>
            <Button
              className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
              onClick={confirm}
              disabled={saving || uploading}
              data-testid="wh-form-save"
            >
              <CheckCircle2 className="w-4 h-4 mr-1" />
              {saving ? "Saving…" : "Acknowledge receipt"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Th({ children, right }) {
  return (
    <th className={`px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap ${right ? "text-right" : ""}`}>
      {children}
    </th>
  );
}

function Td({ children, right, className = "" }) {
  return (
    <td className={`px-3 py-2 whitespace-nowrap ${right ? "text-right" : ""} ${className}`}>
      {children}
    </td>
  );
}
