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
  DialogFooter,
} from "../components/ui/dialog";
import { toast } from "sonner";

export default function Auctions() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState(null);
  const [form, setForm] = useState({ sold_price: "", buyer_name: "", notes: "" });

  const load = () => api.get("/auctions").then((r) => setRows(r.data));
  useEffect(() => {
    load();
  }, []);

  const openSold = (a) => {
    setCurrent(a);
    setForm({ sold_price: a.starting_price || "", buyer_name: "", notes: "" });
    setOpen(true);
  };

  const submitSold = async () => {
    try {
      await api.post(`/auctions/${current.id}/sold`, {
        sold_price: Number(form.sold_price),
        buyer_name: form.buyer_name,
        notes: form.notes,
      });
      toast.success("Marked as sold");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="space-y-6" data-testid="auctions-root">
      <header>
        <div className="text-eyebrow">{t("auctions")}</div>
        <h1 className="font-display text-4xl font-semibold mt-1">{t("auctions")}</h1>
        <p className="text-stone-600 text-sm mt-1">
          Overdue items are moved here from contracts. Mark them as sold to close the loop.
        </p>
      </header>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="auctions-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>{t("contract_number")}</Th>
              <Th>{t("item")}</Th>
              <Th right>{t("starting_price")}</Th>
              <Th right>{t("sold_price")}</Th>
              <Th>{t("buyer_name")}</Th>
              <Th>{t("status")}</Th>
              <Th right>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100">
                <Td className="font-medium">{r.contract_number}</Td>
                <Td>
                  <span className="text-xs uppercase tracking-wider text-stone-500 mr-1">
                    {r.item_type}
                  </span>
                </Td>
                <Td right>${Number(r.starting_price || 0).toLocaleString()}</Td>
                <Td right>{r.sold_price ? `$${Number(r.sold_price).toLocaleString()}` : "—"}</Td>
                <Td>{r.buyer_name || "—"}</Td>
                <Td>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full border ${
                      r.status === "listed"
                        ? "bg-orange-50 text-orange-800 border-orange-200"
                        : "bg-emerald-50 text-emerald-800 border-emerald-200"
                    }`}
                  >
                    {r.status}
                  </span>
                </Td>
                <Td right>
                  {r.status === "listed" && (
                    <Button
                      size="sm"
                      onClick={() => openSold(r)}
                      data-testid={`auction-sold-${r.id}`}
                      className="bg-[#C17767] hover:bg-[#A96253]"
                    >
                      {t("mark_sold")}
                    </Button>
                  )}
                </Td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan="7" className="p-8 text-center text-stone-500">
                  No auctions
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("mark_sold")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-stone-500">
                {t("sold_price")}
              </Label>
              <Input
                type="number"
                step="0.01"
                value={form.sold_price}
                onChange={(e) => setForm({ ...form, sold_price: e.target.value })}
                data-testid="auction-sold-price"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-stone-500">
                {t("buyer_name")}
              </Label>
              <Input
                value={form.buyer_name}
                onChange={(e) => setForm({ ...form, buyer_name: e.target.value })}
                data-testid="auction-buyer-name"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t("cancel")}
            </Button>
            <Button
              onClick={submitSold}
              className="bg-[#C17767] hover:bg-[#A96253]"
              data-testid="auction-sold-confirm"
            >
              {t("save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
