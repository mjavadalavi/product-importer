export function formatPriceToman(n: number | null): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  try {
    return n.toLocaleString("fa-IR") + " تومان";
  } catch {
    return String(n) + " تومان";
  }
}

export function uid(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
}

export function formatDateFa(isoString: string): string {
  try {
    return new Date(isoString).toLocaleString("fa-IR", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return isoString;
  }
}

export function signedAmountFa(
  amount: number,
  generalType: "WITHDRAW" | "DEPOSIT",
): string {
  const sign = generalType === "WITHDRAW" ? "−" : "+";
  const abs = Math.abs(amount);
  let formatted: string;
  try {
    formatted = new Intl.NumberFormat("fa-IR").format(abs);
  } catch {
    formatted = String(abs);
  }
  return `${sign}${formatted}`;
}

export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") {
        resolve(result);
      } else {
        reject(new Error("Failed to read file as data URL"));
      }
    };
    reader.onerror = () => reject(reader.error ?? new Error("FileReader error"));
    reader.readAsDataURL(file);
  });
}
