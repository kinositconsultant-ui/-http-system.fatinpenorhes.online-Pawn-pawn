import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Warehouse,
  Building2,
  ChevronDown,
  ChevronRight,
  Users as UsersIcon,
  Search,
  ArrowRightLeft,
} from "lucide-react";
import { toast } from "sonner";

const fmtUSD = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(n || 0));

export default function StaffAssignments() {
  const { t } = useLang();
  const [data, setData] = useState({ warehouse: [], office: [], staff: [] });
  const [expandedGroup, setExpandedGroup] = useState({}); // {group-userId: true}
  const [search, setSearch] = useState("");
  const [reassign, setReassign] = useState(null); // {item, group}
  const [reassignUser, setReassignUser] = useState("");

  const load = async () => {
    const { data: r } = await api.get("/staff/assignments");
    setData(r);
  };

  useEffect(() => {
    load();
  }, []);

  const staffByType = useMemo(() => {
    return {
      warehouse: data.staff.filter((s) => s.staff_type === "warehouse"),
      office: data.staff.filter((s) => s.staff_type === "office"),
    };
  }, [data.staff]);

  const filter = (buckets) => {
    if (!search.trim()) return buckets;
    const q = search.toLowerCase();
    return buckets.map((b) => ({
      ...b,
      items: b.items.filter(
        (it) =>
          (it.name || "").toLowerCase().includes(q) ||
          (it.brand || "").toLowerCase().includes(q) ||
          (it.plate || "").toLowerCase().includes(q) ||
          (it.serial || "").toLowerCase().includes(q)
      ),
    }));
  };

  const toggle = (group, userId) => {
    const k = `${group}-${userId ?? "unassigned"}`;
    setExpandedGroup((e) => ({ ...e, [k]: !e[k] }));
  };

  const openReassign = (item, group) => {
    setReassign({ item, group });
    setReassignUser("");
  };

  const doReassign = async () => {
    if (!reassign || !reassignUser) {
      toast.error("Choose a staff member");
      return;
    }
    try {
      await api.patch(`/items/${reassign.item.kind}/${reassign.item.id}/staff`, {
        responsible_staff: reassignUser,
      });
      toast.success("Item reassigned");
      setReassign(null);
      setReassignUser("");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Reassign failed");
    }
  };

  const totals = useMemo(() => {
    const compute = (buckets) => {
      const assigned = buckets.filter((b) => b.user_id);
      return {
        staff: assigned.length,
        items: assigned.reduce((s, b) => s + b.items.length, 0),
        value: assigned.reduce((s, b) => s + b.total_market_value, 0),
        unassigned: buckets
          .filter((b) => !b.user_id)
          .reduce((s, b) => s + b.items.length, 0),
      };
    };
    return { warehouse: compute(data.warehouse), office: compute(data.office) };
  }, [data]);

  const wh = filter(data.warehouse);
  const of = filter(data.office);

  return (
    <div className="space-y-6" data-testid="staff-assignments-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">Operations</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">
            Staff Responsibility
          </h1>
          <p className="text-sm text-stone-600 mt-1 max-w-2xl">
            Track which warehouse or office staff member is currently responsible
            for each pawned item. Warehouse staff hold vehicles and heavy equipment;
            office staff hold electronics. Click any item to reassign it.
          </p>
        </div>
        <div className="relative">
          <Search className="absolute left-2 top-2.5 w-4 h-4 text-stone-400" />
          <Input
            className="pl-8 w-64"
            placeholder="Search plate, brand, serial…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid="staff-search"
          />
        </div>
      </header>

      {/* Summary strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryTile
          Icon={Warehouse}
          label="Warehouse staff"
          value={totals.warehouse.staff}
          tone="text-[#1B2D5C]"
          bg="bg-[#1B2D5C]/[0.06] border-[#1B2D5C]/25"
          testid="tile-warehouse-staff"
        />
        <SummaryTile
          label="Warehouse items assigned"
          value={`${totals.warehouse.items} · ${fmtUSD(totals.warehouse.value)}`}
          hint={`${totals.warehouse.unassigned} unassigned`}
          tone="text-stone-800"
          bg="bg-stone-50 border-stone-300"
          testid="tile-warehouse-items"
        />
        <SummaryTile
          Icon={Building2}
          label="Office staff"
          value={totals.office.staff}
          tone="text-emerald-800"
          bg="bg-emerald-50 border-emerald-200"
          testid="tile-office-staff"
        />
        <SummaryTile
          label="Office items assigned"
          value={`${totals.office.items} · ${fmtUSD(totals.office.value)}`}
          hint={`${totals.office.unassigned} unassigned`}
          tone="text-stone-800"
          bg="bg-stone-50 border-stone-300"
          testid="tile-office-items"
        />
      </div>

      <Section
        title="Warehouse Staff · Vehicles & Heavy Equipment"
        Icon={Warehouse}
        accent="text-[#1B2D5C]"
        buckets={wh}
        expandedGroup={expandedGroup}
        toggle={(uid) => toggle("warehouse", uid)}
        group="warehouse"
        openReassign={openReassign}
        emptyMsg="No warehouse staff yet — assign staff_type=warehouse under Users."
      />

      <Section
        title="Office Staff · Electronics"
        Icon={Building2}
        accent="text-emerald-800"
        buckets={of}
        expandedGroup={expandedGroup}
        toggle={(uid) => toggle("office", uid)}
        group="office"
        openReassign={openReassign}
        emptyMsg="No office staff yet — assign staff_type=office under Users."
      />

      {/* Reassign dialog */}
      <Dialog open={!!reassign} onOpenChange={(o) => !o && setReassign(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Reassign item</DialogTitle>
          </DialogHeader>
          {reassign && (
            <div className="space-y-3">
              <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm space-y-1">
                <div>
                  <span className="text-stone-500">Item:</span>{" "}
                  <span className="font-medium">
                    {reassign.item.name || `${reassign.item.brand} ${reassign.item.model}`}
                  </span>
                </div>
                {reassign.item.plate && (
                  <div>
                    <span className="text-stone-500">Plate:</span>{" "}
                    <span className="font-mono">{reassign.item.plate}</span>
                  </div>
                )}
                <div>
                  <span className="text-stone-500">Group:</span> {reassign.group}
                </div>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  New responsible staff
                </Label>
                <Select value={reassignUser} onValueChange={setReassignUser}>
                  <SelectTrigger data-testid="reassign-user">
                    <SelectValue placeholder="Choose staff" />
                  </SelectTrigger>
                  <SelectContent>
                    {staffByType[reassign.group].length === 0 && (
                      <SelectItem value="__none__" disabled>
                        No {reassign.group} staff configured
                      </SelectItem>
                    )}
                    {staffByType[reassign.group].map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name} · {s.email}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-[11px] text-stone-500 mt-1">
                  Only users with staff_type = {reassign.group} appear here. Add or
                  edit staff under the Users page.
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setReassign(null)}>
              Cancel
            </Button>
            <Button
              className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
              onClick={doReassign}
              data-testid="reassign-save"
            >
              <ArrowRightLeft className="w-4 h-4 mr-1" /> Reassign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SummaryTile({ Icon, label, value, hint, tone, bg, testid }) {
  return (
    <div className={`rounded-lg border ${bg} p-3 md:p-4`} data-testid={testid}>
      <div className="flex items-center gap-2">
        {Icon && <Icon className={`w-4 h-4 ${tone}`} />}
        <span className="text-[11px] uppercase tracking-wide text-stone-500">
          {label}
        </span>
      </div>
      <div className={`font-display text-xl md:text-2xl font-semibold mt-1 ${tone}`}>
        {value}
      </div>
      {hint && <div className="text-[11px] text-stone-500 mt-0.5">{hint}</div>}
    </div>
  );
}

function Section({
  title,
  Icon,
  accent,
  buckets,
  expandedGroup,
  toggle,
  group,
  openReassign,
  emptyMsg,
}) {
  return (
    <Card className="border border-stone-200 shadow-none rounded-lg bg-white overflow-hidden">
      <div className="p-4 md:p-5 border-b border-stone-200 flex items-center gap-2">
        <Icon className={`w-5 h-5 ${accent}`} />
        <h2 className="font-display text-lg">{title}</h2>
        <span className="ml-auto text-xs text-stone-500">
          {buckets.length} bucket{buckets.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="divide-y divide-stone-100">
        {buckets.length === 0 && (
          <div className="p-6 text-center text-stone-400 text-sm">{emptyMsg}</div>
        )}
        {buckets.map((b) => {
          const k = `${group}-${b.user_id ?? "unassigned"}`;
          const open = !!expandedGroup[k];
          const isUnassigned = !b.user_id;
          return (
            <div key={k} data-testid={`bucket-${group}-${b.user_id ?? "unassigned"}`}>
              <button
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-stone-50 text-left"
                onClick={() => toggle(b.user_id)}
              >
                <div className="flex items-center gap-3">
                  {open ? (
                    <ChevronDown className="w-4 h-4 text-stone-500" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-stone-500" />
                  )}
                  <div>
                    <div className="font-medium text-sm">
                      {b.name || "Unassigned"}
                      {isUnassigned && (
                        <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                          needs owner
                        </span>
                      )}
                    </div>
                    {b.email && (
                      <div className="text-[11px] text-stone-500">{b.email}</div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <div className="text-right">
                    <div className="text-stone-500">Items</div>
                    <div className="font-semibold">{b.items.length}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-stone-500">Total value</div>
                    <div className="font-semibold tabular-nums">
                      {fmtUSD(b.total_market_value)}
                    </div>
                  </div>
                </div>
              </button>

              {open && (
                <div className="px-4 pb-4 overflow-x-auto">
                  <table className="min-w-full text-xs">
                    <thead className="bg-stone-50 text-left">
                      <tr>
                        <Th>Name</Th>
                        <Th>Brand · Model</Th>
                        <Th>Plate / Serial</Th>
                        <Th>Fuel</Th>
                        <Th right>Mileage</Th>
                        <Th right>Market $</Th>
                        <Th>Location</Th>
                        <Th>Status</Th>
                        <Th right>Actions</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {b.items.length === 0 && (
                        <tr>
                          <td colSpan={9} className="text-center py-4 text-stone-400">
                            No items assigned yet.
                          </td>
                        </tr>
                      )}
                      {b.items.map((it) => (
                        <tr
                          key={it.id}
                          className="border-t border-stone-100 hover:bg-stone-50/50"
                          data-testid={`assigned-item-${it.id}`}
                        >
                          <Td>{it.name || "—"}</Td>
                          <Td>
                            {it.brand} · {it.model}
                          </Td>
                          <Td>
                            <span className="font-mono text-[11px]">
                              {it.plate || it.serial || "—"}
                            </span>
                          </Td>
                          <Td>{it.fuel_type || "—"}</Td>
                          <Td right>
                            {it.mileage_km != null
                              ? `${it.mileage_km.toLocaleString()} km`
                              : "—"}
                          </Td>
                          <Td right>{fmtUSD(it.market_value)}</Td>
                          <Td>{it.location || "—"}</Td>
                          <Td>
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded-full bg-stone-100 border border-stone-200 text-[10px]">
                              {it.status || "in_stock"}
                            </span>
                          </Td>
                          <Td right>
                            <button
                              className="p-1 rounded-md hover:bg-stone-100 text-stone-700"
                              onClick={() => openReassign(it, group)}
                              title="Reassign"
                              data-testid={`reassign-${it.id}`}
                            >
                              <ArrowRightLeft className="w-4 h-4" />
                            </button>
                          </Td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function Th({ children, right }) {
  return (
    <th
      className={`px-2 py-1.5 text-[10px] uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap ${
        right ? "text-right" : ""
      }`}
    >
      {children}
    </th>
  );
}

function Td({ children, right }) {
  return (
    <td
      className={`px-2 py-1.5 whitespace-nowrap ${right ? "text-right" : ""}`}
    >
      {children}
    </td>
  );
}
