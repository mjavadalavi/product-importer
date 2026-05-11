"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { api, type ProductOut, type ProductImageOut } from "@/lib/api";
import { formatPriceToman } from "@/lib/format";

type StatusVariant = "default" | "secondary" | "destructive" | "outline";

function statusInfo(status: string): { variant: StatusVariant; label: string } {
  switch (status) {
    case "DRAFT":
    case "PROCESSING":
      return { variant: "secondary", label: "در حال پردازش" };
    case "READY":
      return { variant: "outline", label: "نیاز به تکمیل" };
    case "SUBMITTED":
      return { variant: "default", label: "ثبت شد" };
    case "FAILED":
      return { variant: "destructive", label: "ناموفق" };
    default:
      return { variant: "secondary", label: status };
  }
}

function pickImageUrl(image: ProductImageOut): string | null {
  if (image.use_enhanced && image.enhanced_url) return image.enhanced_url;
  return image.original_url ?? image.enhanced_url ?? null;
}

type EditableForm = {
  name: string;
  brief: string;
  description: string;
  price_final: string;
  stock: string;
  weight: string;
  package_weight: string;
  preparation_days: string;
  sku: string;
};

function toForm(product: ProductOut): EditableForm {
  return {
    name: product.name ?? "",
    brief: product.brief ?? "",
    description: product.description ?? "",
    price_final: product.price_final != null ? String(product.price_final) : "",
    stock: product.stock != null ? String(product.stock) : "",
    weight: product.weight != null ? String(product.weight) : "",
    package_weight:
      product.package_weight != null ? String(product.package_weight) : "",
    preparation_days:
      product.preparation_days != null ? String(product.preparation_days) : "",
    sku: product.sku ?? "",
  };
}

function parseOptionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  if (!Number.isFinite(n)) return null;
  return n;
}

function buildPatchPayload(
  original: ProductOut,
  form: EditableForm,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {};

  const nextName = form.name.trim() === "" ? null : form.name.trim();
  if (nextName !== (original.name ?? null)) payload.name = nextName;

  const nextBrief = form.brief.trim() === "" ? null : form.brief.trim();
  if (nextBrief !== (original.brief ?? null)) payload.brief = nextBrief;

  const nextDescription =
    form.description.trim() === "" ? null : form.description.trim();
  if (nextDescription !== (original.description ?? null))
    payload.description = nextDescription;

  const nextPrice = parseOptionalNumber(form.price_final);
  if (nextPrice !== (original.price_final ?? null))
    payload.price_final = nextPrice;

  const nextStock = parseOptionalNumber(form.stock);
  if (nextStock !== (original.stock ?? null)) payload.stock = nextStock;

  const nextWeight = parseOptionalNumber(form.weight);
  if (nextWeight !== (original.weight ?? null)) payload.weight = nextWeight;

  const nextPackageWeight = parseOptionalNumber(form.package_weight);
  if (nextPackageWeight !== (original.package_weight ?? null))
    payload.package_weight = nextPackageWeight;

  const nextPrepDays = parseOptionalNumber(form.preparation_days);
  if (nextPrepDays !== (original.preparation_days ?? null))
    payload.preparation_days = nextPrepDays;

  const nextSku = form.sku.trim() === "" ? null : form.sku.trim();
  if (nextSku !== (original.sku ?? null)) payload.sku = nextSku;

  return payload;
}

function formHasErrors(form: EditableForm): boolean {
  const numericFields: (keyof EditableForm)[] = [
    "price_final",
    "stock",
    "weight",
    "package_weight",
    "preparation_days",
  ];
  for (const key of numericFields) {
    const raw = form[key].trim();
    if (raw === "") continue;
    const n = Number(raw);
    if (!Number.isFinite(n)) return true;
    if (n < 0) return true;
  }
  return false;
}

function LoadingState() {
  return (
    <div className="px-4 py-3 flex flex-col gap-4">
      <Card className="p-4 flex flex-col gap-3">
        <Skeleton className="h-5 w-1/2" />
        <Skeleton className="h-4 w-1/3" />
        <div className="flex gap-2">
          <Skeleton className="w-32 h-32 rounded-lg" />
          <Skeleton className="w-32 h-32 rounded-lg" />
          <Skeleton className="w-32 h-32 rounded-lg" />
        </div>
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-24 w-full" />
      </Card>
    </div>
  );
}

function NotFoundState({ onBack }: { onBack: () => void }) {
  return (
    <div className="px-4 py-6 flex flex-col gap-3">
      <Card className="p-6 flex flex-col items-center gap-4 text-center">
        <div className="text-base font-semibold">محصول پیدا نشد</div>
        <Button variant="outline" onClick={onBack}>
          بازگشت
        </Button>
      </Card>
    </div>
  );
}

