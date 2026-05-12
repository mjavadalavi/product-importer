"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ImagePlus,
  Loader2,
  RotateCw,
  Sparkles,
  X,
} from "lucide-react";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import {
  api,
  type ProductImageIn,
  type ProductListItem,
  type ProductOut,
} from "@/lib/api";
import { uploadFile } from "@/lib/api/files";
import { cn } from "@/lib/utils";
import { formatNumberFa, uid } from "@/lib/format";

type StagedPhoto = {
  id: string;
  filename: string;
  previewUrl: string;
  file: File;
  fileId: string | null;
  uploading: boolean;
  error: string | null;
};

type Assignments = Record<string, string[]>;

type BulkImagesResponse = {
  attached: number;
  products: ProductOut[];
};

type ApiErrorShape = {
  status?: number;
  message?: string;
  detail?: unknown;
};

export function BulkImageAssigner({
  open,
  onOpenChange,
  drafts,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  drafts: ProductListItem[];
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const fileRef = React.useRef<HTMLInputElement | null>(null);

  const [step, setStep] = React.useState<1 | 2>(1);
  const [photos, setPhotos] = React.useState<StagedPhoto[]>([]);
  // assignments: draftId -> list of staged photo ids
  const [assignments, setAssignments] = React.useState<Assignments>({});
  const [selectedPhotoId, setSelectedPhotoId] = React.useState<string | null>(
    null,
  );

  // Track object URLs for cleanup
  const objectUrlsRef = React.useRef<string[]>([]);
  React.useEffect(() => {
    return () => {
      objectUrlsRef.current.forEach((u) => URL.revokeObjectURL(u));
      objectUrlsRef.current = [];
    };
  }, []);

  React.useEffect(() => {
    if (!open) {
      setStep(1);
      setPhotos([]);
      setAssignments({});
      setSelectedPhotoId(null);
      objectUrlsRef.current.forEach((u) => URL.revokeObjectURL(u));
      objectUrlsRef.current = [];
    }
  }, [open]);

  const startUploadFor = React.useCallback((entry: StagedPhoto) => {
    setPhotos((prev) =>
      prev.map((p) =>
        p.id === entry.id ? { ...p, uploading: true, error: null } : p,
      ),
    );
    uploadFile(entry.file, { kind: "product_image" })
      .then((res) => {
        setPhotos((prev) =>
          prev.map((p) =>
            p.id === entry.id
              ? { ...p, uploading: false, fileId: res.id, error: null }
              : p,
          ),
        );
      })
      .catch((err: unknown) => {
        const msg =
          (err as { message?: string })?.message || "آپلود ناموفق بود";
        setPhotos((prev) =>
          prev.map((p) =>
            p.id === entry.id ? { ...p, uploading: false, error: msg } : p,
          ),
        );
      });
  }, []);

  const onPickGallery = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    for (const f of files) {
      const previewUrl = URL.createObjectURL(f);
      objectUrlsRef.current.push(previewUrl);
      const entry: StagedPhoto = {
        id: uid(),
        filename: f.name,
        previewUrl,
        file: f,
        fileId: null,
        uploading: false,
        error: null,
      };
      setPhotos((s) => [...s, entry]);
      startUploadFor(entry);
    }
    if (fileRef.current) fileRef.current.value = "";
  };

  const retryPhoto = (id: string) => {
    const entry = photos.find((p) => p.id === id);
    if (entry) startUploadFor(entry);
  };

  const removePhoto = (id: string) => {
    setPhotos((p) => p.filter((x) => x.id !== id));
    // remove from any assignment
    setAssignments((prev) => {
      const next: Assignments = {};
      for (const [draftId, ids] of Object.entries(prev)) {
        const filtered = ids.filter((x) => x !== id);
        if (filtered.length) next[draftId] = filtered;
      }
      return next;
    });
    if (selectedPhotoId === id) setSelectedPhotoId(null);
  };

  // photos not yet assigned to anything
  const assignedIds = React.useMemo(() => {
    const s = new Set<string>();
    for (const ids of Object.values(assignments)) {
      for (const id of ids) s.add(id);
    }
    return s;
  }, [assignments]);

  const unassignedPhotos = photos.filter((p) => !assignedIds.has(p.id));

  const handlePhotoTap = (id: string) => {
    setSelectedPhotoId((cur) => (cur === id ? null : id));
  };

  const handleDraftTap = (draftId: string) => {
    if (!selectedPhotoId) return;
    setAssignments((prev) => {
      const cur = prev[draftId] || [];
      if (cur.includes(selectedPhotoId)) return prev;
      return { ...prev, [draftId]: [...cur, selectedPhotoId] };
    });
    setSelectedPhotoId(null);
  };

  const handleUnassign = (draftId: string, photoId: string) => {
    setAssignments((prev) => {
      const cur = prev[draftId] || [];
      const next = cur.filter((x) => x !== photoId);
      const out = { ...prev };
      if (next.length === 0) delete out[draftId];
      else out[draftId] = next;
      return out;
    });
  };

  const handleAutoAssign = () => {
    setAssignments((prev) => {
      const next: Assignments = { ...prev };
      const used = new Set<string>();
      for (const ids of Object.values(next)) ids.forEach((id) => used.add(id));
      const pool = photos.filter((p) => !used.has(p.id));
      let i = 0;
      for (const d of drafts) {
        if (i >= pool.length) break;
        const cur = next[d.id] || [];
        next[d.id] = [...cur, pool[i].id];
        i += 1;
      }
      return next;
    });
    setSelectedPhotoId(null);
  };

  const totalAssigned = Object.values(assignments).reduce(
    (sum, ids) => sum + ids.length,
    0,
  );

  const allUploaded =
    photos.length > 0 &&
    photos.every((p) => !!p.fileId && !p.uploading && !p.error);
  const anyUploading = photos.some((p) => p.uploading);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const photoMap = new Map(photos.map((p) => [p.id, p]));
      const payload: Array<{ product_id: string; images: ProductImageIn[] }> =
        [];
      for (const [draftId, ids] of Object.entries(assignments)) {
        const images: ProductImageIn[] = ids
          .map((id) => photoMap.get(id))
          .filter((x): x is StagedPhoto => !!x && !!x.fileId)
          .map((p) => ({
            filename: p.filename,
            file_id: p.fileId as string,
          }));
        if (images.length > 0) {
          payload.push({ product_id: draftId, images });
        }
      }
      return api.post<BulkImagesResponse>(`/products/bulk/images`, {
        assignments: payload,
      });
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast({
        title: `${formatNumberFa(res.attached)} عکس به محصولات اضافه شد`,
      });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const e = err as ApiErrorShape;
      toast({
        title: "خطا در ذخیره عکس‌ها",
        description: e?.message || "مشکلی پیش آمد.",
        variant: "destructive",
      });
    },
  });

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="h-[92vh]">
        <DrawerHeader className="pb-2">
          <DrawerTitle>افزودن دسته‌ای عکس</DrawerTitle>
          <DrawerDescription>
            عکس‌ها را انتخاب کن و بعد به پیش‌نویس‌ها اختصاص بده.
          </DrawerDescription>
        </DrawerHeader>

        <div className="flex flex-col flex-1 min-h-0 px-4 pb-4 gap-3">
          {step === 1 ? (
            <Step1Pick
              photos={photos}
              onAdd={() => fileRef.current?.click()}
              onRemove={removePhoto}
              onRetry={retryPhoto}
              onNext={() => setStep(2)}
              canProceed={allUploaded}
              anyUploading={anyUploading}
            />
          ) : (
            <Step2Assign
              photos={photos}
              unassignedPhotos={unassignedPhotos}
              drafts={drafts}
              assignments={assignments}
              selectedPhotoId={selectedPhotoId}
              onPhotoTap={handlePhotoTap}
              onDraftTap={handleDraftTap}
              onUnassign={handleUnassign}
              onAutoAssign={handleAutoAssign}
              onBack={() => setStep(1)}
              onSave={() => saveMutation.mutate()}
              saving={saveMutation.isPending}
              totalAssigned={totalAssigned}
              canSave={allUploaded}
            />
          )}
        </div>

        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={onPickGallery}
        />
      </DrawerContent>
    </Drawer>
  );
}

