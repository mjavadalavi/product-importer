"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Check,
  Clock,
  ImagePlus,
  Loader2,
  MoreVertical,
  Package,
  RefreshCcw,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { formatNumberFa } from "@/lib/format";
import { api, type ProductCreatedResponse, type ProductListItem } from "@/lib/api";
import { ImagePickerDialog } from "@/components/image-picker-dialog";

type StatusTone = "info" | "success" | "warning" | "danger" | "neutral";

function statusInfo(status: string): { tone: StatusTone; label: string } {
  switch (status) {
    case "DRAFT":
      return { tone: "warning", label: "پیش‌نویس" };
    case "PROCESSING":
      return { tone: "info", label: "در حال پردازش" };
    case "READY":
      return { tone: "warning", label: "نیاز به تکمیل" };
    case "SUBMITTED":
      return { tone: "success", label: "ثبت شد" };
    case "FAILED":
      return { tone: "danger", label: "ناموفق" };
    default:
      return { tone: "neutral", label: status };
  }
}

const TONE_CLASSES: Record<StatusTone, string> = {
  info: "bg-teal-50 text-teal-700 border-teal-100",
  success: "bg-emerald-50 text-emerald-700 border-emerald-100",
  warning: "bg-amber-50 text-amber-700 border-amber-100",
  danger: "bg-rose-50 text-rose-700 border-rose-100",
  neutral: "bg-neutral-100 text-neutral-700 border-neutral-200",
};

