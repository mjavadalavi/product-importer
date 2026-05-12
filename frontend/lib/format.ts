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

const PERSIAN_DIGIT_MAP: Record<string, string> = {
  "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
  "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
  "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
  "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
};

export function toLatinDigits(input: string): string {
  return input.replace(/[۰-۹٠-٩]/g, (d) => PERSIAN_DIGIT_MAP[d] ?? d);
}

export function digitsOnly(input: string): string {
  return toLatinDigits(input).replace(/[^0-9]/g, "");
}

export function formatNumberFa(n: number | string | null | undefined): string {
  if (n === null || n === undefined || n === "") return "";
  const num = typeof n === "number" ? n : Number(toLatinDigits(String(n)));
  if (!Number.isFinite(num)) return "";
  try {
    return new Intl.NumberFormat("fa-IR").format(num);
  } catch {
    return String(num);
  }
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
