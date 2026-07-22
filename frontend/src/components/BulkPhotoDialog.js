import { useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Upload, X, CheckCircle2, AlertCircle, Loader2, Images } from "lucide-react";
import { toast } from "sonner";

/**
 * BulkPhotoDialog — attach photos to many items in one pass.
 *
 * Props:
 *   open, onOpenChange — dialog visibility
 *   kind               — "car" | "motorcycle" | "electronic" | "pezadu"
 *   items              — full list of items for the current kind; filtered internally
 *                        to those still missing a photo
 *   onDone()           — called after uploads finish so the parent can reload
 *
 * Flow:
 *   1. Drop or pick N image files at the top of the dialog.
 *   2. Files are paired with photo-less items in order (1st file → 1st item …).
 *   3. Users can override any single row with its own file picker.
 *   4. "Upload All" uploads each file via /api/upload (which returns a
 *      thumbnail_storage_path for images) and then PATCHes the item.
 */
export default function BulkPhotoDialog({ open, onOpenChange, kind, items, onDone }) {
  const photoless = useMemo(
    () => (items || []).filter((r) => !r.photo_url),
    [items]
  );

  // Map item.id → File object staged for upload
  const [pending, setPending] = useState({}); // {id: File}
  // Map item.id → "queued" | "uploading" | "done" | "error"
  const [status, setStatus] = useState({});
  const [busy, setBusy] = useState(false);
  const bulkInputRef = useRef(null);

  const reset = () => {
    setPending({});
    setStatus({});
    setBusy(false);
  };

  const handleClose = (o) => {
    if (!o && busy) return; // don't allow close mid-upload
    if (!o) reset();
    onOpenChange(o);
  };

  // Pair files with photo-less items in list order.
  const assignBulk = (files) => {
    const list = Array.from(files || []).filter((f) => f.type.startsWith("image/"));
    if (!list.length) {
      toast.error("Only image files are supported");
      return;
    }
    const next = { ...pending };
    // Fill any unassigned rows first, from the top.
    let fi = 0;
    for (const row of photoless) {
      if (fi >= list.length) break;
      if (!next[row.id]) {
        next[row.id] = list[fi];
        fi += 1;
      }
    }
    // Overflow files replace already-assigned rows in order.
    if (fi < list.length) {
      for (const row of photoless) {
        if (fi >= list.length) break;
        next[row.id] = list[fi];
        fi += 1;
      }
    }
    setPending(next);
  };

  const setRow = (id, file) => {
    setPending((p) => ({ ...p, [id]: file }));
  };

  const clearRow = (id) => {
    setPending((p) => {
      const n = { ...p };
      delete n[id];
      return n;
    });
    setStatus((s) => {
      const n = { ...s };
      delete n[id];
      return n;
    });
  };

  const runUploads = async () => {
    const entries = Object.entries(pending);
    if (!entries.length) {
      toast.error("Pick at least one photo");
      return;
    }
    setBusy(true);
    // Initialise every row as queued so the UI shows progress
    const initial = {};
    for (const [id] of entries) initial[id] = "queued";
    setStatus(initial);
    let ok = 0;
    let fail = 0;
    for (const [id, file] of entries) {
      setStatus((s) => ({ ...s, [id]: "uploading" }));
      try {
        const fd = new FormData();
        fd.append("file", file);
        const up = await api.post("/upload", fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        await api.patch(`/items/${kind}/${id}/photo`, {
          photo_url: up.data.storage_path,
          thumbnail_url: up.data.thumbnail_storage_path || "",
        });
        setStatus((s) => ({ ...s, [id]: "done" }));
        ok += 1;
      } catch (e) {
        setStatus((s) => ({ ...s, [id]: "error" }));
        fail += 1;
      }
    }
    setBusy(false);
    if (ok) toast.success(`Attached ${ok} photo${ok > 1 ? "s" : ""}`);
    if (fail) toast.error(`${fail} upload${fail > 1 ? "s" : ""} failed`);
    if (ok) onDone?.();
  };

  const totalPending = Object.keys(pending).length;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl" data-testid="bulk-photo-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Images className="w-5 h-5 text-[#1B2D5C]" />
            Bulk photo upload — {kind}
          </DialogTitle>
        </DialogHeader>

        <p className="text-xs text-stone-500 -mt-2">
          {photoless.length === 0
            ? "Every item in this tab already has a photo."
            : `${photoless.length} item${photoless.length > 1 ? "s" : ""} missing a photo. Drop images below — they'll be paired with rows top-to-bottom.`}
        </p>

        {photoless.length > 0 && (
          <>
            {/* Drop zone */}
            <label
              className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-stone-300 hover:border-[#1B2D5C] rounded-lg p-6 cursor-pointer bg-stone-50"
              onDragOver={(e) => {
                e.preventDefault();
              }}
              onDrop={(e) => {
                e.preventDefault();
                assignBulk(e.dataTransfer.files);
              }}
              data-testid="bulk-photo-dropzone"
            >
              <Upload className="w-6 h-6 text-stone-500" />
              <div className="text-sm text-stone-700">
                Drag and drop images here, or click to select
              </div>
              <div className="text-[11px] text-stone-500">
                JPG / PNG / WEBP · up to 15 MB each · assigned in list order
              </div>
              <input
                ref={bulkInputRef}
                type="file"
                multiple
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  assignBulk(e.target.files);
                  e.target.value = "";
                }}
                data-testid="bulk-photo-input"
              />
            </label>

            {/* Row list */}
            <div className="max-h-[45vh] overflow-y-auto rounded-md border border-stone-200 divide-y divide-stone-100">
              {photoless.map((row) => (
                <BulkPhotoRow
                  key={row.id}
                  row={row}
                  kind={kind}
                  file={pending[row.id]}
                  status={status[row.id]}
                  onPick={(f) => setRow(row.id, f)}
                  onClear={() => clearRow(row.id)}
                  disabled={busy}
                />
              ))}
            </div>
          </>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={busy}
            data-testid="bulk-photo-cancel"
          >
            {busy ? "Uploading…" : "Close"}
          </Button>
          {photoless.length > 0 && (
            <Button
              onClick={runUploads}
              disabled={busy || totalPending === 0}
              className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
              data-testid="bulk-photo-upload-all"
            >
              {busy ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Uploading
                </>
              ) : (
                <>Upload {totalPending || ""} photo{totalPending === 1 ? "" : "s"}</>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function BulkPhotoRow({ row, kind, file, status, onPick, onClear, disabled }) {
  const inputRef = useRef(null);
  const label =
    row.name?.trim() ||
    `${row.brand || ""} ${row.model || ""}`.trim() ||
    row.plate ||
    row.serial ||
    row.id.slice(0, 8);
  const previewUrl = file ? URL.createObjectURL(file) : null;

  return (
    <div
      className="flex items-center gap-3 px-3 py-2 text-sm"
      data-testid={`bulk-photo-row-${row.id}`}
    >
      {/* Preview */}
      <div className="w-12 h-12 rounded bg-stone-100 border border-stone-200 flex items-center justify-center overflow-hidden shrink-0">
        {previewUrl ? (
          <img alt="" src={previewUrl} className="w-full h-full object-cover" />
        ) : (
          <span className="text-[10px] text-stone-400">no file</span>
        )}
      </div>

      {/* Meta */}
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{label}</div>
        <div className="text-xs text-stone-500 truncate">
          {row.plate || row.serial || row.chassis || row.category || kind}
        </div>
      </div>

      {/* Status */}
      <div className="w-24 text-right shrink-0">
        {status === "done" && (
          <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
            <CheckCircle2 className="w-4 h-4" /> attached
          </span>
        )}
        {status === "error" && (
          <span className="inline-flex items-center gap-1 text-xs text-rose-700">
            <AlertCircle className="w-4 h-4" /> failed
          </span>
        )}
        {status === "uploading" && (
          <span className="inline-flex items-center gap-1 text-xs text-stone-600">
            <Loader2 className="w-3 h-3 animate-spin" /> uploading
          </span>
        )}
        {status === "queued" && (
          <span className="text-xs text-stone-500">queued</span>
        )}
      </div>

      {/* File picker / clear */}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
          e.target.value = "";
        }}
        data-testid={`bulk-photo-row-input-${row.id}`}
      />
      {file ? (
        <button
          type="button"
          onClick={onClear}
          disabled={disabled}
          className="p-1 text-stone-400 hover:text-[#993333] disabled:opacity-40"
          data-testid={`bulk-photo-row-clear-${row.id}`}
        >
          <X className="w-4 h-4" />
        </button>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          data-testid={`bulk-photo-row-pick-${row.id}`}
        >
          Choose
        </Button>
      )}
    </div>
  );
}
