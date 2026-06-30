// Shortened display helpers for document numbers
// Keeps tables compact: CTR-2026-0042 -> CT-2026-42, RCP-2026-0007 -> RC-2026-7, INV-2026-0015 -> INV-2026-15

export const shortContract = (num) => {
  if (!num) return "—";
  const m = String(num).match(/^CTR-(\d{4})-0*(\d+)$/);
  return m ? `CT-${m[1]}-${m[2]}` : num;
};

export const shortReceipt = (num) => {
  if (!num) return "—";
  const m = String(num).match(/^RCP-(\d{4})-0*(\d+)$/);
  return m ? `RC-${m[1]}-${m[2]}` : num;
};

export const shortInvoice = (num) => {
  if (!num) return "—";
  const m = String(num).match(/^INV-(\d{4})-0*(\d+)$/);
  return m ? `INV-${m[1]}-${m[2]}` : num;
};
