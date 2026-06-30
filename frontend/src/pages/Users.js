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
import { Plus, Trash2, Pencil, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const MODULE_LABELS = {
  dashboard: "Dashboard",
  clients: "Clients",
  items: "Pawn Items",
  contracts: "Contracts",
  payments: "Payments",
  auctions: "Auctions",
  reports: "Reports",
  finance: "Finance / Treasury",
  users: "Users",
  settings: "Settings",
  audit_log: "Audit Log",
};

const blank = {
  email: "",
  name: "",
  password: "",
  role: "staff",
  allowed_modules: [],
};

export default function Users() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [moduleCatalog, setModuleCatalog] = useState({ modules: [], role_defaults: {} });
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(blank);

  const load = async () => {
    const [u, c] = await Promise.all([
      api.get("/users"),
      api.get("/users/modules"),
    ]);
    setRows(u.data);
    setModuleCatalog(c.data);
  };
  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    setEditingId(null);
    setForm({
      ...blank,
      allowed_modules: moduleCatalog.role_defaults?.staff || [],
    });
    setOpen(true);
  };

  const openEdit = (u) => {
    setEditingId(u.id);
    setForm({
      email: u.email,
      name: u.name || "",
      password: "",
      role: u.role,
      allowed_modules: u.allowed_modules || moduleCatalog.role_defaults?.[u.role] || [],
    });
    setOpen(true);
  };

  const applyRolePreset = (role) => {
    const defaults = moduleCatalog.role_defaults?.[role] || [];
    setForm((f) => ({ ...f, role, allowed_modules: role === "admin" ? moduleCatalog.modules : defaults }));
  };

  const toggleModule = (m) => {
    setForm((f) => {
      const has = f.allowed_modules.includes(m);
      return {
        ...f,
        allowed_modules: has
          ? f.allowed_modules.filter((x) => x !== m)
          : [...f.allowed_modules, m],
      };
    });
  };

  const submit = async () => {
    try {
      if (editingId) {
        const payload = {
          name: form.name,
          role: form.role,
          allowed_modules: form.allowed_modules,
        };
        if (form.password) payload.password = form.password;
        await api.patch(`/users/${editingId}`, payload);
        toast.success("User updated");
      } else {
        await api.post("/users", form);
        toast.success("User created");
      }
      setOpen(false);
      setForm(blank);
      setEditingId(null);
      load();
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

  const isAdminRole = form.role === "admin";

  return (
    <div className="space-y-6" data-testid="users-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("users")}</div>
          <h1 className="font-display text-4xl font-semibold mt-1">{t("users")}</h1>
        </div>
        <Dialog
          open={open}
          onOpenChange={(o) => {
            setOpen(o);
            if (!o) {
              setForm(blank);
              setEditingId(null);
            }
          }}
        >
          <DialogTrigger asChild>
            <Button
              className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
              data-testid="user-new-btn"
              onClick={openNew}
            >
              <Plus className="w-4 h-4 mr-1" /> {t("new")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-[#1B2D5C]" />
                {editingId ? `${t("edit")} — ${t("users")}` : `${t("new")} — ${t("users")}`}
              </DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                  disabled={!!editingId}
                  data-testid="user-email"
                />
              </Field>
              <Field label={editingId ? `${t("password")} (leave blank to keep)` : t("password")}>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  data-testid="user-password"
                />
              </Field>
              <Field label="Role">
                <Select value={form.role} onValueChange={applyRolePreset}>
                  <SelectTrigger data-testid="user-role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">admin (full access, locked)</SelectItem>
                    <SelectItem value="staff">staff</SelectItem>
                    <SelectItem value="cashier">cashier</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            </div>

            <div className="mt-2 space-y-2" data-testid="module-access-section">
              <div className="flex items-center justify-between">
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  Module Access {isAdminRole && <span className="ml-2 text-amber-700 normal-case">(admin always has full access)</span>}
                </Label>
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => applyRolePreset("staff")}
                    disabled={isAdminRole}
                    className="text-[11px] px-2 py-1 rounded border border-stone-300 text-stone-700 hover:bg-stone-100 disabled:opacity-40 disabled:cursor-not-allowed"
                    data-testid="preset-staff"
                  >
                    Staff preset
                  </button>
                  <button
                    type="button"
                    onClick={() => applyRolePreset("cashier")}
                    disabled={isAdminRole}
                    className="text-[11px] px-2 py-1 rounded border border-stone-300 text-stone-700 hover:bg-stone-100 disabled:opacity-40 disabled:cursor-not-allowed"
                    data-testid="preset-cashier"
                  >
                    Cashier preset
                  </button>
                  <button
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, allowed_modules: moduleCatalog.modules }))}
                    disabled={isAdminRole}
                    className="text-[11px] px-2 py-1 rounded border border-stone-300 text-stone-700 hover:bg-stone-100 disabled:opacity-40 disabled:cursor-not-allowed"
                    data-testid="preset-all"
                  >
                    All
                  </button>
                  <button
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, allowed_modules: [] }))}
                    disabled={isAdminRole}
                    className="text-[11px] px-2 py-1 rounded border border-stone-300 text-stone-700 hover:bg-stone-100 disabled:opacity-40 disabled:cursor-not-allowed"
                    data-testid="preset-none"
                  >
                    None
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 rounded-md border border-stone-200 bg-stone-50/70 p-3">
                {moduleCatalog.modules.map((m) => {
                  const checked = isAdminRole || form.allowed_modules.includes(m);
                  return (
                    <label
                      key={m}
                      className={`flex items-center gap-2 text-sm px-2 py-1.5 rounded border ${
                        checked
                          ? "bg-white border-[#1B2D5C]/30"
                          : "bg-stone-100 border-stone-200 text-stone-500"
                      } ${isAdminRole ? "opacity-70 cursor-not-allowed" : "cursor-pointer hover:border-stone-400"}`}
                      data-testid={`module-${m}`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={isAdminRole}
                        onChange={() => toggleModule(m)}
                        className="accent-[#1B2D5C]"
                      />
                      <span className="font-medium">{MODULE_LABELS[m] || m}</span>
                    </label>
                  );
                })}
              </div>
              <p className="text-[11px] text-stone-500">
                Module access controls which sidebar items the user can see and read. Role still determines who can create/edit/delete inside each module.
              </p>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                {t("cancel")}
              </Button>
              <Button
                onClick={submit}
                className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
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
              <Th>Modules</Th>
              <Th right>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const mods = r.allowed_modules || [];
              return (
                <tr key={r.id} className="border-t border-stone-100">
                  <Td className="font-medium whitespace-nowrap">{r.name}</Td>
                  <Td className="whitespace-nowrap">{r.email}</Td>
                  <Td>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full border ${
                        r.role === "admin"
                          ? "bg-[#1B2D5C]/10 text-[#1B2D5C] border-[#1B2D5C]/20"
                          : r.role === "staff"
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : "bg-amber-50 text-amber-800 border-amber-200"
                      }`}
                    >
                      {r.role}
                    </span>
                  </Td>
                  <Td>
                    <div className="flex flex-wrap gap-1 max-w-md">
                      {r.role === "admin" ? (
                        <span className="text-xs text-stone-500 italic">All modules</span>
                      ) : mods.length === 0 ? (
                        <span className="text-xs text-stone-400 italic">No modules</span>
                      ) : (
                        mods.map((m) => (
                          <span
                            key={m}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-stone-100 text-stone-700 border border-stone-200"
                          >
                            {MODULE_LABELS[m] || m}
                          </span>
                        ))
                      )}
                    </div>
                  </Td>
                  <Td right>
                    <div className="flex justify-end gap-1.5">
                      <button
                        onClick={() => openEdit(r)}
                        data-testid={`user-edit-${r.id}`}
                        className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#C17767] text-white hover:bg-[#A96253] transition-colors"
                        title={t("edit")}
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => remove(r.id)}
                        data-testid={`user-delete-${r.id}`}
                        className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#993333] text-white hover:bg-[#7A2828] transition-colors"
                        title={t("delete")}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </Td>
                </tr>
              );
            })}
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
