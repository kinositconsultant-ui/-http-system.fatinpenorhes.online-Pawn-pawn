import { useEffect, useState } from "react";
import { api, pdfUrl } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Card } from "../components/ui/card";
import { toast } from "sonner";
import { Save, Send, Download, Database, RefreshCw } from "lucide-react";

export default function Settings() {
  const { t } = useLang();
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [testPhone, setTestPhone] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const [testing, setTesting] = useState(false);
  const [backups, setBackups] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [schedule, setSchedule] = useState(null);

  useEffect(() => {
    api.get("/settings").then((r) => setS(r.data));
    api.get("/admin/backups").then((r) => setBackups(r.data)).catch(() => {});
    api.get("/admin/backups/schedule").then((r) => setSchedule(r.data)).catch(() => {});
  }, []);

  const onChange = (k, v) => setS((cur) => ({ ...cur, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...s };
      // strip server-only flags
      delete payload.whatsapp_token_masked;
      delete payload.whatsapp_connected;
      delete payload.warehouse_locked;
      ["interest_rate_car", "interest_rate_motorcycle", "interest_rate_electronic", "interest_rate_pezadu", "reminder_days_before"].forEach(
        (k) => (payload[k] = Number(payload[k]))
      );
      const { data } = await api.put("/settings", payload);
      setS(data);
      toast.success("Settings saved");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
    setSaving(false);
  };

  const runReminders = async (lang) => {
    setRunning(true);
    try {
      const { data } = await api.post(`/whatsapp/reminders/run?language=${lang}`);
      toast.success(`Reminders processed: ${data.count}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
    setRunning(false);
  };

  const sendTest = async () => {
    if (!testPhone.trim()) {
      toast.error("Enter a phone number first");
      return;
    }
    setTesting(true);
    try {
      const { data } = await api.post("/whatsapp/test", {
        to_phone: testPhone.trim(),
        body: testMessage.trim(),
      });
      if (data.status === "sent") {
        toast.success(`Sent — Meta message id: ${data.meta_message_id || "ok"}`);
      } else if (data.status === "mocked") {
        toast.info("Mock mode — message logged only");
      } else {
        toast.error("Send failed: " + JSON.stringify(data.error || data));
      }
    } catch (e) {
      const detail = e.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : JSON.stringify(detail || e.message));
    }
    setTesting(false);
  };

  const generateBackup = async () => {
    setGenerating(true);
    try {
      const { data } = await api.post("/admin/backups/generate");
      setBackups(data);
      toast.success("Fresh backup generated");
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === "string"
        ? e.response.data.detail
        : "Backup failed — check backend logs");
    }
    setGenerating(false);
  };

  const generateProject = async () => {
    setGenerating(true);
    try {
      const { data } = await api.post("/admin/backups/generate-project");
      setBackups(data);
      toast.success("Full project zip generated — ready to download");
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === "string"
        ? e.response.data.detail
        : "Project zip failed — check backend logs");
    }
    setGenerating(false);
  };

  const fmtSize = (b) => {
    if (b > 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
    if (b > 1024) return `${(b / 1024).toFixed(1)} KB`;
    return `${b} B`;
  };
  const fmtAge = (iso) => {
    const ms = Date.now() - new Date(iso).getTime();
    const min = Math.floor(ms / 60000);
    if (min < 1) return "just now";
    if (min < 60) return `${min} min ago`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h} h ago`;
    return `${Math.floor(h / 24)} days ago`;
  };
  const latestBackupAt = backups.length
    ? backups.reduce((latest, b) => (b.modified > latest ? b.modified : latest), backups[0].modified)
    : null;

  if (!s) return <div className="text-stone-500">Loading…</div>;

  return (
    <div className="space-y-8" data-testid="settings-root">
      <header>
        <div className="text-eyebrow">{t("settings")}</div>
        <h1 className="font-display text-4xl font-semibold mt-1">{t("settings")}</h1>
      </header>

      <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white space-y-4">
        <h2 className="font-display text-xl">{t("interest_defaults")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Field label={`${t("car")} %`}>
            <Input
              type="number"
              value={s.interest_rate_car}
              onChange={(e) => onChange("interest_rate_car", e.target.value)}
              data-testid="settings-rate-car"
            />
          </Field>
          <Field label={`${t("motorcycle")} %`}>
            <Input
              type="number"
              value={s.interest_rate_motorcycle}
              onChange={(e) => onChange("interest_rate_motorcycle", e.target.value)}
              data-testid="settings-rate-motorcycle"
            />
          </Field>
          <Field label={`${t("electronic")} %`}>
            <Input
              type="number"
              value={s.interest_rate_electronic}
              onChange={(e) => onChange("interest_rate_electronic", e.target.value)}
              data-testid="settings-rate-electronic"
            />
          </Field>
          <Field label={`${t("pezadu")} %`}>
            <Input
              type="number"
              value={s.interest_rate_pezadu ?? 10}
              onChange={(e) => onChange("interest_rate_pezadu", e.target.value)}
              data-testid="settings-rate-pezadu"
            />
          </Field>
        </div>
      </Card>

      <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white space-y-4">
        <h2 className="font-display text-xl">{t("terms_and_conditions")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="English">
            <Textarea
              rows={10}
              value={s.terms_and_conditions_en}
              onChange={(e) => onChange("terms_and_conditions_en", e.target.value)}
              data-testid="settings-tnc-en"
            />
          </Field>
          <Field label="Tetum">
            <Textarea
              rows={10}
              value={s.terms_and_conditions_tet}
              onChange={(e) => onChange("terms_and_conditions_tet", e.target.value)}
              data-testid="settings-tnc-tet"
            />
          </Field>
        </div>
      </Card>

      <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h2 className="font-display text-xl">Public Warehouse Access</h2>
          {s.warehouse_locked ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
              🔒 Locked — password required
            </span>
          ) : (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
              🔓 Open to public
            </span>
          )}
        </div>
        <p className="text-sm text-stone-600">
          When set, visitors must enter this password before they can view the public Warehouse page.
          Leave empty to keep current value. Share the password only with people you trust.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label={s.warehouse_locked ? "New warehouse password (leave empty to keep current)" : "Set warehouse password"}>
            <Input
              type="password"
              value={s.warehouse_password || ""}
              onChange={(e) => onChange("warehouse_password", e.target.value)}
              data-testid="settings-warehouse-password"
              placeholder={s.warehouse_locked ? "•••••••• (already set)" : "Choose a password"}
              autoComplete="new-password"
            />
          </Field>
        </div>
      </Card>

      <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <h2 className="font-display text-xl">{t("whatsapp_config")}</h2>
            {s.whatsapp_connected ? (
              <span
                className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200"
                data-testid="wa-status-connected"
              >
                ● Connected — Real Meta API
              </span>
            ) : (
              <span
                className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200"
                data-testid="wa-status-mock"
              >
                ● Mock mode — messages logged only
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => runReminders("en")}
              disabled={running}
              data-testid="settings-run-reminders-en"
            >
              <Send className="w-4 h-4 mr-1" /> {t("run_reminders")} (EN)
            </Button>
            <Button
              variant="outline"
              onClick={() => runReminders("tet")}
              disabled={running}
              data-testid="settings-run-reminders-tet"
            >
              <Send className="w-4 h-4 mr-1" /> {t("run_reminders")} (TET)
            </Button>
          </div>
        </div>
        <p className="text-sm text-stone-600">
          Paste your <strong>Phone Number ID</strong> and <strong>Permanent Access Token</strong> from
          <a className="text-[#1B2D5C] underline mx-1" href="https://developers.facebook.com/apps/" target="_blank" rel="noopener noreferrer">Meta for Developers → WhatsApp → API Setup</a>
          to send real messages. The token is encrypted at rest. Leave empty to keep mock mode (messages just get logged).
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Phone Number ID">
            <Input
              value={s.whatsapp_phone_id || ""}
              onChange={(e) => onChange("whatsapp_phone_id", e.target.value)}
              data-testid="settings-wa-phone-id"
              placeholder="e.g. 102938475610293"
            />
          </Field>
          <Field label={s.whatsapp_token_masked ? `Permanent Access Token (saved: ${s.whatsapp_token_masked})` : "Permanent Access Token"}>
            <Input
              type="password"
              value={s.whatsapp_token || ""}
              onChange={(e) => onChange("whatsapp_token", e.target.value)}
              data-testid="settings-wa-token"
              placeholder={s.whatsapp_token_masked ? "Leave empty to keep current token" : "EAA..."}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Template name (EN)">
            <Input
              value={s.whatsapp_template_en || ""}
              onChange={(e) => onChange("whatsapp_template_en", e.target.value)}
              data-testid="settings-wa-template-en"
            />
          </Field>
          <Field label="Template name (TET)">
            <Input
              value={s.whatsapp_template_tet || ""}
              onChange={(e) => onChange("whatsapp_template_tet", e.target.value)}
              data-testid="settings-wa-template-tet"
            />
          </Field>
          <Field label="Reminder days before due">
            <Input
              type="number"
              value={s.reminder_days_before}
              onChange={(e) => onChange("reminder_days_before", e.target.value)}
              data-testid="settings-reminder-days"
            />
          </Field>
        </div>

        {/* Test connection */}
        <div className="rounded-lg border border-stone-200 bg-stone-50 p-4 space-y-3">
          <div className="text-sm font-medium text-stone-800">Test Connection</div>
          <p className="text-xs text-stone-600">
            Send a free-form text message to verify the connection. Note: Meta only allows free-form text inside a 24-hour
            window after the recipient messages you. For a brand new conversation, you must send an approved <em>template</em> first.
          </p>
          <div className="flex flex-col md:flex-row gap-2">
            <Input
              value={testPhone}
              onChange={(e) => setTestPhone(e.target.value)}
              placeholder="+670 78372678"
              className="md:max-w-xs"
              data-testid="wa-test-phone"
            />
            <Input
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              placeholder="(optional) custom test message"
              data-testid="wa-test-body"
            />
            <Button
              onClick={sendTest}
              disabled={testing || !s.whatsapp_connected}
              className="bg-[#25D366] hover:bg-[#1EA952] text-white whitespace-nowrap"
              data-testid="wa-test-send"
              title={s.whatsapp_connected ? "" : "Save Phone Number ID + Token first"}
            >
              <Send className="w-4 h-4 mr-1" /> {testing ? "Sending…" : "Send Test"}
            </Button>
          </div>
        </div>
      </Card>

      {/* Backups & Migration */}
      <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5 text-[#1B2D5C]" />
            <h2 className="font-display text-xl">Backups &amp; Migration</h2>
            {latestBackupAt && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
                Last backup: {fmtAge(latestBackupAt)}
              </span>
            )}
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button
              onClick={generateBackup}
              disabled={generating}
              className="bg-[#1B2D5C] hover:bg-[#0F1B3A] gap-2"
              data-testid="settings-generate-backup"
            >
              <RefreshCw className={`w-4 h-4 ${generating ? "animate-spin" : ""}`} />
              {generating ? "Generating…" : "Fresh Data Backup"}
            </Button>
            <Button
              onClick={generateProject}
              disabled={generating}
              variant="outline"
              className="border-[#1B2D5C] text-[#1B2D5C] hover:bg-[#1B2D5C] hover:text-white gap-2"
              data-testid="settings-generate-project"
            >
              <Database className={`w-4 h-4 ${generating ? "animate-spin" : ""}`} />
              {generating ? "Building…" : "Build Full Deployment Zip"}
            </Button>
          </div>
        </div>
        <p className="text-sm text-stone-600">
          Generate a complete snapshot of your database, uploaded files (item photos, client documents),
          and a sanitized <code className="text-xs bg-stone-100 px-1 rounded">.env</code> template.
          Download the artifacts before migrating to your own server and keep them in a safe place
          (encrypted folder or password-protected cloud storage).
        </p>

        {schedule?.running && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 flex items-center justify-between flex-wrap gap-2 text-sm" data-testid="backup-schedule-info">
            <div className="flex items-center gap-2 text-emerald-800">
              <span className="text-emerald-600">●</span>
              <span>
                <strong>Auto-backup enabled.</strong> Runs daily at <strong>02:00 UTC</strong> and keeps the
                last <strong>{schedule.retention}</strong> snapshots.
              </span>
            </div>
            {schedule.next_run_at && (
              <span className="text-emerald-700 text-xs">
                Next run: {new Date(schedule.next_run_at).toLocaleString()}
              </span>
            )}
          </div>
        )}

        {backups.length === 0 ? (
          <div className="rounded-lg border border-dashed border-stone-300 p-6 text-center text-sm text-stone-500">
            No backups yet — click <strong>Generate Fresh Backup</strong> above to create your first snapshot.
          </div>
        ) : (
          <div className="rounded-lg border border-stone-200 overflow-hidden">
            <table className="min-w-full text-sm" data-testid="backups-table">
              <thead className="bg-stone-50 text-left">
                <tr>
                  <th className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold">File</th>
                  <th className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold">Size</th>
                  <th className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold">Created</th>
                  <th className="px-3 py-2 text-right text-[10px] uppercase tracking-wider text-stone-500 font-semibold">Download</th>
                </tr>
              </thead>
              <tbody>
                {backups.map((b) => {
                  const isZip = b.name.endsWith(".zip");
                  const description = b.name.startsWith("mongodb")
                    ? "Database dump (clients, contracts, payments, items, settings, …)"
                    : b.name.startsWith("uploads")
                    ? "Uploaded photos & client documents (with MANIFEST.json)"
                    : b.name === "FatinPenhores_Full_Project_Backup.zip"
                    ? "🎁 COMPLETE deployment package — backend + frontend + MongoDB dump + .env templates + DEPLOYMENT.md"
                    : b.name === "env-template.txt"
                    ? "Production .env template — placeholders only"
                    : b.name === "collections.txt"
                    ? "List of all collections with document counts"
                    : b.name === "README.md"
                    ? "Restore instructions for your server"
                    : "";
                  return (
                    <tr key={b.name} className="border-t border-stone-100 hover:bg-stone-50/50" data-testid={`backup-row-${b.name}`}>
                      <td className="px-3 py-3">
                        <div className="font-medium text-[#1B2D5C] flex items-center gap-2">
                          {isZip ? "📦" : b.name.endsWith(".md") ? "📖" : "📄"} {b.name}
                        </div>
                        {description && (
                          <div className="text-xs text-stone-500 mt-0.5">{description}</div>
                        )}
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap text-stone-700">{fmtSize(b.size)}</td>
                      <td className="px-3 py-3 whitespace-nowrap text-stone-500">{fmtAge(b.modified)}</td>
                      <td className="px-3 py-3 text-right">
                        <a
                          href={pdfUrl(`/admin/backups/${encodeURIComponent(b.name)}`)}
                          data-testid={`backup-download-${b.name}`}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-[#1B2D5C] text-white text-xs font-semibold hover:bg-[#0F1B3A] transition-colors whitespace-nowrap"
                        >
                          <Download className="w-3.5 h-3.5" /> Download
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="text-xs uppercase tracking-wider font-semibold text-amber-800 mb-1">⚠️ Security reminder</div>
          <p className="text-xs text-amber-800">
            The MongoDB dump contains every client&apos;s personal data (BI/passport numbers, phone, address).
            Treat these files as <strong>confidential</strong> — store them encrypted, never commit to GitHub.
          </p>
        </div>
      </Card>

      <div className="flex justify-end">
        <Button
          onClick={save}
          disabled={saving}
          className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
          data-testid="settings-save"
        >
          <Save className="w-4 h-4 mr-2" /> {saving ? "…" : t("save")}
        </Button>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs uppercase tracking-wider text-stone-500">{label}</Label>
      {children}
    </div>
  );
}
