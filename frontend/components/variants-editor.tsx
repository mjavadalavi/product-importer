"use client";

import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * The backend stores variants as `list[dict[str, Any]]` so the shape is
 * intentionally loose. We support the common subset of keys used elsewhere in
 * this codebase (sku / size / color / price / stock).
 */
export type ProductVariant = {
  sku?: string | null;
  size?: string | null;
  color?: string | null;
  price?: number | null;
  stock?: number | null;
  [key: string]: unknown;
};

type EditableVariantRow = {
  sku: string;
  size: string;
  color: string;
  price: string;
  stock: string;
  /** Preserves any backend-specific keys that we don't render. */
  extra: Record<string, unknown>;
};

function readString(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  return "";
}

function fromBackend(
  raw: Array<Record<string, unknown>> | null | undefined,
): EditableVariantRow[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((r) => {
    const rec = (r ?? {}) as Record<string, unknown>;
    const { sku, size, color, price, stock, ...extra } = rec;
    return {
      sku: readString(sku),
      size: readString(size),
      color: readString(color),
      price: readString(price),
      stock: readString(stock),
      extra,
    };
  });
}

function toBackend(rows: EditableVariantRow[]): Array<Record<string, unknown>> {
  return rows.map((r) => {
    const out: Record<string, unknown> = { ...r.extra };
    if (r.sku.trim() !== "") out.sku = r.sku.trim();
    if (r.size.trim() !== "") out.size = r.size.trim();
    if (r.color.trim() !== "") out.color = r.color.trim();
    if (r.price.trim() !== "") {
      const n = Number(r.price);
      if (Number.isFinite(n)) out.price = n;
    }
    if (r.stock.trim() !== "") {
      const n = Number(r.stock);
      if (Number.isFinite(n)) out.stock = n;
    }
    return out;
  });
}

function rowsEqual(
  a: Array<Record<string, unknown>>,
  b: Array<Record<string, unknown>>,
): boolean {
  // Cheap structural compare — variants are small.
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
}

export function VariantsEditor({
  value,
  onChange,
  disabled,
}: {
  value: Array<Record<string, unknown>> | null | undefined;
  onChange: (next: Array<Record<string, unknown>>) => void;
  disabled?: boolean;
}) {
  const [rows, setRows] = React.useState<EditableVariantRow[]>(() =>
    fromBackend(value),
  );

  // Sync from upstream when the product is refetched.
  // We rehydrate when the JSON-serialised backend value changes.
  const lastUpstream = React.useRef<string>(JSON.stringify(value ?? []));
  React.useEffect(() => {
    const next = JSON.stringify(value ?? []);
    if (next !== lastUpstream.current) {
      lastUpstream.current = next;
      setRows(fromBackend(value));
    }
  }, [value]);

  const commit = React.useCallback(
    (nextRows: EditableVariantRow[]) => {
      setRows(nextRows);
      const backend = toBackend(nextRows);
      const upstream = (value ?? []) as Array<Record<string, unknown>>;
      if (!rowsEqual(backend, upstream)) {
        onChange(backend);
      }
    },
    [onChange, value],
  );

  const handleField = (
    index: number,
    key: keyof Omit<EditableVariantRow, "extra">,
    fieldValue: string,
  ) => {
    const next = rows.map((r, i) =>
      i === index ? { ...r, [key]: fieldValue } : r,
    );
    commit(next);
  };

  const handleAdd = () => {
    const next: EditableVariantRow[] = [
      ...rows,
      { sku: "", size: "", color: "", price: "", stock: "", extra: {} },
    ];
    commit(next);
  };

  const handleRemove = (index: number) => {
    const next = rows.filter((_, i) => i !== index);
    commit(next);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-sm font-medium">تنوع‌ها</Label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleAdd}
          disabled={disabled}
        >
          <Plus className="h-4 w-4" />
          <span>افزودن تنوع</span>
        </Button>
      </div>

      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          این محصول هنوز تنوعی ندارد.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((row, idx) => (
            <div
              key={idx}
              className="rounded-md border border-neutral-200 bg-neutral-50/60 p-2 flex flex-col gap-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-neutral-500">
                  تنوع {idx + 1}
                </span>
                <button
                  type="button"
                  onClick={() => handleRemove(idx)}
                  disabled={disabled}
                  className="inline-flex items-center gap-1 rounded-md border border-rose-200 bg-white px-2 py-0.5 text-[11px] font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                  aria-label="حذف تنوع"
                >
                  <Trash2 className="h-3 w-3" />
                  حذف
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="flex flex-col gap-1">
                  <Label className="text-[11px] text-neutral-500">SKU</Label>
                  <Input
                    value={row.sku}
                    onChange={(e) => handleField(idx, "sku", e.target.value)}
                    disabled={disabled}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-[11px] text-neutral-500">سایز</Label>
                  <Input
                    value={row.size}
                    onChange={(e) => handleField(idx, "size", e.target.value)}
                    disabled={disabled}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-[11px] text-neutral-500">رنگ</Label>
                  <Input
                    value={row.color}
                    onChange={(e) => handleField(idx, "color", e.target.value)}
                    disabled={disabled}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-[11px] text-neutral-500">
                    قیمت (تومان)
                  </Label>
                  <Input
                    type="number"
                    inputMode="numeric"
                    min={0}
                    value={row.price}
                    onChange={(e) => handleField(idx, "price", e.target.value)}
                    disabled={disabled}
                  />
                </div>
                <div className="flex flex-col gap-1 col-span-2">
                  <Label className="text-[11px] text-neutral-500">موجودی</Label>
                  <Input
                    type="number"
                    inputMode="numeric"
                    min={0}
                    value={row.stock}
                    onChange={(e) => handleField(idx, "stock", e.target.value)}
                    disabled={disabled}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
