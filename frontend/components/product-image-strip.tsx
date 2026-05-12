"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Image as ImageIcon,
  ImagePlus,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ImagePickerDialog } from "@/components/image-picker-dialog";
import { useToast } from "@/hooks/use-toast";
import { api, type ProductImageOut, type ProductOut } from "@/lib/api";
import { formatNumberFa } from "@/lib/format";

function pickImageUrl(image: ProductImageOut): string | null {
  if (image.use_enhanced && image.enhanced_url) return image.enhanced_url;
  return image.original_url ?? image.enhanced_url ?? null;
}

function ImageStatusBadge({
  image,
  productStatus,
}: {
  image: ProductImageOut;
  productStatus: string;
}) {
  if (image.enhanced_url) {
    return (
      <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium leading-none bg-green-100 text-green-800 border border-green-200">
        <Sparkles className="h-2.5 w-2.5" />
        AI پردازش شده
      </span>
    );
  }
  if (
    !image.enhanced_url &&
    image.enhancement_error &&
    productStatus !== "DRAFT"
  ) {
    return (
      <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium leading-none bg-amber-100 text-amber-800 border border-amber-200">
        <AlertTriangle className="h-2.5 w-2.5" />
        AI ناموفق
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium leading-none bg-muted text-muted-foreground border border-border">
      <ImageIcon className="h-2.5 w-2.5" />
      اصلی
    </span>
  );
}

function DeleteImageDialog({
  open,
  onOpenChange,
  onConfirm,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isPending: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm" dir="rtl">
        <DialogTitle>حذف عکس</DialogTitle>
        <p className="text-sm text-muted-foreground">
          این کار قابل بازگشت نیست.
        </p>
        <div className="flex gap-2 justify-end mt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            انصراف
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? "در حال حذف..." : "حذف"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ImagePreviewDialog({
  image,
  open,
  onOpenChange,
}: {
  image: ProductImageOut | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const hasBoth = !!(image?.original_url && image?.enhanced_url);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[95vw] sm:max-w-2xl p-2" dir="rtl">
        <DialogTitle className="text-sm font-medium px-2 pt-1 truncate">
          {image?.filename ?? "تصویر محصول"}
        </DialogTitle>

        {image ? (
          <div className="flex flex-col gap-2">
            {hasBoth ? (
              <Tabs defaultValue="sent" dir="rtl" className="w-full">
                <TabsList className="w-full grid grid-cols-2 mx-auto max-w-xs">
                  <TabsTrigger value="sent">نسخه ارسالی</TabsTrigger>
                  <TabsTrigger value="original">اصلی</TabsTrigger>
                </TabsList>
                <TabsContent value="sent" className="mt-2">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={image.enhanced_url!}
                    alt="نسخه ارسالی"
                    className="w-full h-auto max-h-[70vh] object-contain rounded-md"
                  />
                </TabsContent>
                <TabsContent value="original" className="mt-2">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={image.original_url!}
                    alt="نسخه اصلی"
                    className="w-full h-auto max-h-[70vh] object-contain rounded-md"
                  />
                </TabsContent>
              </Tabs>
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={pickImageUrl(image) ?? ""}
                alt="تصویر محصول"
                className="w-full h-auto max-h-[70vh] object-contain rounded-md"
              />
            )}

            <p className="text-[11px] text-muted-foreground text-center pb-1">
              تنها نسخه‌ای به باسلام ارسال می‌شود که AI پردازش کرده است.
            </p>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function ImageCard({
  image,
  productId,
  productStatus,
  priority,
  isDragging,
  isDragOver,
  onOpenPreview,
  onDragStart,
  onDragOver,
  onDragLeave,
  onDrop,
  onDragEnd,
}: {
  image: ProductImageOut;
  productId: string;
  productStatus: string;
  priority: number;
  isDragging: boolean;
  isDragOver: boolean;
  onOpenPreview: (image: ProductImageOut) => void;
  onDragStart: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragLeave: (e: React.DragEvent<HTMLDivElement>) => void;
  onDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragEnd: (e: React.DragEvent<HTMLDivElement>) => void;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [deleteOpen, setDeleteOpen] = React.useState(false);

  const url = pickImageUrl(image);
  const isDraft = productStatus === "DRAFT";
  const canReorder = ["DRAFT", "READY", "FAILED"].includes(productStatus);

  const deleteMutation = useMutation({
    mutationFn: () =>
      api.del<ProductOut>(`/products/${productId}/images/${image.id}`),
    onSuccess: () => {
      toast({ title: "عکس حذف شد" });
      queryClient.invalidateQueries({ queryKey: ["product", productId] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setDeleteOpen(false);
    },
    onError: (err: unknown) => {
      const message =
        (err as { message?: string } | null)?.message ||
        "حذف عکس با خطا روبه‌رو شد.";
      toast({ title: "خطا", description: message, variant: "destructive" });
    },
  });

  const enhanceMutation = useMutation({
    mutationFn: () =>
      api.post<ProductOut>(
        `/products/${productId}/images/${image.id}/enhance`,
        null,
      ),
    onSuccess: () => {
      toast({ title: "بهبود AI انجام شد" });
      queryClient.invalidateQueries({ queryKey: ["product", productId] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (err: unknown) => {
      const message =
        (err as { message?: string } | null)?.message ||
        "بهبود AI با خطا روبه‌رو شد.";
      toast({ title: "خطا", description: message, variant: "destructive" });
    },
  });

  if (!url) {
    return <Skeleton className="w-36 h-36 rounded-lg shrink-0" />;
  }

  return (
    <>
      <div
        draggable={canReorder}
        onDragStart={canReorder ? onDragStart : undefined}
        onDragOver={canReorder ? onDragOver : undefined}
        onDragLeave={canReorder ? onDragLeave : undefined}
        onDrop={canReorder ? onDrop : undefined}
        onDragEnd={canReorder ? onDragEnd : undefined}
        className={
          "relative shrink-0 w-36 h-36 transition-opacity " +
          (isDragging ? "opacity-40" : "") +
          (isDragOver ? " ring-2 ring-emerald-400 rounded-lg" : "") +
          (canReorder ? " cursor-move" : "")
        }
      >
        {/* Clickable thumbnail */}
        <button
          type="button"
          onClick={() => onOpenPreview(image)}
          className="block w-full h-full focus:outline-none focus:ring-2 focus:ring-ring rounded-lg"
          aria-label="مشاهده تصویر"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={url}
            alt="تصویر محصول"
            className="w-full h-full rounded-lg object-cover"
            draggable={false}
          />
        </button>

        {/* Priority badge — bottom-start */}
        <div className="absolute bottom-1 start-1 pointer-events-none">
          <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-md bg-neutral-900/80 text-white text-[10px] font-semibold tabular-nums">
            {formatNumberFa(priority)}
          </span>
        </div>

        {/* Top-right: AI status badge */}
        <div className="absolute top-1 end-1 pointer-events-none">
          <ImageStatusBadge image={image} productStatus={productStatus} />
        </div>

        {/* Top-left: delete button (DRAFT only) */}
        {isDraft ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteOpen(true);
            }}
            className="absolute top-1 start-1 w-6 h-6 rounded-full bg-background/90 border border-destructive text-destructive flex items-center justify-center hover:bg-destructive hover:text-destructive-foreground transition-colors focus:outline-none focus:ring-2 focus:ring-destructive"
            aria-label="حذف عکس"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : null}

        {/* Bottom-end: AI enhance button */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            if (!enhanceMutation.isPending) enhanceMutation.mutate();
          }}
          disabled={enhanceMutation.isPending}
          className="absolute bottom-1 end-1 w-7 h-7 rounded-full bg-background/90 border border-emerald-300 text-emerald-700 flex items-center justify-center hover:bg-emerald-50 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-emerald-300"
          aria-label="بهبود با AI"
          title="بهبود با AI"
        >
          {enhanceMutation.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
        </button>

        {/* Full-thumb spinner overlay while enhancing */}
        {enhanceMutation.isPending ? (
          <div className="absolute inset-0 rounded-lg bg-black/30 flex items-center justify-center pointer-events-none">
            <Loader2 className="h-6 w-6 text-white animate-spin" />
          </div>
        ) : null}
      </div>

      <DeleteImageDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={() => deleteMutation.mutate()}
        isPending={deleteMutation.isPending}
      />
    </>
  );
}

function ImagesBanner({
  images,
  productStatus,
}: {
  images: ProductImageOut[];
  productStatus: string;
}) {
  const anyUnprocessed = images.some((img) => !img.enhanced_url);

  if (!anyUnprocessed) return null;

  if (productStatus === "DRAFT") {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 p-3 flex gap-2 text-amber-800">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
        <p className="text-xs leading-5">
          عکس‌های این محصول هنوز پردازش نشده‌اند. بعد از ثبت، AI روی آن‌ها
          اعمال می‌شود.
        </p>
      </div>
    );
  }

  if (productStatus === "SUBMITTED") {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 p-3 flex gap-2 text-amber-800">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
        <p className="text-xs leading-5">
          بعضی عکس‌ها در پردازش AI ناموفق بودند و در باسلام ثبت نشدند.
        </p>
      </div>
    );
  }

  return null;
}

function AddImageTile({ productId }: { productId: string }) {
  const [open, setOpen] = React.useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="افزودن عکس"
        className="shrink-0 h-36 w-36 rounded-lg border-2 border-dashed border-neutral-300 bg-neutral-50 hover:bg-neutral-100 flex flex-col items-center justify-center gap-1 text-neutral-500 transition-colors"
      >
        <ImagePlus className="h-7 w-7" />
        <span className="text-xs font-medium">افزودن عکس</span>
      </button>
      <ImagePickerDialog
        open={open}
        onOpenChange={setOpen}
        productId={productId}
      />
    </>
  );
}

function AddImagesEmptyState({ productId }: { productId: string }) {
  const [open, setOpen] = React.useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full rounded-lg border-2 border-dashed border-amber-300 bg-amber-50/60 hover:bg-amber-100/60 transition-colors px-4 py-6 flex flex-col items-center justify-center gap-2 text-amber-800"
      >
        <ImagePlus className="h-8 w-8" />
        <span className="text-sm font-semibold">این محصول هنوز عکس ندارد</span>
        <span className="text-xs text-amber-700/80">
          برای افزودن عکس از گالری یا دوربین اینجا بزن
        </span>
      </button>
      <ImagePickerDialog
        open={open}
        onOpenChange={setOpen}
        productId={productId}
      />
    </>
  );
}

/**
 * ProductImageStrip — horizontal scrollable strip of product images with
 *  - per-image numeric priority badge
 *  - drag-and-drop reorder (HTML5 DnD, calls `PATCH /products/{id}/images/order`)
 *  - per-image "AI enhance" button (calls `POST /.../enhance`)
 *  - delete (DRAFT) and preview
 */
export function ProductImageStrip({
  productId,
  productStatus,
  images,
}: {
  productId: string;
  productStatus: string;
  images: ProductImageOut[];
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [previewImage, setPreviewImage] = React.useState<ProductImageOut | null>(null);
  const [dragId, setDragId] = React.useState<string | null>(null);
  const [overId, setOverId] = React.useState<string | null>(null);

  // Local ordering for optimistic UX while the reorder mutation is in flight.
  const [localOrder, setLocalOrder] = React.useState<string[] | null>(null);

  const reorderMutation = useMutation({
    mutationFn: (orderedIds: string[]) =>
      api.patch<ProductOut>(`/products/${productId}/images/order`, {
        ordered_ids: orderedIds,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["product", productId] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (err: unknown) => {
      // Roll back the optimistic order.
      setLocalOrder(null);
      const message =
        (err as { message?: string } | null)?.message ||
        "تغییر ترتیب با خطا روبه‌رو شد.";
      toast({ title: "خطا", description: message, variant: "destructive" });
    },
    onSettled: () => {
      setLocalOrder(null);
    },
  });

  // Build the effective ordered list. Prefer local (in-flight) order; else
  // sort by the backend `order` field.
  const orderedImages = React.useMemo(() => {
    if (!images.length) return images;
    const byId = new Map(images.map((img) => [img.id, img]));
    if (localOrder) {
      const out: ProductImageOut[] = [];
      for (const id of localOrder) {
        const img = byId.get(id);
        if (img) out.push(img);
      }
      // Append any new images not in the local order.
      for (const img of images) {
        if (!localOrder.includes(img.id)) out.push(img);
      }
      return out;
    }
    return [...images].sort((a, b) => a.order - b.order);
  }, [images, localOrder]);

  const canEditImages = ["DRAFT", "READY", "FAILED"].includes(productStatus);

  if (orderedImages.length === 0) {
    if (!canEditImages) return null;
    return <AddImagesEmptyState productId={productId} />;
  }

  const handleDrop = (targetId: string) => {
    if (!dragId || dragId === targetId) {
      setDragId(null);
      setOverId(null);
      return;
    }
    const currentIds = orderedImages.map((img) => img.id);
    const fromIdx = currentIds.indexOf(dragId);
    const toIdx = currentIds.indexOf(targetId);
    if (fromIdx < 0 || toIdx < 0) {
      setDragId(null);
      setOverId(null);
      return;
    }
    const next = [...currentIds];
    const [moved] = next.splice(fromIdx, 1);
    next.splice(toIdx, 0, moved);
    setLocalOrder(next);
    setDragId(null);
    setOverId(null);
    reorderMutation.mutate(next);
  };

  return (
    <div className="flex flex-col gap-2">
      <ImagesBanner images={orderedImages} productStatus={productStatus} />
      <ScrollArea className="w-full whitespace-nowrap">
        <div className="flex gap-2 pb-2 items-stretch">
          {orderedImages.map((image, idx) => (
            <ImageCard
              key={image.id}
              image={image}
              productId={productId}
              productStatus={productStatus}
              priority={idx + 1}
              isDragging={dragId === image.id}
              isDragOver={overId === image.id && dragId !== image.id}
              onOpenPreview={setPreviewImage}
              onDragStart={(e) => {
                setDragId(image.id);
                e.dataTransfer.effectAllowed = "move";
                try {
                  e.dataTransfer.setData("text/plain", image.id);
                } catch {
                  // some browsers throw on empty payloads — ignore
                }
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                if (dragId && dragId !== image.id) {
                  setOverId(image.id);
                }
              }}
              onDragLeave={() => {
                if (overId === image.id) setOverId(null);
              }}
              onDrop={(e) => {
                e.preventDefault();
                handleDrop(image.id);
              }}
              onDragEnd={() => {
                setDragId(null);
                setOverId(null);
              }}
            />
          ))}
          {canEditImages ? <AddImageTile productId={productId} /> : null}
        </div>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>

      <ImagePreviewDialog
        image={previewImage}
        open={!!previewImage}
        onOpenChange={(open) => {
          if (!open) setPreviewImage(null);
        }}
      />
    </div>
  );
}
