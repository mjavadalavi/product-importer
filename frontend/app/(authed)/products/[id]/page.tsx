"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ChevronRight,
  RefreshCcw,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DetectionField,
  aiFieldConfidence,
  aiFieldValue,
  fieldErrorMessages,
} from "@/components/detection-field";
import { DetectedAttributes } from "@/components/detected-attributes";
import { ProductImageStrip } from "@/components/product-image-strip";
import { VariantsEditor } from "@/components/variants-editor";
import { useToast } from "@/hooks/use-toast";
import { api, type ProductOut } from "@/lib/api";
import { formatPriceToman, formatNumberFa } from "@/lib/format";

type StatusVariant = "default" | "secondary" | "destructive" | "outline";

const ERROR_FIELD_LABELS: Record<string, string> = {
  name: "نام محصول",
  title: "نام محصول",
  brief: "توضیح کوتاه",
  description: "توضیحات",
  category: "دسته‌بندی",
  category_id: "دسته‌بندی",
  price: "قیمت",
  price_final: "قیمت",
  primary_price: "قیمت",
  stock: "موجودی",
  preparation_days: "زمان آماده‌سازی",
  package_weight: "وزن بسته‌بندی",
  packaged_weight: "وزن بسته‌بندی",
  weight: "وزن خالص",
  image: "تصویر محصول",
  photo: "تصویر محصول",
  photos: "تصاویر محصول",
  attributes: "ویژگی‌ها",
  variants: "تنوع‌ها",
  unit: "واحد فروش",
  unit_type: "واحد فروش",
  unit_quantity: "مقدار واحد",
  sku: "شناسه انباری",
};

const FIELD_ERROR_KEYS = new Set<string>([
  "name",
  "title",
  "brief",
  "description",
  "category",
  "category_id",
  "price",
  "price_final",
  "primary_price",
  "stock",
  "preparation_days",
  "package_weight",
  "packaged_weight",
  "weight",
  "attributes",
  "variants",
  "unit",
  "unit_type",
  "unit_quantity",
  "sku",
]);

function fieldLabel(key: string): string {
  if (ERROR_FIELD_LABELS[key]) return ERROR_FIELD_LABELS[key];
  if (key.startsWith("attribute:")) return "ویژگی الزامی";
  return key;
}

/**
 * Pull "general" (non-field-specific) error messages out of the product
 * `errors` blob — these belong in the top-of-form red banner. Field-specific
 * errors are already surfaced under the relevant input via `fieldErrorMessages`.
 */
function extractGeneralErrorMessages(errors: unknown): string[] {
  if (!errors) return [];
  if (typeof errors === "string") return [errors];
  if (!(errors && typeof errors === "object")) return [];

  const out: string[] = [];
  const seen = new Set<string>();
  const push = (s: unknown) => {
    if (typeof s !== "string") return;
    const t = s.trim();
    if (!t || seen.has(t)) return;
    seen.add(t);
    out.push(t);
  };

  const e = errors as Record<string, unknown>;

  if (typeof e.message === "string") push(e.message);

  const fieldErrors = e.field_errors;
  if (
    fieldErrors &&
    typeof fieldErrors === "object" &&
    !Array.isArray(fieldErrors)
  ) {
    // Field-level errors that DON'T have a corresponding inline input
    // surface here so they aren't silently dropped.
    for (const [k, msgs] of Object.entries(
      fieldErrors as Record<string, unknown>,
    )) {
      if (FIELD_ERROR_KEYS.has(k) || k.startsWith("attribute:")) continue;
      if (Array.isArray(msgs)) {
        for (const m of msgs) {
          if (typeof m === "string") push(`${fieldLabel(k)}: ${m}`);
        }
      } else if (typeof msgs === "string") {
        push(`${fieldLabel(k)}: ${msgs}`);
      }
    }
  }

  if (Array.isArray(e.general_errors)) {
    for (const g of e.general_errors) push(g);
  }

  if (typeof e.basalam_update === "string") {
    push(`به‌روزرسانی باسلام: ${e.basalam_update}`);
  }

  const provider = e.provider_detail;
  if (provider && typeof provider === "object" && !Array.isArray(provider)) {
    const pd = provider as Record<string, unknown>;
    const lists = [pd.messages, pd.openapi_raw_data, pd.errors, pd.detail];
    for (const list of lists) {
      if (Array.isArray(list)) {
        for (const item of list) {
          if (item && typeof item === "object") {
            const m =
              (item as Record<string, unknown>).message ??
              (item as Record<string, unknown>).msg;
            if (typeof m === "string") push(m);
          }
        }
      } else if (typeof list === "string") {
        push(list);
      }
    }
  }

  return out;
}

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

function variantsEqual(
  a: Array<Record<string, unknown>> | null | undefined,
  b: Array<Record<string, unknown>> | null | undefined,
): boolean {
  try {
    return JSON.stringify(a ?? []) === JSON.stringify(b ?? []);
  } catch {
    return false;
  }
}

