"use client";

import * as React from "react";
import { formatNumberFa } from "@/lib/format";

export type StatusFilter =
  | "ALL"
  | "DRAFT"
  | "PROCESSING"
  | "READY"
  | "SUBMITTED"
  | "FAILED";

interface ChipDef {
  value: StatusFilter;
  label: string;
  count: number;
  /** Only render this chip when count > 0 */
  hideWhenEmpty?: boolean;
  activeClass: string;
}

interface StatusFilterChipsProps {
  counts: {
    all: number;
    draft: number;
    processing: number;
    ready: number;
    submitted: number;
    failed: number;
  };
  active: StatusFilter;
  onChange: (value: StatusFilter) => void;
}

export function StatusFilterChips({
  counts,
  active,
  onChange,
}: StatusFilterChipsProps) {
  const chips: ChipDef[] = [
    {
      value: "ALL",
      label: "همه",
      count: counts.all,
      activeClass: "bg-primary text-primary-foreground border-primary",
    },
    {
      value: "DRAFT",
      label: "پیش‌نویس",
      count: counts.draft,
      activeClass: "bg-amber-500 text-white border-amber-500",
    },
    {
      value: "PROCESSING",
      label: "در حال پردازش",
      count: counts.processing,
      activeClass: "bg-teal-600 text-white border-teal-600",
    },
    {
      value: "READY",
      label: "نیاز به تکمیل",
      count: counts.ready,
      hideWhenEmpty: true,
      activeClass: "bg-amber-600 text-white border-amber-600",
    },
    {
      value: "SUBMITTED",
      label: "ثبت شده",
      count: counts.submitted,
      activeClass: "bg-emerald-600 text-white border-emerald-600",
    },
    {
      value: "FAILED",
      label: "ناموفق",
      count: counts.failed,
      hideWhenEmpty: true,
      activeClass: "bg-rose-600 text-white border-rose-600",
    },
  ];

  const visibleChips = chips.filter(
    (c) => !(c.hideWhenEmpty && c.count === 0),
  );

  return (
    <div
      className="overflow-x-auto"
      role="group"
      aria-label="فیلتر وضعیت محصولات"
    >
      {/* Scrollable inner row — RTL so chips go right to left naturally */}
      <div className="flex gap-2 px-4 py-3 w-max min-w-full">
        {visibleChips.map((chip) => {
          const isActive = active === chip.value;
          return (
            <button
              key={chip.value}
              type="button"
              onClick={() => onChange(chip.value)}
              aria-pressed={isActive}
              className={[
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium whitespace-nowrap",
                "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive
                  ? chip.activeClass
                  : "border-neutral-200 bg-background text-neutral-700 hover:bg-neutral-100",
              ].join(" ")}
            >
              <span>{chip.label}</span>
              <span
                className={[
                  "tabular-nums rounded-full px-1.5 py-px text-[10px] font-semibold",
                  isActive
                    ? "bg-white/20 text-inherit"
                    : "bg-neutral-100 text-neutral-500",
                ].join(" ")}
              >
                {formatNumberFa(chip.count)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
