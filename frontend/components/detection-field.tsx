"use client";

import * as React from "react";
import { Sparkles, AlertCircle } from "lucide-react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export function aiFieldConfidence(
  aiResult: Record<string, unknown> | null | undefined,
  key: string,
): number | null {
  if (!aiResult || typeof aiResult !== "object") return null;
  const node = (aiResult as Record<string, unknown>)[key];
  if (node && typeof node === "object" && !Array.isArray(node)) {
    const conf = (node as Record<string, unknown>).confidence;
    if (typeof conf === "number" && conf > 0) return Math.round(conf * 100);
  }
  // Special-case category_confidence sits at top level
  if (key === "category") {
    const top = (aiResult as Record<string, unknown>).category;
    if (top && typeof top === "object") {
      const c = (top as Record<string, unknown>).confidence;
      if (typeof c === "number" && c > 0) return Math.round(c * 100);
    }
  }
  return null;
}

/**
 * Read a scalar AI-suggested value from `ai_result`. Returns the string form
 * of the detected value, or `null` if the AI didn't detect anything for this key.
 *
 * Looks at the conventional shape `{ key: { value, confidence } }`. As a
 * fallback, accepts raw scalar `key: <value>` entries too.
 */
export function aiFieldValue(
  aiResult: Record<string, unknown> | null | undefined,
  key: string,
): string | null {
  if (!aiResult || typeof aiResult !== "object") return null;
  const node = (aiResult as Record<string, unknown>)[key];
  if (node == null) return null;
  if (typeof node === "object" && !Array.isArray(node)) {
    const rec = node as Record<string, unknown>;
    const v = rec.value;
    if (v == null) return null;
    const s = String(v).trim();
    return s === "" ? null : s;
  }
  if (typeof node === "string") {
    const s = node.trim();
    return s === "" ? null : s;
  }
  if (typeof node === "number") {
    return String(node);
  }
  return null;
}

export function fieldErrorMessages(
  errors: unknown,
  key: string,
): string[] {
  if (!errors || typeof errors !== "object") return [];
  const fieldErrors = (errors as Record<string, unknown>).field_errors;
  if (!fieldErrors || typeof fieldErrors !== "object") return [];
  const arr = (fieldErrors as Record<string, unknown>)[key];
  if (!Array.isArray(arr)) return [];
  return arr.filter((m): m is string => typeof m === "string");
}

export function AiBadge({ confidence }: { confidence: number }) {
  const tone =
    confidence >= 70
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : confidence >= 45
        ? "bg-amber-50 text-amber-700 border-amber-200"
        : "bg-rose-50 text-rose-700 border-rose-200";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium leading-4",
        tone,
      )}
      title={`AI با اطمینان ${confidence}٪ تشخیص داد`}
    >
      <Sparkles className="h-3 w-3" />
      AI {confidence}٪
    </span>
  );
}

export function MissingBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-rose-200 bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium leading-4 text-rose-700">
      <AlertCircle className="h-3 w-3" />
      نیاز به تکمیل
    </span>
  );
}

export function DetectionField({
  id,
  label,
  errors = [],
  aiConfidence = null,
  aiSuggestion = null,
  currentValue,
  onApplyAi,
  required = false,
  hint,
  children,
}: {
  id?: string;
  label: string;
  errors?: string[];
  aiConfidence?: number | null;
  /** AI-suggested value (string) to surface inline. Hides itself when null. */
  aiSuggestion?: string | null;
  /** Current form value — used to hide the apply hint when already applied. */
  currentValue?: string;
  /** Called when the user clicks the "اعمال" button on the AI hint. */
  onApplyAi?: (value: string) => void;
  required?: boolean;
  hint?: React.ReactNode;
  children: React.ReactNode;
}) {
  const hasError = errors.length > 0;
  const trimmedSuggestion = aiSuggestion?.trim() ?? "";
  const trimmedCurrent = (currentValue ?? "").trim();
  const showAiSuggestion =
    trimmedSuggestion !== "" && trimmedSuggestion !== trimmedCurrent;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5 flex-wrap">
        {id ? <Label htmlFor={id}>{label}</Label> : <Label>{label}</Label>}
        {required ? (
          <span className="text-rose-600 leading-none" aria-hidden="true">
            *
          </span>
        ) : null}
        {hasError ? <MissingBadge /> : null}
        {aiConfidence != null ? <AiBadge confidence={aiConfidence} /> : null}
      </div>
      <div
        className={cn(
          hasError && "[&_input]:border-rose-300 [&_textarea]:border-rose-300 [&_input]:focus-visible:ring-rose-200 [&_textarea]:focus-visible:ring-rose-200",
        )}
      >
        {children}
      </div>
      {showAiSuggestion ? (
        <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] text-emerald-800">
          <Sparkles className="h-3 w-3 shrink-0" />
          <span className="min-w-0 flex-1 truncate" title={trimmedSuggestion}>
            <span className="text-emerald-700/80">AI:</span>{" "}
            <span className="font-medium">{trimmedSuggestion}</span>
          </span>
          {onApplyAi ? (
            <button
              type="button"
              onClick={() => onApplyAi(trimmedSuggestion)}
              className="shrink-0 rounded-md border border-emerald-300 bg-white px-2 py-0.5 text-[11px] font-medium text-emerald-800 hover:bg-emerald-100 focus:outline-none focus:ring-2 focus:ring-emerald-300"
            >
              اعمال
            </button>
          ) : null}
        </div>
      ) : null}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      {hasError ? (
        <ul className="text-xs text-rose-600 leading-5">
          {errors.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
