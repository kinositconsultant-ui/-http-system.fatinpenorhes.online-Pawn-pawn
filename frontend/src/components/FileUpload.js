import { useRef, useState } from "react";
import { api, API_BASE } from "../lib/api";
import { Button } from "./ui/button";
import { Upload, X, FileText } from "lucide-react";
import { toast } from "sonner";

/**
 * FileUpload — uploads a file via /api/upload and returns the public path
 *   via onChange(value). Stores `storage_path` (e.g. fatin-penhores/uploads/.../uuid.png)
 *   The display uses /api/files/<path> with cookie auth.
 */
export default function FileUpload({
  value,
  onChange,
  accept = "image/*",
  label = "Upload",
  testid,
}) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);

  const upload = async (file) => {
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onChange(data.storage_path);
      toast.success("Uploaded");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    }
    setBusy(false);
  };

  const handleChange = (e) => {
    const f = e.target.files?.[0];
    if (f) upload(f);
    e.target.value = "";
  };

  const fileUrl = value ? `${API_BASE}/files/${value}` : null;
  const isImage = (value || "").match(/\.(png|jpe?g|webp|gif)$/i);

  return (
    <div className="space-y-2" data-testid={testid}>
      <input
        type="file"
        ref={inputRef}
        accept={accept}
        onChange={handleChange}
        className="hidden"
        data-testid={`${testid}-input`}
      />
      {value ? (
        <div className="flex items-center gap-3 p-2 rounded-md border border-stone-200 bg-stone-50">
          {isImage ? (
            <img
              alt=""
              src={fileUrl}
              className="w-14 h-14 object-cover rounded"
            />
          ) : (
            <div className="w-14 h-14 flex items-center justify-center bg-white rounded border border-stone-200">
              <FileText className="w-6 h-6 text-stone-500" />
            </div>
          )}
          <div className="flex-1 text-xs text-stone-600 truncate">
            {value.split("/").pop()}
          </div>
          <button
            type="button"
            onClick={() => onChange("")}
            className="p-1 hover:text-[#993333]"
            data-testid={`${testid}-clear`}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <Button
          type="button"
          variant="outline"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          data-testid={`${testid}-btn`}
        >
          <Upload className="w-4 h-4 mr-2" /> {busy ? "…" : label}
        </Button>
      )}
    </div>
  );
}
