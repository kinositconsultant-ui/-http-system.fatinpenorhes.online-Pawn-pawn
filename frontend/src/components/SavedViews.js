import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Bookmark, BookmarkPlus, Trash2, Check, Pin, PinOff, AlertCircle } from "lucide-react";

/**
 * Per-user saved views for the Reports page.
 * A view stores the currently-active tab + filters + sort combo.
 * Props:
 *  - tab, filters, sort           → current state (used when saving)
 *  - onApply({tab, filters, sort}) → parent applies the view
 */
export default function SavedViews({ tab, filters, sort, onApply }) {
  const { t } = useLang();
  const [views, setViews] = useState([]);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/report-views");
      setViews(data || []);
    } catch {
      setViews([]);
    }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    const n = name.trim();
    if (!n) return;
    setSaving(true);
    try {
      await api.post("/report-views", { name: n, tab, filters, sort });
      setName("");
      await load();
    } catch (e) {
      alert(`Save failed: ${e?.response?.data?.detail || e.message}`);
    }
    setSaving(false);
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this saved view?")) return;
    try {
      await api.delete(`/report-views/${id}`);
      await load();
    } catch (e) {
      alert(`Delete failed: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const togglePin = async (id) => {
    try {
      await api.patch(`/report-views/${id}/pin`);
      await load();
    } catch (e) {
      alert(`Pin failed: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const setThreshold = async (id, value) => {
    const n = value === "" || value == null ? null : parseInt(value, 10);
    if (n != null && (Number.isNaN(n) || n < 0)) return;
    try {
      await api.patch(`/report-views/${id}/threshold`, { alert_threshold: n });
      await load();
    } catch (e) {
      alert(`Threshold failed: ${e?.response?.data?.detail || e.message}`);
    }
  };

  // Views for the current tab first, then rest
  const forTab = views.filter((v) => v.tab === tab);
  const others = views.filter((v) => v.tab !== tab);

  return (
    <div
      className="border border-stone-200 rounded-lg bg-white p-3 print:hidden"
      data-testid="saved-views"
    >
      <div className="flex items-center gap-2 mb-2">
        <Bookmark className="w-4 h-4 text-[#1B2D5C]" />
        <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500 font-semibold">
          {t("saved_views")}
        </div>
        {views.length > 0 && (
          <span className="text-[10px] text-stone-400">· {views.length}</span>
        )}
      </div>

      {views.length === 0 ? (
        <div className="text-xs text-stone-500 mb-3">{t("no_saved_views")}</div>
      ) : (
        <div className="flex flex-wrap gap-1.5 mb-3" data-testid="saved-views-list">
          {[...forTab, ...others].map((v) => {
            const sameTab = v.tab === tab;
            return (
              <div
                key={v.id}
                className={`group inline-flex items-center gap-1 pl-2.5 pr-1 py-1 rounded-full text-xs border transition ${
                  sameTab
                    ? "border-[#1B2D5C]/30 bg-[#1B2D5C]/5 text-[#1B2D5C]"
                    : "border-stone-200 bg-stone-50 text-stone-600"
                }`}
                data-testid={`saved-view-${v.id}`}
              >
                <button
                  onClick={() => onApply({ tab: v.tab, filters: v.filters || {}, sort: v.sort || null })}
                  className="hover:underline underline-offset-2"
                  title={`Apply: ${v.tab}${v.sort ? ` · sort ${v.sort.key} ${v.sort.dir}` : ""}`}
                  data-testid={`saved-view-apply-${v.id}`}
                >
                  {v.name}
                </button>
                <span className="text-[9px] uppercase tracking-wider text-stone-400 px-1">
                  {v.tab.replace("-", " ")}
                </span>
                <button
                  onClick={() => togglePin(v.id)}
                  className={`p-0.5 rounded transition ${
                    v.pinned
                      ? "text-[#1B2D5C] opacity-100"
                      : "text-stone-400 hover:text-[#1B2D5C] opacity-60 group-hover:opacity-100"
                  }`}
                  title={v.pinned ? "Unpin from Dashboard" : "Pin to Dashboard"}
                  data-testid={`saved-view-pin-${v.id}`}
                >
                  {v.pinned
                    ? <Pin className="w-3 h-3 fill-[#1B2D5C]" />
                    : <PinOff className="w-3 h-3" />
                  }
                </button>
                {v.pinned && (
                  <span
                    className="inline-flex items-center gap-1 text-[9px] text-stone-400"
                    title="Show a red alert dot on the Dashboard when the row count exceeds this number. Leave blank to disable."
                  >
                    <AlertCircle className="w-2.5 h-2.5" />
                    <span>&gt;</span>
                    <input
                      type="number"
                      min={0}
                      max={100000}
                      defaultValue={v.alert_threshold ?? ""}
                      onBlur={(e) => {
                        const raw = e.target.value.trim();
                        const cur = v.alert_threshold;
                        const nextVal = raw === "" ? null : parseInt(raw, 10);
                        if (nextVal === cur) return;
                        setThreshold(v.id, raw);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") e.target.blur();
                      }}
                      className="w-9 h-4 px-1 text-[10px] rounded border border-stone-200 bg-white text-stone-700 focus:border-[#1B2D5C] focus:outline-none"
                      placeholder="—"
                      data-testid={`saved-view-threshold-${v.id}`}
                    />
                  </span>
                )}
                <button
                  onClick={() => remove(v.id)}
                  className="opacity-0 group-hover:opacity-100 text-stone-400 hover:text-red-600 p-0.5 rounded transition"
                  title="Delete saved view"
                  data-testid={`saved-view-delete-${v.id}`}
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("view_name")}
          className="h-8 text-xs w-56"
          maxLength={60}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
          }}
          data-testid="saved-view-name-input"
        />
        <Button
          onClick={save}
          disabled={!name.trim() || saving}
          size="sm"
          className="h-8 bg-[#1B2D5C] hover:bg-[#0F1B3A] text-white text-xs"
          data-testid="saved-view-save"
        >
          {saving ? <Check className="w-3.5 h-3.5" /> : <BookmarkPlus className="w-3.5 h-3.5 mr-1" />}
          {t("save_view")}
        </Button>
        <span className="text-[10px] text-stone-400">
          Saves current tab + filters + sort
        </span>
      </div>
    </div>
  );
}
