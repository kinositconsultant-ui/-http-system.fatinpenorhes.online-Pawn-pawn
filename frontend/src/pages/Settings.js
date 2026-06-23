import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Card } from "../components/ui/card";
import { toast } from "sonner";
import { Save, Send } from "lucide-react";

export default function Settings() {
  const { t } = useLang();
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [testPhone, setTestPhone] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    api.get("/settings").then((r) => setS(r.data));
  }, []);

  const onChange = (k, v) => setS((cur) => ({ ...cur, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...s };
      // strip server-only flags
      delete payload.whatsapp_token_masked;
      delete payload.whatsapp_connected;
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
