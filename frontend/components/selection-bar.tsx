"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { api, type ProductListItem } from "@/lib/api";
import { formatNumberFa } from "@/lib/format";

type ApiErrorShape = {
  status?: number;
  message?: string;
  detail?: unknown;
};

type ConfirmAllResponse = {
  confirmed: Array<{ product_id: string; ok: boolean; error?: string | null }>;
  failed_count: number;
  total_charged: number;
};

interface SelectionBarProps {
  selectedIds: Set<string>;
  drafts: ProductListItem[];
  onClearSelection: () => void;
  onInsufficient?: (required: number, available: number) => void;
}

export function SelectionBar({
  selectedIds,
  drafts,
  onClearSelection,
  onInsufficient,
}: SelectionBarProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const count = selectedIds.size;
  const visible = count > 0;

  const selectedDrafts = drafts.filter((d) => selectedIds.has(d.id));
  const validSelected = selectedDrafts.filter((d) => !!d.primary_image_url);
  const invalidSelected = selectedDrafts.filter((d) => !d.primary_image_url);

  const confirmSelectedMutation = useMutation({
    mutationKey: ["confirm-selected"],
    mutationFn: () =>
      api.post<ConfirmAllResponse>("/products/confirm-all", {
        product_ids: validSelected.map((d) => d.id),
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      const okCount = res.confirmed.filter((c) => c.ok).length;
      toast({ title: `${formatNumberFa(okCount)} محصول ثبت شد` });
      if (res.failed_count > 0) {
        toast({
          title: `${formatNumberFa(res.failed_count)} محصول ثبت نشد`,
          variant: "destructive",
        });
      }
      onClearSelection();
    },
    onError: (err: unknown) => {
      const e = err as ApiErrorShape;
      if (e?.status === 402) {
        const detail = (e.detail || {}) as {
          required?: number;
          available?: number;
        };
        onInsufficient?.(detail.required ?? 0, detail.available ?? 0);
        return;
      }
      if (e?.status === 422) {
        toast({
          title: "بعضی محصول‌ها عکس ندارن — لیست رو ببین",
          variant: "destructive",
        });
        return;
      }
      toast({
        title: "خطا در ثبت",
        description: e?.message || "مشکلی پیش آمد.",
        variant: "destructive",
      });
    },
  });

  return (
    <div
      role="region"
      aria-label="نوار انتخاب"
      className={[
        "fixed bottom-16 left-0 right-0 z-30",
        "border-t border-amber-200 bg-amber-50 px-4 py-3 shadow-lg",
        "transition-all duration-[240ms] ease-out",
        visible
          ? "translate-y-0 opacity-100"
          : "translate-y-[calc(100%+5rem)] opacity-0 pointer-events-none",
      ].join(" ")}
    >
      {invalidSelected.length > 0 && (
        <p className="mb-1.5 text-[11px] text-rose-600">
          {formatNumberFa(invalidSelected.length)} انتخاب بدون عکس نادیده گرفته می‌شه
        </p>
      )}
      <div className="flex items-center gap-3">
        {/* Count chip */}
        <span className="shrink-0 rounded-full bg-amber-200 px-2.5 py-0.5 text-xs font-semibold text-amber-900 tabular-nums">
          {formatNumberFa(count)} انتخاب شده
        </span>

        {/* Cancel link */}
        <button
          type="button"
          onClick={onClearSelection}
          className="shrink-0 inline-flex items-center gap-1 text-xs text-amber-800 underline underline-offset-2 hover:text-amber-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 rounded"
          aria-label="لغو انتخاب"
        >
          <X className="h-3.5 w-3.5" />
          لغو انتخاب
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Submit button */}
        <Button
          type="button"
          size="sm"
          onClick={() => confirmSelectedMutation.mutate()}
          disabled={confirmSelectedMutation.isPending || validSelected.length === 0}
          className="shrink-0"
        >
          {confirmSelectedMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          <span>
            {validSelected.length === 0
              ? "اول عکس اضافه کن"
              : `ثبت ${formatNumberFa(validSelected.length)} محصول`}
          </span>
        </Button>
      </div>
    </div>
  );
}
