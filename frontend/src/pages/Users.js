import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

const blank = { email: "", name: "", password: "", role: "staff" };

export default function Users() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);

  const load = () => api.get("/users").then((r) => setRows(r.data));
  useEffect(() => {
    load();
  }, []);

  const submit = async () => {
    try {
      await api.post("/users", form);
      setOpen(false);
      setForm(blank);
      load();
      toast.success("User created");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete user?")) return;
    try {
      await api.delete(`/users/${id}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="space-y-6" data-testid="users-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("users")}</div>
          <h1 className="font-display text-4xl font-semibold mt-1">{t("users")}</h1>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-[#2F4F4F] hover:bg-[#1D3333]" data-testid="user-new-btn">
              <Plus className="w-4 h-4 mr-1" /> {t("new")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{t("new")} — {t("users")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <Field label="Name">
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  data-testid="user-name"
                />
              </Field>
              <Field label={t("email")}>
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  data-testid="user-email"
                />
              </Field>
              <Field label={t("password")}>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  data-testid="user-password"
                />
              </Field>
              <Field label="Role">
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="user-role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">admin</SelectItem>
                    <SelectItem value="staff">staff</SelectItem>
                    <SelectItem value="cashier">cashier</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                {t("cancel")}
              </Button>
              <Button
                onClick={submit}
                className="bg-[#2F4F4F] hover:bg-[#1D3333]"
                data-testid="user-save"
              >
                {t("save")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </header>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="users-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>Name</Th>
              <Th>{t("email")}</Th>
              <Th>Role</Th>
              <Th right>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100">
                <Td className="font-medium">{r.name}</Td>
                <Td>{r.email}</Td>
                <Td>{r.role}</Td>
                <Td right>
                  <button
                    onClick={() => remove(r.id)}
                    data-testid={`user-delete-${r.id}`}
                    className="p-1 hover:text-[#993333]"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
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
function Th({ children, right }) {
  return (
    <th
      className={`px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold ${
        right ? "text-right" : ""
      }`}
    >
      {children}
    </th>
  );
}
function Td({ children, right, className = "" }) {
  return <td className={`px-4 py-3 ${right ? "text-right" : ""} ${className}`}>{children}</td>;
}
