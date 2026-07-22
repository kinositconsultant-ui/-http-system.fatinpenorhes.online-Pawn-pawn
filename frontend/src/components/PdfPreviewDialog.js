import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Download, X } from "lucide-react";

/**
 * Reusable PDF preview modal.
 * Opens the given `url` inside an iframe so the user can review the PDF
 * before deciding whether to download it. Includes a "Download" action
 * that forces a save-to-disk via the browser.
 *
 * Props:
 *   open, onOpenChange — dialog visibility
 *   url            — absolute (or same-origin) PDF URL
 *   title          — modal title (e.g. "Invoice INV-2026-0001")
 *   downloadName   — suggested filename for the "Download" button
 */
export default function PdfPreviewDialog({ open, onOpenChange, url, title = "PDF Preview", downloadName }) {
  const download = () => {
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
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
          {open && url && (
            <iframe
              key={url}
              src={url}
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
