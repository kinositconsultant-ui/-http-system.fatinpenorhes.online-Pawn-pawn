import { useState } from "react";
import { api } from "../../lib/api";
import { readPreviewPayload, exitPreview } from "../../lib/publicSite";
import { Eye, Save, ArrowLeft, X } from "lucide-react";
import { toast } from "sonner";

// Shown on every public page while previewing unsaved Settings (Settings → Preview changes).
export default function PreviewRibbon() {
  const [publishing, setPublishing] = useState(false);
  const draft = readPreviewPayload()?.draft;

  const publish = async () => {
    if (!draft) return toast.error("Preview draft not found — go back to Settings");
    setPublishing(true);
    try {
      const payload = { ...draft };
      ["whatsapp_token_masked", "whatsapp_connected", "warehouse_locked", "id"].forEach((k) => delete payload[k]);
      await api.put("/settings", payload);
      toast.success("Published — the website is now live with these changes");
      exitPreview();
      window.location.href = window.location.pathname;
    } catch (e) {
      toast.error(e.response?.data?.detail || "Publish failed (are you signed in as admin?)");
    } finally {
      setPublishing(false);
    }
  };

  const leave = () => {
    exitPreview();
    window.location.href = window.location.pathname;
  };

  const btn = "inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-semibold transition-colors";
  return (
    <div className="sticky top-0 z-[60] bg-[#B8860B] text-[#0F1B3A] px-4 py-1.5 flex items-center justify-center gap-3 flex-wrap" data-testid="site-preview-ribbon">
      <span className="inline-flex items-center gap-1.5 text-xs font-semibold">
        <Eye className="w-3.5 h-3.5" /> PREVIEW — unsaved Settings changes (Home · Services · FAQ · Contact)
      </span>
      <button type="button" onClick={publish} disabled={publishing} className={`${btn} bg-[#0F1B3A] text-white hover:bg-[#1B2D5C]`} data-testid="preview-publish">
        <Save className="w-3 h-3" /> {publishing ? "Publishing…" : "Publish now"}
      </button>
      <a href="/settings" className={`${btn} bg-white/70 hover:bg-white`} data-testid="preview-back">
        <ArrowLeft className="w-3 h-3" /> Back to Settings
      </a>
      <button type="button" onClick={leave} className={`${btn} bg-transparent hover:bg-white/40`} data-testid="preview-exit" title="Exit preview">
        <X className="w-3 h-3" /> Exit
      </button>
    </div>
  );
}
