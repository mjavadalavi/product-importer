"use client";

import * as React from "react";
import { Sparkles } from "lucide-react";
import { AiBadge } from "@/components/detection-field";
import { formatNumberFa } from "@/lib/format";

type Field = { key: string; label: string };

const SCALAR_FIELDS: Field[] = [
  { key: "brand", label: "برند" },
  { key: "color", label: "رنگ" },
  { key: "material", label: "جنس" },
  { key: "condition", label: "وضعیت" },
  { key: "country_of_origin", label: "ساخت" },
  { key: "packaging", label: "بسته‌بندی" },
];

function readScalar(
  ai: Record<string, unknown>,
  key: string,
): { value: string; confidence: number } | null {
  const node = ai[key];
  if (!node || typeof node !== "object" || Array.isArray(node)) return null;
  const rec = node as Record<string, unknown>;
  const v = String(rec.value ?? "").trim();
  if (!v) return null;
  const c = typeof rec.confidence === "number" ? Math.round(rec.confidence * 100) : 0;
  return { value: v, confidence: c };
}

function readDimensions(
  ai: Record<string, unknown>,
): { length: number; width: number; height: number; confidence: number } | null {
  const dims = ai.dimensions;
  if (!dims || typeof dims !== "object") return null;
  const rec = dims as Record<string, unknown>;
  const length = Number(rec.length_cm);
  const width = Number(rec.width_cm);
  const height = Number(rec.height_cm);
  if (![length, width, height].every((n) => Number.isFinite(n) && n > 0)) {
    return null;
  }
  const conf =
    typeof rec.confidence === "number" ? Math.round(rec.confidence * 100) : 0;
  return { length, width, height, confidence: conf };
}

function readStringList(ai: Record<string, unknown>, key: string): string[] {
  const v = ai[key];
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string" && x.trim().length > 0);
}

export function DetectedAttributes({
  aiResult,
}: {
  aiResult: Record<string, unknown>;
}) {
  const scalars = SCALAR_FIELDS.map((f) => ({
    ...f,
    detected: readScalar(aiResult, f.key),
  })).filter((f) => f.detected);

  const dims = readDimensions(aiResult);
  const keywords = readStringList(aiResult, "keywords");
  const tags = readStringList(aiResult, "tags");

  const isEmpty = scalars.length === 0 && !dims && keywords.length === 0 && tags.length === 0;

  if (isEmpty) {
    return (
      <div className="rounded-md border border-dashed border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-500 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-neutral-400" />
        AI ویژگی‌های قابل تشخیصی پیدا نکرد.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-neutral-200 bg-white p-3 flex flex-col gap-3">
      <div className="flex items-center gap-2 text-sm font-medium text-neutral-700">
        <Sparkles className="h-4 w-4 text-emerald-500" />
        ویژگی‌های تشخیص داده‌شده
      </div>

      {scalars.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
          {scalars.map(({ key, label, detected }) => (
            <div key={key} className="flex flex-col gap-0.5">
              <dt className="flex items-center gap-1 text-neutral-500">
                <span>{label}</span>
                <AiBadge confidence={detected!.confidence} />
              </dt>
              <dd className="text-neutral-900 font-medium">{detected!.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {dims && (
        <div className="flex flex-col gap-1 text-xs">
          <div className="flex items-center gap-1 text-neutral-500">
            <span>ابعاد بسته‌بندی</span>
            <AiBadge confidence={dims.confidence} />
          </div>
          <div className="text-neutral-900 font-medium tabular-nums">
            {formatNumberFa(dims.length)} × {formatNumberFa(dims.width)} ×{" "}
            {formatNumberFa(dims.height)} سانتی‌متر
          </div>
        </div>
      )}

      {keywords.length > 0 && (
        <div className="flex flex-col gap-1 text-xs">
          <div className="text-neutral-500">کلمات کلیدی</div>
          <div className="flex flex-wrap gap-1">
            {keywords.map((k) => (
              <span
                key={k}
                className="inline-flex items-center rounded-md bg-neutral-100 px-2 py-0.5 text-neutral-700"
              >
                {k}
              </span>
            ))}
          </div>
        </div>
      )}

      {tags.length > 0 && (
        <div className="flex flex-col gap-1 text-xs">
          <div className="text-neutral-500">برچسب‌ها</div>
          <div className="flex flex-wrap gap-1">
            {tags.map((t) => (
              <span
                key={t}
                className="inline-flex items-center rounded-md bg-emerald-50 text-emerald-700 px-2 py-0.5"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