function buildPatchPayload(
  original: ProductOut,
  form: EditableForm,
  variants: Array<Record<string, unknown>> | null,
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

  if (variants && !variantsEqual(variants, original.variants)) {
    payload.variants = variants;
  }

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

// ---------------------------------------------------------------------------
// ProductDetailPage
// ---------------------------------------------------------------------------
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
  const [variants, setVariants] = React.useState<Array<Record<string, unknown>> | null>(null);

  React.useEffect(() => {
    if (product) {
      setForm(toForm(product));
      setVariants(product.variants ? [...product.variants] : []);
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
        <header className="sticky top-14 z-30 bg-background/95 backdrop-blur border-b">
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
        <header className="sticky top-14 z-30 bg-background/95 backdrop-blur border-b">
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
  const currentVariants = variants ?? (product.variants ?? []);
  const patchPayload = buildPatchPayload(product, currentForm, currentVariants);
  const hasEdits = Object.keys(patchPayload).length > 0;
  const formInvalid = formHasErrors(currentForm);
  const saveDisabled = !hasEdits || formInvalid || patchMutation.isPending;

  const aiResult = product.ai_result ?? null;
  const aiCategoryConfidenceRaw =
    aiResult && typeof aiResult === "object" && "category_confidence" in aiResult
      ? (aiResult as Record<string, unknown>).category_confidence
      : product.category_confidence;
  const aiCategoryConfidence =
    typeof aiCategoryConfidenceRaw === "number"
      ? Math.round(aiCategoryConfidenceRaw * 100)
      : null;

  const priceSamples = (product.price_samples ?? []).slice(0, 10);

  const errorsRaw = product.errors;
  const generalErrors = extractGeneralErrorMessages(errorsRaw);

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

  const errs = errorsRaw as Record<string, unknown> | null | undefined;
  const fieldErrors =
    errs && typeof errs === "object"
      ? (errs.field_errors as Record<string, unknown> | undefined)
      : undefined;
  const missingFields = fieldErrors
    ? Object.keys(fieldErrors).filter((k) => {
        const arr = fieldErrors[k];
        return Array.isArray(arr) && arr.length > 0;
      })
    : [];

  return (
    <div className="min-h-dvh">
      <header className="sticky top-14 z-30 bg-background/95 backdrop-blur border-b">
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

        {missingFields.length > 0 ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 flex gap-2 text-amber-800">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div className="flex-1 text-sm leading-6">
              <div className="font-medium">
                {formatNumberFa(missingFields.length)} مورد نیاز به تکمیل داره
              </div>
              <div className="text-xs text-amber-700/90">
                هوش مصنوعی نتونست این فیلدها رو تشخیص بده. خودت تکمیل کن تا
                محصول قابل ارسال بشه.
              </div>
            </div>
          </div>
        ) : null}

        {/* General (non-field) error banner — replaces the old Errors tab. */}
        {generalErrors.length > 0 ? (
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 flex gap-2 text-rose-800">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div className="flex-1 text-sm leading-6 flex flex-col gap-1">
              <div className="font-medium">خطا در ثبت یا به‌روزرسانی محصول</div>
              <ul className="list-disc pr-4 text-xs leading-5">
                {generalErrors.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
              {product.status === "FAILED" ? (
                <div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => resubmitMutation.mutate()}
                    disabled={resubmitMutation.isPending}
                    className="mt-1"
                  >
                    <RefreshCcw className="h-4 w-4 ml-1" />
                    {resubmitMutation.isPending
                      ? "در حال ارسال..."
                      : "بازارسال"}
                  </Button>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* Image strip */}
        <ProductImageStrip
          productId={product.id}
          productStatus={product.status}
          images={images}
        />

        {/* Edit form — flat, no tabs */}
        <Card className="p-4">
          <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
            <DetectionField
              id="name"
              label="نام محصول"
              required
              errors={fieldErrorMessages(errorsRaw, "name")}
              aiConfidence={aiFieldConfidence(aiResult, "title")}
              aiSuggestion={aiFieldValue(aiResult, "title")}
              currentValue={currentForm.name}
              onApplyAi={(v) => updateField("name", v)}
            >
              <Input
                id="name"
                value={currentForm.name}
                onChange={(e) => updateField("name", e.target.value)}
              />
            </DetectionField>

            <DetectionField
              id="brief"
              label="توضیح کوتاه"
              errors={fieldErrorMessages(errorsRaw, "brief")}
              aiConfidence={aiFieldConfidence(aiResult, "brief")}
              aiSuggestion={aiFieldValue(aiResult, "brief")}
              currentValue={currentForm.brief}
              onApplyAi={(v) => updateField("brief", v)}
            >
              <Textarea
                id="brief"
                rows={2}
                value={currentForm.brief}
                onChange={(e) => updateField("brief", e.target.value)}
              />
            </DetectionField>

            <DetectionField
              id="description"
              label="توضیحات"
              errors={fieldErrorMessages(errorsRaw, "description")}
              aiConfidence={aiFieldConfidence(aiResult, "description")}
              aiSuggestion={aiFieldValue(aiResult, "description")}
              currentValue={currentForm.description}
              onApplyAi={(v) => updateField("description", v)}
            >
              <Textarea
                id="description"
                rows={5}
                value={currentForm.description}
                onChange={(e) => updateField("description", e.target.value)}
              />
            </DetectionField>

            <DetectionField
              id="category_title"
              label="دسته‌بندی"
              required
              errors={fieldErrorMessages(errorsRaw, "category")}
              aiConfidence={
                aiFieldConfidence(aiResult, "category") ?? aiCategoryConfidence
              }
              hint="دسته‌بندی توسط هوش مصنوعی تعیین می‌شود و قابل ویرایش نیست."
            >
              <Input
                id="category_title"
                value={product.category_title ?? ""}
                readOnly
                disabled
              />
            </DetectionField>

            <div className="grid grid-cols-2 gap-3">
              <DetectionField
                id="price_final"
                label="قیمت (تومان)"
                required
                errors={fieldErrorMessages(errorsRaw, "price")}
                aiSuggestion={aiFieldValue(aiResult, "price")}
                currentValue={currentForm.price_final}
                onApplyAi={(v) => updateField("price_final", v)}
              >
                <Input
                  id="price_final"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={currentForm.price_final}
                  onChange={(e) => updateField("price_final", e.target.value)}
                />
              </DetectionField>

              <DetectionField
                id="stock"
                label="موجودی"
                required
                errors={fieldErrorMessages(errorsRaw, "stock")}
                aiSuggestion={aiFieldValue(aiResult, "stock")}
                currentValue={currentForm.stock}
                onApplyAi={(v) => updateField("stock", v)}
              >
                <Input
                  id="stock"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={currentForm.stock}
                  onChange={(e) => updateField("stock", e.target.value)}
                />
              </DetectionField>

              <DetectionField
                id="weight"
                label="وزن (گرم)"
                errors={fieldErrorMessages(errorsRaw, "weight")}
                aiConfidence={aiFieldConfidence(aiResult, "estimated_weight")}
                aiSuggestion={aiFieldValue(aiResult, "estimated_weight")}
                currentValue={currentForm.weight}
                onApplyAi={(v) => updateField("weight", v)}
              >
                <Input
                  id="weight"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={currentForm.weight}
                  onChange={(e) => updateField("weight", e.target.value)}
                />
              </DetectionField>

              <DetectionField
                id="package_weight"
                label="وزن بسته (گرم)"
                required
                errors={fieldErrorMessages(errorsRaw, "package_weight")}
                aiConfidence={aiFieldConfidence(
                  aiResult,
                  "estimated_package_weight",
                )}
                aiSuggestion={aiFieldValue(aiResult, "estimated_package_weight")}
                currentValue={currentForm.package_weight}
                onApplyAi={(v) => updateField("package_weight", v)}
              >
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
              </DetectionField>

              <DetectionField
                id="preparation_days"
                label="زمان آماده‌سازی (روز)"
                errors={fieldErrorMessages(errorsRaw, "preparation_days")}
                aiSuggestion={aiFieldValue(aiResult, "preparation_days")}
                currentValue={currentForm.preparation_days}
                onApplyAi={(v) => updateField("preparation_days", v)}
              >
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
              </DetectionField>

              <DetectionField
                id="sku"
                label="شناسه انباری (SKU)"
                errors={fieldErrorMessages(errorsRaw, "sku")}
                aiSuggestion={aiFieldValue(aiResult, "sku")}
                currentValue={currentForm.sku}
                onApplyAi={(v) => updateField("sku", v)}
              >
                <Input
                  id="sku"
                  value={currentForm.sku}
                  onChange={(e) => updateField("sku", e.target.value)}
                />
              </DetectionField>
            </div>

            {/* Variants editor */}
            <div className="rounded-md border border-neutral-200 p-3">
              <VariantsEditor
                value={currentVariants}
                onChange={(next) => setVariants(next)}
                disabled={patchMutation.isPending}
              />
              {fieldErrorMessages(errorsRaw, "variants").length > 0 ? (
                <ul className="mt-2 text-xs text-rose-600 leading-5">
                  {fieldErrorMessages(errorsRaw, "variants").map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              ) : null}
            </div>

            {formInvalid ? (
              <div className="text-xs text-destructive">
                مقادیر عددی باید معتبر و غیرمنفی باشند.
              </div>
            ) : null}

            <Button type="submit" disabled={saveDisabled} className="w-full">
              {patchMutation.isPending ? "در حال ذخیره..." : "ذخیره تغییرات"}
            </Button>
          </form>
        </Card>

        {/* AI detected attributes — surfaced inline below the form */}
        {aiResult ? (
          <Card className="p-4">
            <DetectedAttributes aiResult={aiResult as Record<string, unknown>} />
          </Card>
        ) : null}

        {/* Price samples */}
        {priceSamples.length > 0 ? (
          <div className="flex flex-col gap-2">
            <div className="text-sm font-medium text-neutral-700">
              نمونه قیمت
            </div>
            {priceSamples.map((sample, idx) => (
              <PriceSampleRow
                key={idx}
                sample={
                  (sample && typeof sample === "object"
                    ? (sample as Record<string, unknown>)
                    : {}) as Record<string, unknown>
                }
              />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
