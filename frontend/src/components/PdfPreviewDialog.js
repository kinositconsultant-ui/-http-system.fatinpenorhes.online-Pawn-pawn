import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Download, X } from "lucide-react";
import { useMemo, useState } from "react";

/**
 * Reusable PDF preview modal.
 *
 * Props:
 *   open, onOpenChange — dialog visibility
 *   url            — absolute (or same-origin) PDF URL
 *   title          — modal title
 *   downloadName   — suggested filename for the "Download" button
 *   langToggle     — when true, shows an EN/TET pill toggle that appends
 *                    (or replaces) `?lang=` on the URL. Use for receipts.
 */
export default function PdfPreviewDialog({
  open,
  onOpenChange,
  url,
  title = "PDF Preview",
  downloadName,
  langToggle = false,
}) {
  const [lang, setLang] = useState(() => {
    try {
      const u = new URL(url || "", window.location.origin);
      return u.searchParams.get("lang") || "en";
    } catch {
      return "en";
    }
  });
  const finalUrl = useMemo(() => {
    if (!url || !langToggle) return url;
    try {
      const u = new URL(url, window.location.origin);
      u.searchParams.set("lang", lang);
      return u.toString();
    } catch {
      return url;
    }
  }, [url, lang, langToggle]);
  const download = () => {
    if (!finalUrl) return;
    const a = document.createElement("a");
    a.href = finalUrl;
    if (downloadName) a.download = downloadName;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl w-[95vw] h-[90vh] flex flex-col p-0" data-testid="pdf-preview-dialog">
        <DialogHeader className="px-6 pt-5 pb-3 border-b border-stone-200 shrink-0">
          <div className="flex items-center justify-between gap-4">
            <DialogTitle className="font-display text-lg truncate">{title}</DialogTitle>
            <div className="flex items-center gap-2">
              {langToggle && (
                <div
                  className="inline-flex items-center rounded-md border border-stone-300 p-0.5 bg-white text-xs"
                  data-testid="pdf-preview-lang-toggle"
                >
                  {["en", "tet"].map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => setLang(opt)}
                      data-testid={`pdf-preview-lang-${opt}`}
                      className={`px-2 py-1 rounded font-semibold uppercase ${
                        lang === opt
                          ? "bg-[#1B2D5C] text-white"
                          : "text-stone-600 hover:bg-stone-100"
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}
              <Button
                onClick={download}
                className="bg-[#DC2626] hover:bg-[#B91C1C] text-white gap-2 h-8"
                data-testid="pdf-preview-download"
              >
                <Download className="w-4 h-4" /> Download
              </Button>
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-stone-100"
                data-testid="pdf-preview-close"
                aria-label="Close preview"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
          <DialogDescription className="sr-only">
            Preview the PDF in an embedded viewer, then use the Download button
            to save a copy to disk.
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 bg-stone-100 overflow-hidden">
          {open && finalUrl && (
            <iframe
              key={finalUrl}
              src={finalUrl}
              title={title}
              className="w-full h-full border-0"
              data-testid="pdf-preview-iframe"
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
