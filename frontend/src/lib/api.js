import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

export function pdfUrl(path) {
  return `${API_BASE}${path}`;
}

/**
 * Build a full public URL for a client-uploaded file (photo, document, etc.).
 * Handles the shapes the backend / DB may store:
 *   - Absolute URL:    "https://cdn.example.com/…" → returned as-is
 *   - Full API path:   "/api/files/foo.jpg"        → prefixed with backend origin
 *   - Relative /files: "/files/foo.jpg"            → prefixed with `${API_BASE}`
 *   - Storage key:     "fatin-penhores/uploads/…"  → served via `${API_BASE}/files/<key>`
 * Returns "" for null/undefined so <img> tags can conditionally render.
 */
export function fileUrl(pathOrKey) {
  if (!pathOrKey) return "";
  const s = String(pathOrKey);
  if (/^https?:\/\//i.test(s)) return s;
  if (s.startsWith("/api/")) return `${BACKEND_URL}${s}`;
  if (s.startsWith("/files/")) return `${API_BASE}${s}`;
  const key = s.startsWith("/") ? s.slice(1) : s;
  return `${API_BASE}/files/${key}`;
}

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}
