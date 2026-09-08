import { useMemo, useState } from "react";
import { api, API_BASE } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import PdfPreviewDialog from "./PdfPreviewDialog";
import { Car, Bike, Truck, Laptop, Search, PackageCheck, FileText, Fuel, Gauge, Camera, UserCheck } from "lucide-react";
import { toast } from "sonner";

const KIND_ICON = { car: Car, motorcycle: Bike, pezadu: Truck, electronic: Laptop };
const itemLabel = (r) => r.item?.name || `${r.item?.brand || ""} ${r.item?.model || ""}`.trim() || "—";
const fmtWhen = (v) => (v ? new Date(v).toLocaleString() : "—");

export function ReleaseQueue({ rows, onReleased }) {
  const [q, setQ] = useState("");
  const [target, setTarget] = useState(null);
  const filtered = useMemo(() => {
    if (!q.trim()) return rows;
    const s = q.toLowerCase();
    return rows.filter((r) =>
      [r.contract_number, r.client_name, r.item?.brand, r.item?.model, r.item?.plate]
        .filter(Boolean).some((v) => v.toLowerCase().includes(s)));
  }, [rows, q]);

  return (
    <>
      <Card className="p-3 border border-stone-200 shadow-none rounded-lg bg-white">
        <div className="relative">
          <Search className="absolute left-2 top-2.5 w-4 h-4 text-stone-400" />
          <Input className="pl-8" placeholder="Search contract / client / plate…" value={q}
            onChange={(e) => setQ(e.target.value)} data-testid="wh-release-search" />
        </div>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.length === 0 && (
          <div className="col-span-full text-center text-stone-400 py-10 text-sm" data-testid="wh-release-empty">
            No fully-paid items waiting for hand-over.
          </div>
        )}
        {filtered.map((r) => {
          const Icon = KIND_ICON[r.item_type] || Car;
          return (
            <Card key={r.id} className="p-4 border border-emerald-200 bg-emerald-50/30 hover:shadow-md transition-all"
              data-testid={`wh-release-pending-${r.id}`}>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-600/10 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-emerald-700" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-xs text-stone-500">{r.contract_number}</div>
                  <div className="font-semibold truncate">{itemLabel(r)}</div>
                </div>
                <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full bg-emerald-600 text-white">
                  {r.group}
                </span>
              </div>
              <div className="mt-3 text-xs text-stone-600 space-y-1">
                <div>Client: <span className="font-medium">{r.client_name || "—"}</span></div>
                {r.item?.plate && <div>Plate: <span className="font-mono">{r.item.plate}</span></div>}
                <div>Paid off: {r.redeemed_at ? r.redeemed_at.slice(0, 10) : "—"}</div>
              </div>
              <Button className="mt-3 w-full bg-emerald-700 hover:bg-emerald-800" onClick={() => setTarget(r)}
                data-testid={`wh-release-open-${r.id}`}>
                <PackageCheck className="w-4 h-4 mr-1" /> Release to client
              </Button>
            </Card>
          );
        })}
      </div>
      <ReleaseDialog key={target?.id || "none"} row={target} onClose={() => setTarget(null)} onReleased={onReleased} />
    </>
  );
}