function StatusPill({ tone, label }: { tone: StatusTone; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium leading-5 ${TONE_CLASSES[tone]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {label}
    </span>
  );
}

function MetaChip({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-neutral-500">
      {icon}
      {children}
    </span>
  );
}

export function ProductCard({
  product,
  onInsufficient,
}: {
  product: ProductListItem;
  onInsufficient?: (required: number, available: number) => void;
}) {
  const status = statusInfo(product.status);
  const title = product.name || "بدون نام";
  const productId = product.basalam_product_id;
  const hasStock = typeof product.stock === "number";
  const hasPrep = typeof product.preparation_days === "number";
  const hasPrice = typeof product.price_final === "number" && product.price_final > 0;
  const isFailed = product.status === "FAILED";
  const isReady = product.status === "READY";
  const canResubmit = isFailed || isReady;
  const hasImage = !!product.primary_image_url;

  const { toast } = useToast();
  const queryClient = useQueryClient();

  const resubmitMutation = useMutation({
    mutationKey: ["resubmit-product", product.id],
    mutationFn: () =>
      api.post<ProductCreatedResponse>(
        `/products/${product.id}/resubmit`,
        null,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      toast({ title: "محصول دوباره برای پردازش ارسال شد" });
    },
    onError: (err: unknown) => {
      const e = err as ApiErrorShape;
      if (e?.status === 402) {
        const detail = (e.detail || {}) as { required?: number; available?: number };
        onInsufficient?.(detail.required ?? 0, detail.available ?? 0);
        return;
      }
      if (e?.status === 422) {
        toast({
          title: "این محصول عکس ندارد. اول عکس اضافه کن.",
          variant: "destructive",
        });
        return;
      }
      toast({
        title: "بازارسال ناموفق بود",
        description: e?.message || "مشکلی پیش آمد.",
        variant: "destructive",
      });
    },
  });

  return (
    <div className="block bg-white px-4 py-3">
      <div className="flex items-start gap-3">
        {/* Thumb (clickable) */}
        <Link href={`/products/${product.id}`} className="shrink-0" aria-label={title}>
          {product.primary_image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={product.primary_image_url}
              alt={title}
              className="h-16 w-16 rounded-md object-cover bg-neutral-100"
            />
          ) : (
            <div className="h-16 w-16 rounded-md bg-neutral-100 flex items-center justify-center">
              <Package className="h-6 w-6 text-neutral-300" />
            </div>
          )}
        </Link>

        {/* Body */}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <Link href={`/products/${product.id}`} className="min-w-0 block">
              <h3 className="line-clamp-2 text-sm font-medium text-neutral-900 leading-6">
                {title}
              </h3>
              {productId ? (
                <p className="mt-0.5 text-[11px] text-neutral-400 tabular-nums">
                  شناسه: {formatNumberFa(productId)}
                </p>
              ) : null}
            </Link>

            {/* 3-dot menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="-mr-1 -mt-1 inline-flex h-7 w-7 items-center justify-center rounded-md text-neutral-400 hover:bg-neutral-100"
                  aria-label="گزینه‌های بیشتر"
                >
                  <MoreVertical className="h-4 w-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem asChild>
                  <Link href={`/products/${product.id}`}>مشاهده جزئیات</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href={`/products/${product.id}`}>ویرایش محصول</Link>
                </DropdownMenuItem>
                {canResubmit ? (
                  <DropdownMenuItem
                    onSelect={(e) => {
                      e.preventDefault();
                      if (!hasImage) {
                        toast({
                          title: "این محصول عکس ندارد. اول عکس اضافه کن.",
                          variant: "destructive",
                        });
                        return;
                      }
                      resubmitMutation.mutate();
                    }}
                  >
                    بازارسال برای پردازش
                  </DropdownMenuItem>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Meta line */}
          {(hasStock || hasPrep) && (
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              {hasStock && (
                <MetaChip icon={<Package className="h-3 w-3" />}>
                  {formatNumberFa(product.stock!)} عدد
                </MetaChip>
              )}
              {hasPrep && (
                <MetaChip icon={<Clock className="h-3 w-3" />}>
                  {formatNumberFa(product.preparation_days!)} روز ارسال
                </MetaChip>
              )}
            </div>
          )}

          {/* Footer: price + status */}
          <div className="mt-2 flex items-center justify-between gap-2">
            <div className="text-sm font-semibold text-neutral-900 tabular-nums">
              {hasPrice ? (
                <>
                  {formatNumberFa(product.price_final!)}
                  <span className="text-[11px] font-normal text-neutral-400"> تومان</span>
                </>
              ) : (
                <span className="text-[11px] font-normal text-neutral-400">قیمت ثبت نشده</span>
              )}
            </div>
            <StatusPill tone={status.tone} label={status.label} />
          </div>

          {/* Inline action bar for FAILED/READY products */}
          {canResubmit ? (
            <div className="mt-3 flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="flex-1"
                asChild
              >
                <Link href={`/products/${product.id}#errors`}>مشاهده خطا</Link>
              </Button>
              <Button
                type="button"
                size="sm"
                className="flex-1"
                onClick={() => {
                  if (!hasImage) {
                    toast({
                      title: "این محصول عکس ندارد. اول عکس اضافه کن.",
                      variant: "destructive",
                    });
                    return;
                  }
                  resubmitMutation.mutate();
                }}
                disabled={resubmitMutation.isPending}
              >
                {resubmitMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCcw className="h-4 w-4" />
                )}
                <span>بازارسال</span>
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

type ApiErrorShape = {
  status?: number;
  message?: string;
  detail?: unknown;
};

export function DraftCard({
  product,
  onInsufficient,
  selected = false,
  onToggleSelect,
}: {
  product: ProductListItem;
  onInsufficient?: (required: number, available: number) => void;
  selected?: boolean;
  onToggleSelect?: (id: string) => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [pickerOpen, setPickerOpen] = React.useState(false);

  const title = product.name || "بدون نام";
  const productId = product.basalam_product_id;
  const hasImage = !!product.primary_image_url;
  const hasStock = typeof product.stock === "number";
  const hasPrep = typeof product.preparation_days === "number";
  const hasPrice =
    typeof product.price_final === "number" && product.price_final > 0;
  const category = product.category_title || null;

  const confirmMutation = useMutation({
    mutationKey: ["confirm-draft", product.id],
    mutationFn: () =>
      api.post<ProductCreatedResponse>(
        `/products/${product.id}/confirm`,
        null,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      toast({ title: "محصول در حال پردازش است" });
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
          title: "این محصول عکس ندارد. اول عکس اضافه کن.",
          variant: "destructive",
        });
        return;
      }
      toast({
        title: "خطا در ثبت محصول",
        description: e?.message || "مشکلی پیش آمد.",
        variant: "destructive",
      });
    },
  });

  return (
    <>
      <div className="bg-white border-b border-neutral-100 px-4 py-3">
        <div className="flex items-start gap-3">
          {/* Selection checkbox — START of row (right in RTL) */}
          {onToggleSelect ? (
            <div className="shrink-0 flex items-center pt-1">
              <input
                type="checkbox"
                checked={selected}
                onChange={() => onToggleSelect(product.id)}
                onClick={(e) => e.stopPropagation()}
                aria-label={`انتخاب ${product.name || "پیش‌نویس"}`}
                className="h-4 w-4 rounded accent-amber-500 cursor-pointer"
              />
            </div>
          ) : null}

          {/* Thumb */}
          <Link
            href={`/products/${product.id}`}
            className="shrink-0"
            aria-label="مشاهده پیش‌نویس"
          >
            {hasImage ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={product.primary_image_url ?? undefined}
                alt={title}
                className="h-16 w-16 rounded-md object-cover bg-neutral-100"
              />
            ) : (
              <div className="h-16 w-16 rounded-md bg-neutral-50 border border-dashed border-neutral-300 flex items-center justify-center">
                <ImagePlus className="h-6 w-6 text-neutral-400" />
              </div>
            )}
          </Link>

          {/* Body */}
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <Link
                  href={`/products/${product.id}`}
                  className="block min-w-0"
                >
                  <h3 className="line-clamp-2 text-sm font-medium text-neutral-900 leading-6">
                    {title}
                  </h3>
                </Link>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <span className="inline-flex items-center gap-1 rounded-md border border-amber-200 bg-amber-100/70 text-amber-800 px-1.5 py-0.5 text-[10px] font-medium">
                    پیش‌نویس
                  </span>
                  {hasImage ? (
                    <span className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 text-emerald-700 px-1.5 py-0.5 text-[10px] font-medium">
                      <ImagePlus className="h-3 w-3" />
                      عکس دارد
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setPickerOpen(true)}
                      className="inline-flex items-center gap-1 rounded-md border-2 border-rose-400 bg-rose-50 text-rose-700 px-1.5 py-0.5 text-[10px] font-medium hover:bg-rose-100 ring-1 ring-rose-300"
                    >
                      <AlertCircle className="h-3 w-3" />
                      این محصول عکس ندارد
                    </button>
                  )}
                  {category ? (
                    <span className="inline-flex items-center gap-1 rounded-md border border-neutral-200 bg-white text-neutral-700 px-1.5 py-0.5 text-[10px] font-medium">
                      <span className="text-neutral-400">دسته:</span>
                      {category}
                    </span>
                  ) : null}
                </div>
                {productId ? (
                  <p className="mt-1 text-[11px] text-neutral-400 tabular-nums">
                    شناسه: {formatNumberFa(productId)}
                  </p>
                ) : null}
              </div>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className="-mr-1 -mt-1 inline-flex h-7 w-7 items-center justify-center rounded-md text-neutral-400 hover:bg-neutral-100"
                    aria-label="گزینه‌های بیشتر"
                  >
                    <MoreVertical className="h-4 w-4" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start">
                  <DropdownMenuItem asChild>
                    <Link href={`/products/${product.id}`}>مشاهده جزئیات</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href={`/products/${product.id}`}>ویرایش محصول</Link>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Meta line */}
            {(hasStock || hasPrep) && (
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                {hasStock && (
                  <span className="inline-flex items-center gap-1 text-[11px] text-neutral-500">
                    <Package className="h-3 w-3" />
                    {formatNumberFa(product.stock!)} عدد
                  </span>
                )}
                {hasPrep && (
                  <span className="inline-flex items-center gap-1 text-[11px] text-neutral-500">
                    <Clock className="h-3 w-3" />
                    {formatNumberFa(product.preparation_days!)} روز ارسال
                  </span>
                )}
              </div>
            )}

            {/* Price */}
            <div className="mt-2 text-sm font-semibold text-neutral-900 tabular-nums">
              {hasPrice ? (
                <>
                  {formatNumberFa(product.price_final!)}
                  <span className="text-[11px] font-normal text-neutral-400">
                    {" "}
                    تومان
                  </span>
                </>
              ) : (
                <span className="text-[11px] font-normal text-neutral-400">
                  قیمت ثبت نشده
                </span>
              )}
            </div>

            {/* Bottom action row */}
            <div className="mt-3 flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="flex-1 bg-white"
                onClick={() => setPickerOpen(true)}
                disabled={confirmMutation.isPending}
              >
                <ImagePlus className="h-4 w-4" />
                <span>افزودن عکس</span>
              </Button>
              <Button
                type="button"
                size="sm"
                className="flex-1"
                onClick={() => confirmMutation.mutate()}
                disabled={confirmMutation.isPending || !hasImage}
                title={!hasImage ? "اول عکس اضافه کن" : undefined}
              >
                {confirmMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
                <span>ثبت</span>
              </Button>
            </div>
          </div>
        </div>
      </div>

      <ImagePickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        productId={product.id}
      />
    </>
  );
}