function PriceSampleRow({ sample }: { sample: Record<string, unknown> }) {
  const url =
    typeof sample.image_url === "string"
      ? sample.image_url
      : typeof sample.thumbnail_url === "string"
        ? (sample.thumbnail_url as string)
        : null;
  const name =
    typeof sample.name === "string"
      ? sample.name
      : typeof sample.title === "string"
        ? (sample.title as string)
        : "بدون نام";
  const priceRaw = sample.price ?? sample.price_final ?? null;
  const price =
    typeof priceRaw === "number"
      ? priceRaw
      : typeof priceRaw === "string" && priceRaw.trim() !== ""
        ? Number(priceRaw)
        : null;
  const vendorTitle =
    typeof sample.vendor_title === "string" ? sample.vendor_title : null;
  const weightBand =
    typeof sample.weight_band === "string" ? sample.weight_band : null;
  const weightRatioRaw = sample.weight_ratio;
  const weightRatio =
    typeof weightRatioRaw === "number"
      ? weightRatioRaw.toLocaleString("fa-IR", { maximumFractionDigits: 2 })
      : typeof weightRatioRaw === "string"
        ? weightRatioRaw
        : null;

  return (
    <Card className="flex gap-3 p-3 items-center">
      <div className="shrink-0">
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={name}
            className="w-14 h-14 rounded-md object-cover"
          />
        ) : (
          <Skeleton className="w-14 h-14 rounded-md" />
        )}
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-1">
        <div className="font-medium text-sm truncate">{name}</div>
        <div className="text-sm">
          {price != null && Number.isFinite(price)
            ? formatPriceToman(price)
            : "—"}
        </div>
        <div className="flex flex-wrap gap-1">
          {vendorTitle ? (
            <Badge variant="secondary" className="text-xs">
              {vendorTitle}
            </Badge>
          ) : null}
          {weightBand ? (
            <Badge variant="outline" className="text-xs">
              {weightBand}
            </Badge>
          ) : null}
          {weightRatio ? (
            <Badge variant="outline" className="text-xs">
              نسبت وزن: {weightRatio}
            </Badge>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

export default function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const id = params?.id ?? "";

  const {
    data: product,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["product", id],
    queryFn: () => api.get<ProductOut>(`/products/${id}`),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "PROCESSING" ? 3000 : false;
    },
  });

  const [form, setForm] = React.useState<EditableForm | null>(null);
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (product) {
      setForm(toForm(product));
    }
  }, [product]);

  const patchMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.patch<ProductOut>(`/products/${id}`, payload),
    onSuccess: () => {
      toast({
        title: "ذخیره شد",
        description: "تغییرات با موفقیت ذخیره شد.",
      });
      queryClient.invalidateQueries({ queryKey: ["product", id] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (err: unknown) => {
      const message =
        (err as { message?: string } | null)?.message ||
        "ذخیره تغییرات با خطا روبه‌رو شد.";
      toast({
        title: "خطا",
        description: message,
        variant: "destructive",
      });
    },
  });

  const resubmitMutation = useMutation({
    mutationFn: () => api.post<ProductOut>(`/products/${id}/resubmit`, null),
    onSuccess: () => {
      toast({
        title: "بازارسال انجام شد",
        description: "محصول دوباره برای پردازش ارسال شد.",
      });
      queryClient.invalidateQueries({ queryKey: ["product", id] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (err: unknown) => {
      const message =
        (err as { message?: string } | null)?.message ||
        "بازارسال با خطا روبه‌رو شد.";
      toast({
        title: "خطا",
        description: message,
        variant: "destructive",
      });
    },
  });

  const handleBack = React.useCallback(() => {
    router.back();
  }, [router]);

  const apiStatus = (error as { status?: number } | null)?.status;
  const isNotFound = isError && (apiStatus === 404 || !product);

  if (isLoading) {
    return (
      <div className="min-h-dvh">
        <header className="sticky top-0 z-30 bg-background/95 backdrop-blur border-b">
          <div className="h-12 px-2 flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleBack}
              aria-label="بازگشت"
            >
              <ChevronRight className="h-5 w-5" />
            </Button>
            <div className="font-semibold">جزئیات محصول</div>
          </div>
        </header>
        <LoadingState />
      </div>
    );
  }

  if (isError || !product) {
    return (
      <div className="min-h-dvh">
        <header className="sticky top-0 z-30 bg-background/95 backdrop-blur border-b">
          <div className="h-12 px-2 flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleBack}
              aria-label="بازگشت"
            >
              <ChevronRight className="h-5 w-5" />
            </Button>
            <div className="font-semibold">جزئیات محصول</div>
          </div>
        </header>
        <NotFoundState onBack={handleBack} />
        {/* Avoid unused warning */}
        <span className="hidden">{isNotFound ? "1" : "0"}</span>
      </div>
    );
  }

  const status = statusInfo(product.status);
  const images = product.images ?? [];
  const currentForm = form ?? toForm(product);
  const patchPayload = buildPatchPayload(product, currentForm);
  const hasEdits = Object.keys(patchPayload).length > 0;
  const formInvalid = formHasErrors(currentForm);
  const saveDisabled =
    !hasEdits || formInvalid || patchMutation.isPending;

  const aiResult = product.ai_result ?? null;
  const aiCategoryConfidenceRaw =
    aiResult && typeof aiResult === "object" && "category_confidence" in aiResult
      ? (aiResult as Record<string, unknown>).category_confidence
      : product.category_confidence;
  const aiCategoryConfidence =
    typeof aiCategoryConfidenceRaw === "number"
      ? Math.round(aiCategoryConfidenceRaw * 100)
      : null;
  const aiEstimatedWeight =
    aiResult && typeof aiResult === "object" && "estimated_weight" in aiResult
      ? (aiResult as Record<string, unknown>).estimated_weight
      : null;
  const aiSaleUnit =
    aiResult && typeof aiResult === "object" && "sale_unit" in aiResult
      ? (aiResult as Record<string, unknown>).sale_unit
      : null;

  const priceSamples = (product.price_samples ?? []).slice(0, 10);

  const errorsRaw = product.errors;
  const errorsEmpty =
    !errorsRaw ||
    (typeof errorsRaw === "object" &&
      !Array.isArray(errorsRaw) &&
      Object.keys(errorsRaw).length === 0);

  const updateField = (key: keyof EditableForm, value: string) => {
    setForm((prev) => ({
      ...(prev ?? toForm(product)),
      [key]: value,
    }));
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (saveDisabled) return;
    patchMutation.mutate(patchPayload);
  };

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 bg-background/95 backdrop-blur border-b">
        <div className="h-12 px-2 flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleBack}
            aria-label="بازگشت"
          >
            <ChevronRight className="h-5 w-5" />
          </Button>
          <div className="font-semibold">جزئیات محصول</div>
        </div>
      </header>

      <div className="px-4 py-3 flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={status.variant}>{status.label}</Badge>
          {product.basalam_product_id ? (
            <Badge variant="outline">
              شناسه باسلام: {product.basalam_product_id}
            </Badge>
          ) : null}
        </div>

        {images.length > 0 ? (
          <ScrollArea className="w-full whitespace-nowrap">
            <div className="flex gap-2 pb-2">
              {images.map((image) => {
                const url = pickImageUrl(image);
                if (!url) {
                  return (
                    <Skeleton
                      key={image.id}
                      className="w-32 h-32 rounded-lg shrink-0"
                    />
                  );
                }
                return (
                  <button
                    key={image.id}
                    type="button"
                    onClick={() => setPreviewUrl(url)}
                    className="shrink-0 focus:outline-none focus:ring-2 focus:ring-ring rounded-lg"
                    aria-label="مشاهده تصویر"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={url}
                      alt={product.name ?? "تصویر محصول"}
                      className="w-32 h-32 rounded-lg object-cover"
                    />
                  </button>
                );
              })}
            </div>
            <ScrollBar orientation="horizontal" />
          </ScrollArea>
        ) : null}

        <Tabs defaultValue="edit" dir="rtl">
          <TabsList className="w-full grid grid-cols-4">
            <TabsTrigger value="edit">ویرایش</TabsTrigger>
            <TabsTrigger value="ai">تحلیل AI</TabsTrigger>
            <TabsTrigger value="samples">نمونه قیمت</TabsTrigger>
            <TabsTrigger value="errors">خطاها</TabsTrigger>
          </TabsList>

          <TabsContent value="edit" className="mt-3">
            <Card className="p-4">
              <form
                className="flex flex-col gap-4"
                onSubmit={handleSubmit}
                noValidate
              >
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="name">نام محصول</Label>
                  <Input
                    id="name"
                    value={currentForm.name}
                    onChange={(e) => updateField("name", e.target.value)}
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="brief">توضیح کوتاه</Label>
                  <Textarea
                    id="brief"
                    rows={2}
                    value={currentForm.brief}
                    onChange={(e) => updateField("brief", e.target.value)}
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="description">توضیحات</Label>
                  <Textarea
                    id="description"
                    rows={5}
                    value={currentForm.description}
                    onChange={(e) =>
                      updateField("description", e.target.value)
                    }
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="category_title">دسته‌بندی</Label>
                  <Input
                    id="category_title"
                    value={product.category_title ?? ""}
                    readOnly
                    disabled
                  />
                  <span className="text-xs text-muted-foreground">
                    دسته‌بندی توسط هوش مصنوعی تعیین می‌شود و قابل ویرایش نیست.
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="price_final">قیمت (تومان)</Label>
                    <Input
                      id="price_final"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      value={currentForm.price_final}
                      onChange={(e) =>
                        updateField("price_final", e.target.value)
                      }
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="stock">موجودی</Label>
                    <Input
                      id="stock"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      value={currentForm.stock}
                      onChange={(e) => updateField("stock", e.target.value)}
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="weight">وزن (گرم)</Label>
                    <Input
                      id="weight"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      value={currentForm.weight}
                      onChange={(e) => updateField("weight", e.target.value)}
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="package_weight">وزن بسته (گرم)</Label>
                    <Input
                      id="package_weight"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      value={currentForm.package_weight}
                      onChange={(e) =>
                        updateField("package_weight", e.target.value)
                      }
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="preparation_days">
                      زمان آماده‌سازی (روز)
                    </Label>
                    <Input
                      id="preparation_days"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      value={currentForm.preparation_days}
                      onChange={(e) =>
                        updateField("preparation_days", e.target.value)
                      }
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="sku">شناسه انباری (SKU)</Label>
                    <Input
                      id="sku"
                      value={currentForm.sku}
                      onChange={(e) => updateField("sku", e.target.value)}
                    />
                  </div>
                </div>

                {formInvalid ? (
                  <div className="text-xs text-destructive">
                    مقادیر عددی باید معتبر و غیرمنفی باشند.
                  </div>
                ) : null}

                <Button
                  type="submit"
                  disabled={saveDisabled}
                  className="w-full"
                >
                  {patchMutation.isPending
                    ? "در حال ذخیره..."
                    : "ذخیره تغییرات"}
                </Button>
              </form>
            </Card>
          </TabsContent>

          <TabsContent value="ai" className="mt-3">
            <Card className="p-4 flex flex-col gap-3">
              {!aiResult ? (
                <div className="text-sm text-muted-foreground">
                  تحلیلی ثبت نشده است.
                </div>
              ) : (
                <>
                  <div className="flex flex-wrap gap-2">
                    {aiCategoryConfidence != null ? (
                      <Badge variant="secondary">
                        اطمینان دسته‌بندی: {aiCategoryConfidence}%
                      </Badge>
                    ) : null}
                    {typeof aiEstimatedWeight === "number" ||
                    typeof aiEstimatedWeight === "string" ? (
                      <Badge variant="outline">
                        وزن تخمینی: {String(aiEstimatedWeight)}
                      </Badge>
                    ) : null}
                    {typeof aiSaleUnit === "string" ||
                    typeof aiSaleUnit === "number" ? (
                      <Badge variant="outline">
                        واحد فروش: {String(aiSaleUnit)}
                      </Badge>
                    ) : null}
                  </div>

                  <div className="text-xs text-muted-foreground">
                    داده کامل:
                  </div>
                  <pre className="max-h-96 overflow-auto text-xs bg-muted rounded-md p-3 whitespace-pre-wrap break-words">
                    {JSON.stringify(aiResult, null, 2)}
                  </pre>
                </>
              )}
            </Card>
          </TabsContent>

          <TabsContent value="samples" className="mt-3">
            <div className="flex flex-col gap-2">
              {priceSamples.length === 0 ? (
                <Card className="p-4 text-sm text-muted-foreground">
                  نمونه قیمتی یافت نشد.
                </Card>
              ) : (
                priceSamples.map((sample, idx) => (
                  <PriceSampleRow
                    key={idx}
                    sample={
                      (sample && typeof sample === "object"
                        ? (sample as Record<string, unknown>)
                        : {}) as Record<string, unknown>
                    }
                  />
                ))
              )}
            </div>
          </TabsContent>

          <TabsContent value="errors" className="mt-3">
            <Card className="p-4 flex flex-col gap-3">
              {errorsEmpty ? (
                <div className="text-sm text-muted-foreground">
                  خطایی ثبت نشده.
                </div>
              ) : (
                <pre className="max-h-96 overflow-auto text-xs bg-muted rounded-md p-3 whitespace-pre-wrap break-words">
                  {JSON.stringify(errorsRaw, null, 2)}
                </pre>
              )}

              {product.status === "FAILED" ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => resubmitMutation.mutate()}
                  disabled={resubmitMutation.isPending}
                  className="self-start"
                >
                  <RefreshCcw className="h-4 w-4 ml-2" />
                  {resubmitMutation.isPending ? "در حال ارسال..." : "بازارسال"}
                </Button>
              ) : null}
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <Dialog
        open={!!previewUrl}
        onOpenChange={(open) => {
          if (!open) setPreviewUrl(null);
        }}
      >
        <DialogContent className="max-w-[95vw] sm:max-w-2xl p-2">
          <DialogTitle className="sr-only">تصویر محصول</DialogTitle>
          {previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={previewUrl}
              alt="تصویر محصول"
              className="w-full h-auto max-h-[80vh] object-contain rounded-md"
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