function ReleaseDialog({ row, onClose, onReleased }) {
  const [form, setForm] = useState(() => ({
    collector_name: row?.client_name || "", collector_id_number: row?.client_id_number || "",
    collector_relation: "owner", condition: "good",
    fuel_percent: row?.item?.fuel_percent ?? "", mileage_km: row?.item?.mileage_km ?? "",
    notes: "", photo_url: "", thumbnail_url: "",
  }));
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const uploadPhoto = async (file) => {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setForm((f) => ({ ...f, photo_url: data.storage_path, thumbnail_url: data.thumbnail_storage_path || "" }));
      toast.success("Photo attached");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const submit = async () => {
    if (!form.collector_name?.trim()) return toast.error("Collector name is required");
    setSaving(true);
    try {
      const { data } = await api.post(`/warehouse/releases/${row.id}`, {
        ...form,
        fuel_percent: form.fuel_percent === "" ? null : Number(form.fuel_percent),
        mileage_km: form.mileage_km === "" ? null : Number(form.mileage_km),
      });
      toast.success("Item released — custody closed");
      onClose();
      onReleased(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Release failed");
    } finally {
      setSaving(false);
    }
  };

  const isVehicle = row && row.item_type !== "electronic";
  return (
    <Dialog open={!!row} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="wh-release-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-emerald-700" /> Release item to client
          </DialogTitle>
        </DialogHeader>
        {row && (
          <div className="space-y-3">
            <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm">
              <div className="font-mono text-xs text-stone-500">{row.contract_number}</div>
              <div className="font-semibold">{itemLabel(row)}</div>
              <div className="text-xs text-stone-500">Client: {row.client_name || "—"}</div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs uppercase tracking-wide text-stone-500">Collected by *</Label>
                <Input value={form.collector_name || ""} onChange={set("collector_name")} data-testid="wh-release-collector" />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wide text-stone-500">ID number</Label>
                <Input value={form.collector_id_number || ""} onChange={set("collector_id_number")} data-testid="wh-release-id" />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wide text-stone-500">Relation</Label>
                <select className="mt-1 w-full border border-stone-300 rounded-md px-2 py-2 text-sm"
                  value={form.collector_relation} onChange={set("collector_relation")} data-testid="wh-release-relation">
                  <option value="owner">Client (owner)</option>
                  <option value="representative">Representative</option>
                </select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wide text-stone-500">Condition at release</Label>
                <select className="mt-1 w-full border border-stone-300 rounded-md px-2 py-2 text-sm"
                  value={form.condition} onChange={set("condition")} data-testid="wh-release-condition">
                  <option value="good">Good</option>
                  <option value="minor damage">Minor damage</option>
                  <option value="damaged">Damaged</option>
                  <option value="not operational">Not operational</option>
                </select>
              </div>
              {isVehicle && (
                <>
                  <div>
                    <Label className="text-xs uppercase tracking-wide text-stone-500 inline-flex items-center gap-1"><Fuel className="w-3 h-3" /> Fuel %</Label>
                    <Input type="number" min={0} max={100} value={form.fuel_percent} onChange={set("fuel_percent")} data-testid="wh-release-fuel" />
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wide text-stone-500 inline-flex items-center gap-1"><Gauge className="w-3 h-3" /> Mileage (km)</Label>
                    <Input type="number" value={form.mileage_km} onChange={set("mileage_km")} data-testid="wh-release-km" />
                  </div>
                </>
              )}
              <div>
                <Label className="text-xs uppercase tracking-wide text-stone-500 inline-flex items-center gap-1"><Camera className="w-3 h-3" /> Photo at release</Label>
                <input type="file" accept="image/*" className="mt-1 w-full text-xs" data-testid="wh-release-photo"
                  onChange={(e) => e.target.files?.[0] && uploadPhoto(e.target.files[0])} />
                {form.photo_url && <div className="text-[10px] text-emerald-700 mt-0.5">✓ attached</div>}
              </div>
              <div className="md:col-span-2">
                <Label className="text-xs uppercase tracking-wide text-stone-500">Notes</Label>
                <Input value={form.notes || ""} onChange={set("notes")} placeholder="e.g. keys + documents handed over" data-testid="wh-release-notes" />
              </div>
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={submit} disabled={saving || uploading} data-testid="wh-release-save">
            <PackageCheck className="w-4 h-4 mr-1" /> {saving ? "Releasing…" : "Confirm release"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ReleaseHistory({ rows }) {
  const [preview, setPreview] = useState({ open: false });
  const th = "px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap";
  const td = "px-3 py-2 whitespace-nowrap";
  return (
    <Card className="p-0 border border-stone-200 shadow-none rounded-lg bg-white overflow-x-auto">
      <table className="min-w-full text-sm" data-testid="wh-release-history-table">
        <thead className="bg-stone-50 text-left">
          <tr>
            <th className={th}>Released</th><th className={th}>Contract</th><th className={th}>Client</th>
            <th className={th}>Kind</th><th className={th}>Collected by</th><th className={th}>ID no.</th>
            <th className={th}>Condition</th><th className={th}>Released by</th><th className={th}>Gate pass</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={9} className="text-center py-6 text-stone-400">No releases recorded yet.</td></tr>
          )}
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-stone-100 hover:bg-stone-50/60" data-testid={`wh-release-row-${r.id}`}>
              <td className={td}>{fmtWhen(r.item_released_at)}</td>
              <td className={`${td} font-mono text-xs`}>{r.contract_number}</td>
              <td className={td}>{r.client_name || "—"}</td>
              <td className={td}>{r.item_type}</td>
              <td className={td}>{r.release_collector_name || "—"}</td>
              <td className={`${td} font-mono text-xs`}>{r.release_collector_id_number || "—"}</td>
              <td className={td}>{r.release_condition || "—"}</td>
              <td className={td}>{r.released_by_name || "—"}</td>
              <td className={td}>
                <button type="button" data-testid={`wh-release-pdf-${r.id}`}
                  className="inline-flex items-center gap-1 text-xs text-[#1B2D5C] hover:underline"
                  onClick={() => setPreview({ open: true, url: `${API_BASE}/warehouse/releases/${r.id}/pdf`,
                    title: `Gate pass ${r.contract_number || ""}`, filename: `${r.contract_number || "release"}-release.pdf` })}>
                  <FileText className="w-3.5 h-3.5" /> PDF
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <PdfPreviewDialog open={preview.open} onOpenChange={(o) => setPreview((p) => ({ ...p, open: o }))}
        url={preview.url} title={preview.title} downloadName={preview.filename} />
    </Card>
  );
}