// ---------- Step 1 ----------

function Step1Pick({
  photos,
  onAdd,
  onRemove,
  onRetry,
  onNext,
  canProceed,
  anyUploading,
}: {
  photos: StagedPhoto[];
  onAdd: () => void;
  onRemove: (id: string) => void;
  onRetry: (id: string) => void;
  onNext: () => void;
  canProceed: boolean;
  anyUploading: boolean;
}) {
  return (
    <>
      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-3">
        <button
          type="button"
          onClick={onAdd}
          className="border-2 border-dashed border-neutral-300 rounded-xl py-10 flex flex-col items-center justify-center gap-2 hover:bg-neutral-50"
        >
          <ImagePlus className="h-8 w-8 text-neutral-400" />
          <div className="text-sm font-medium text-neutral-800">
            انتخاب عکس از گالری
          </div>
          <div className="text-[11px] text-neutral-500">
            می‌تونی چند عکس را با هم انتخاب کنی
          </div>
        </button>

        {photos.length > 0 ? (
          <div className="flex flex-col gap-2">
            <div className="text-xs text-muted-foreground">
              {formatNumberFa(photos.length)} عکس انتخاب شده
            </div>
            <div className="grid grid-cols-4 sm:grid-cols-5 gap-2">
              {photos.map((p) => (
                <div
                  key={p.id}
                  className="relative aspect-square rounded-md overflow-hidden border bg-muted"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={p.previewUrl}
                    alt={p.filename}
                    className="h-full w-full object-cover"
                  />
                  {p.uploading ? (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                      <Loader2 className="h-5 w-5 animate-spin text-white" />
                    </div>
                  ) : p.error ? (
                    <button
                      type="button"
                      onClick={() => onRetry(p.id)}
                      className="absolute inset-0 flex items-center justify-center bg-rose-600/70 text-white"
                      aria-label="تلاش مجدد"
                      title={p.error}
                    >
                      <RotateCw className="h-5 w-5" />
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => onRemove(p.id)}
                    className="absolute top-1 left-1 h-6 w-6 inline-flex items-center justify-center rounded-full bg-black/70 text-white"
                    aria-label="حذف عکس"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="flex items-center justify-end gap-2 pt-2 border-t">
        <Button
          type="button"
          size="sm"
          onClick={onNext}
          disabled={photos.length === 0 || !canProceed}
        >
          {anyUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          <span>{anyUploading ? "در حال آپلود..." : "بعدی"}</span>
          {!anyUploading ? <ArrowLeft className="h-4 w-4" /> : null}
        </Button>
      </div>
    </>
  );
}

// ---------- Step 2 ----------

function Step2Assign({
  photos,
  unassignedPhotos,
  drafts,
  assignments,
  selectedPhotoId,
  onPhotoTap,
  onDraftTap,
  onUnassign,
  onAutoAssign,
  onBack,
  onSave,
  saving,
  totalAssigned,
  canSave,
}: {
  photos: StagedPhoto[];
  unassignedPhotos: StagedPhoto[];
  drafts: ProductListItem[];
  assignments: Assignments;
  selectedPhotoId: string | null;
  onPhotoTap: (id: string) => void;
  onDraftTap: (draftId: string) => void;
  onUnassign: (draftId: string, photoId: string) => void;
  onAutoAssign: () => void;
  onBack: () => void;
  onSave: () => void;
  saving: boolean;
  totalAssigned: number;
  canSave: boolean;
}) {
  const photoMap = React.useMemo(
    () => new Map(photos.map((p) => [p.id, p])),
    [photos],
  );

  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs text-muted-foreground">
          {selectedPhotoId
            ? "یک پیش‌نویس را انتخاب کن تا عکس به آن اضافه شود"
            : "روی یک عکس بزن، بعد روی پیش‌نویس مقصد بزن"}
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onAutoAssign}
          disabled={unassignedPhotos.length === 0 || drafts.length === 0}
        >
          <Sparkles className="h-4 w-4" />
          <span>اختصاص خودکار</span>
        </Button>
      </div>

      {/* Unassigned strip */}
      <div className="rounded-md border bg-neutral-50 p-2">
        <div className="text-[11px] text-muted-foreground mb-1.5">
          عکس‌های بدون مقصد ({formatNumberFa(unassignedPhotos.length)})
        </div>
        {unassignedPhotos.length === 0 ? (
          <div className="text-[11px] text-neutral-400 py-2 text-center">
            همه عکس‌ها اختصاص داده شدند
          </div>
        ) : (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {unassignedPhotos.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onPhotoTap(p.id)}
                className={cn(
                  "shrink-0 relative h-16 w-16 rounded-md overflow-hidden border-2",
                  selectedPhotoId === p.id
                    ? "border-primary ring-2 ring-primary/30"
                    : "border-transparent",
                )}
                aria-label="انتخاب عکس"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={p.previewUrl}
                  alt=""
                  className="h-full w-full object-cover"
                />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Drafts list */}
      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-2">
        {drafts.map((d) => {
          const ids = assignments[d.id] || [];
          const hasExisting = !!d.primary_image_url;
          const isTarget = !!selectedPhotoId;
          return (
            <button
              key={d.id}
              type="button"
              onClick={() => onDraftTap(d.id)}
              disabled={!isTarget}
              className={cn(
                "text-right rounded-md border bg-white p-2.5 flex items-start gap-2 transition-colors",
                isTarget
                  ? "border-primary/40 hover:bg-primary/5 cursor-pointer"
                  : "border-neutral-200 cursor-default",
              )}
            >
              <div className="shrink-0">
                {hasExisting ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={d.primary_image_url ?? undefined}
                    alt={d.name || ""}
                    className="h-12 w-12 rounded-md object-cover bg-neutral-100"
                  />
                ) : (
                  <div className="h-12 w-12 rounded-md bg-amber-100/60 border border-dashed border-amber-300 flex items-center justify-center">
                    <ImagePlus className="h-4 w-4 text-amber-500" />
                  </div>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-neutral-900 line-clamp-1">
                  {d.name || "بدون نام"}
                </div>
                {d.category_title ? (
                  <div className="text-[11px] text-neutral-500 line-clamp-1">
                    {d.category_title}
                  </div>
                ) : null}
                {ids.length > 0 ? (
                  <div className="mt-1.5 flex gap-1 flex-wrap">
                    {ids.map((pid) => {
                      const p = photoMap.get(pid);
                      if (!p) return null;
                      return (
                        <div
                          key={pid}
                          className="relative h-10 w-10 rounded overflow-hidden border bg-muted"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={p.previewUrl}
                            alt=""
                            className="h-full w-full object-cover"
                          />
                          <span
                            role="button"
                            tabIndex={0}
                            onClick={(e) => {
                              e.stopPropagation();
                              onUnassign(d.id, pid);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                e.stopPropagation();
                                onUnassign(d.id, pid);
                              }
                            }}
                            className="absolute top-0 left-0 h-4 w-4 inline-flex items-center justify-center rounded-br bg-black/70 text-white cursor-pointer"
                            aria-label="حذف اختصاص"
                          >
                            <X className="h-2.5 w-2.5" />
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between gap-2 pt-2 border-t">
        <Button type="button" variant="outline" size="sm" onClick={onBack} disabled={saving}>
          <ArrowRight className="h-4 w-4" />
          <span>بازگشت</span>
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={onSave}
          disabled={saving || totalAssigned === 0 || !canSave}
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          <span>
            تأیید و ذخیره ({formatNumberFa(totalAssigned)})
          </span>
        </Button>
      </div>
    </>
  );
}
