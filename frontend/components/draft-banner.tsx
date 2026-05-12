"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, ImagePlus, Loader2 } from "lucide-react";
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

export function DraftBanner({
  drafts,
  onOpenBulkPicker,
  onInsufficient,
}: {
  drafts: ProductListItem[];
  onOpenBulkPicker: () => void;
  onInsufficient?: (required: number, available: number) => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const total = drafts.length;
  const submittableDrafts = drafts.filter((d) => !!d.primary_image_url);
  const imagelessDrafts = drafts.filter((d) => !d.primary_image_url);
  const withoutImage = imagelessDrafts.length;

  const confirmAllMutation = useMutation({
    mutationKey: ["confirm-all"],
    mutationFn: () =>
      api.post<ConfirmAllResponse>(`/products/confirm-all`, {
        product_ids: submittableDrafts.map((d) => d.id),
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      const okCount = res.confirmed.filter((c) => c.ok).length;
      toast({
        title: `${formatNumberFa(okCount)} محصول ثبت شد`,
      });
      if (res.failed_count > 0) {
        toast({
          title: `${formatNumberFa(res.failed_count)} محصول ثبت نشد`,
          variant: "destructive",
        });
      }
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
        title: "خطا در ثبت دسته‌ای",
        description: e?.message || "مشکلی پیش آمد.",
        variant: "destructive",
      });
    },
  });

  if (total === 0) return null;

  return (
    <div className="mx-3 mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex flex-col gap-1 text-sm text-amber-900">
          <div className="font-semibold">
            {formatNumberFa(total)} پیش‌نویس آماده ثبت
          </div>
          <div className="text-xs text-amber-800">
            {withoutImage > 0 ? (
              <span>
                {formatNumberFa(withoutImage)} پیش‌نویس بدون عکس
              </span>
            ) : (
              <span>همه پیش‌نویس‌ها عکس دارند</span>
            )}
          </div>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="bg-white"
            onClick={onOpenBulkPicker}
            disabled={confirmAllMutation.isPending}
          >
            <ImagePlus className="h-4 w-4" />
            <span>افزودن دسته‌ای عکس</span>
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => confirmAllMutation.mutate()}
            disabled={confirmAllMutation.isPending || submittableDrafts.length === 0}
          >
            {confirmAllMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            <span>
              {submittableDrafts.length === 0
                ? "اول عکس اضافه کن"
                : imagelessDrafts.length === 0
                  ? `ثبت همه (${formatNumberFa(total)})`
                  : `ثبت آماده‌ها (${formatNumberFa(submittableDrafts.length)})`}
            </span>
          </Button>
        </div>
      </div>
    </div>
  );
}
