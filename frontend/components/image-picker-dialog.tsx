"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, ImagePlus, Loader2, RotateCw, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { api, type ProductImageIn, type ProductOut } from "@/lib/api";
import { uploadFile } from "@/lib/api/files";
import { formatNumberFa, uid } from "@/lib/format";

type StagedImage = {
  id: string;
  filename: string;
  previewUrl: string;
  file: File;
  fileId: string | null;
  uploading: boolean;
  error: string | null;
};

type ApiErrorShape = {
  status?: number;
  message?: string;
  detail?: unknown;
};

export function ImagePickerDialog({
  open,
  onOpenChange,
  productId,
  onUploaded,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  productId: string;
  onUploaded?: (product: ProductOut) => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const fileRef = React.useRef<HTMLInputElement | null>(null);
  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const streamRef = React.useRef<MediaStream | null>(null);

  const [staged, setStaged] = React.useState<StagedImage[]>([]);
  const [camOpen, setCamOpen] = React.useState(false);
  const [camError, setCamError] = React.useState<string | null>(null);

  const stopCam = React.useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setCamOpen(false);
  }, []);

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
      stopCam();
      setStaged([]);
      setCamError(null);
      objectUrlsRef.current.forEach((u) => URL.revokeObjectURL(u));
      objectUrlsRef.current = [];
    }
    return () => stopCam();
  }, [open, stopCam]);

  const startUploadFor = React.useCallback((entry: StagedImage) => {
    setStaged((prev) =>
      prev.map((s) =>
        s.id === entry.id ? { ...s, uploading: true, error: null } : s,
      ),
    );
    uploadFile(entry.file, { kind: "product_image" })
      .then((res) => {
        setStaged((prev) =>
          prev.map((s) =>
            s.id === entry.id
              ? { ...s, uploading: false, fileId: res.id, error: null }
              : s,
          ),
        );
      })
      .catch((err: unknown) => {
        const msg =
          (err as { message?: string })?.message || "آپلود ناموفق بود";
        setStaged((prev) =>
          prev.map((s) =>
            s.id === entry.id ? { ...s, uploading: false, error: msg } : s,
          ),
        );
      });
  }, []);

  const addStaged = React.useCallback(
    (file: File, filename: string) => {
      const previewUrl = URL.createObjectURL(file);
      objectUrlsRef.current.push(previewUrl);
      const entry: StagedImage = {
        id: uid(),
        filename,
        previewUrl,
        file,
        fileId: null,
        uploading: false,
        error: null,
      };
      setStaged((s) => [...s, entry]);
      startUploadFor(entry);
    },
    [startUploadFor],
  );

  const startCam = async () => {
    setCamError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      setCamOpen(true);
      requestAnimationFrame(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => undefined);
        }
      });
    } catch (e) {
      const msg =
        (e as { message?: string })?.message || "دسترسی به دوربین رد شد";
      setCamError(msg);
    }
  };

  const capture = () => {
    const v = videoRef.current;
    if (!v) return;
    const w = v.videoWidth || 1280;
    const h = v.videoHeight || 720;
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(v, 0, 0, w, h);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const filename = `camera-${Date.now()}.jpg`;
        const file = new File([blob], filename, { type: "image/jpeg" });
        addStaged(file, filename);
      },
      "image/jpeg",
      0.9,
    );
  };

  const onPickGallery = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    for (const f of files) {
      addStaged(f, f.name);
    }
    if (fileRef.current) fileRef.current.value = "";
  };

  const removeOne = (id: string) => {
    setStaged((s) => s.filter((i) => i.id !== id));
  };

  const retryOne = (id: string) => {
    const entry = staged.find((s) => s.id === id);
    if (entry) startUploadFor(entry);
  };

  const allUploaded =
    staged.length > 0 &&
    staged.every((s) => !!s.fileId && !s.uploading && !s.error);
  const anyUploading = staged.some((s) => s.uploading);

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const images: ProductImageIn[] = staged
        .filter((s) => !!s.fileId)
        .map((s) => ({
          filename: s.filename,
          file_id: s.fileId as string,
        }));
      return api.post<ProductOut>(`/products/${productId}/images`, { images });
    },
    onSuccess: (product) => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["product", productId] });
      toast({
        title: `${formatNumberFa(staged.length)} عکس اضافه شد`,
      });
      onUploaded?.(product);
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const e = err as ApiErrorShape;
      toast({
        title: "خطا در افزودن عکس",
        description: e?.message || "مشکلی پیش آمد.",
        variant: "destructive",
      });
    },
  });

  const handleConfirm = () => {
    if (staged.length === 0) return;
    if (!allUploaded) return;
    uploadMutation.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>افزودن عکس</DialogTitle>
          <DialogDescription>
            می‌تونی هم‌زمان چندتا عکس انتخاب کنی یا چند بار اضافه کنی.
          </DialogDescription>
        </DialogHeader>

        {camOpen ? (
          <div className="flex flex-col gap-3">
            <div className="rounded-md overflow-hidden bg-black">
              <video
                ref={videoRef}
                playsInline
                muted
                className="w-full h-auto"
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <Button variant="outline" size="sm" onClick={stopCam}>
                بستن دوربین
              </Button>
              <Button size="sm" onClick={capture}>
                <Camera className="h-4 w-4" />
                <span>گرفتن عکس</span>
              </Button>
            </div>
            {staged.length > 0 ? (
              <p className="text-[11px] text-muted-foreground text-center">
                می‌تونی چند عکس پشت سر هم بگیری
              </p>
            ) : null}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => fileRef.current?.click()}
              disabled={uploadMutation.isPending}
              className="h-auto py-3 flex flex-col items-center gap-1"
            >
              <ImagePlus className="h-5 w-5" />
              <span className="text-sm">از گالری</span>
              <span className="text-[10px] text-muted-foreground">
                چند عکس همزمان
              </span>
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={startCam}
              disabled={uploadMutation.isPending}
              className="h-auto py-3 flex flex-col items-center gap-1"
            >
              <Camera className="h-5 w-5" />
              <span className="text-sm">از دوربین</span>
              <span className="text-[10px] text-muted-foreground">
                یکی یکی بگیر
              </span>
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={onPickGallery}
            />
          </div>
        )}

        {camError ? (
          <div className="text-xs text-rose-600 leading-5">{camError}</div>
        ) : null}

        {/* Staged area — always visible so the user understands they can stack photos */}
        <div className="flex flex-col gap-2 mt-1">
          <div className="text-xs font-medium text-neutral-700 flex items-center justify-between">
            <span>
              {staged.length > 0
                ? `${formatNumberFa(staged.length)} عکس انتخاب شده`
                : "هنوز عکسی اضافه نکردی"}
            </span>
            {staged.length > 0 && !camOpen ? (
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="text-[11px] text-primary hover:underline"
              >
                + افزودن بیشتر
              </button>
            ) : null}
          </div>
          {staged.length > 0 ? (
            <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto rounded-md border bg-neutral-50 p-2">
              {staged.map((img) => (
                <div
                  key={img.id}
                  className="relative h-16 w-16 rounded-md overflow-hidden border bg-muted"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={img.previewUrl}
                    alt={img.filename}
                    className="h-full w-full object-cover"
                  />
                  {img.uploading ? (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                      <Loader2 className="h-4 w-4 animate-spin text-white" />
                    </div>
                  ) : img.error ? (
                    <button
                      type="button"
                      onClick={() => retryOne(img.id)}
                      className="absolute inset-0 flex items-center justify-center bg-rose-600/70 text-white"
                      aria-label="تلاش مجدد"
                      title={img.error}
                    >
                      <RotateCw className="h-4 w-4" />
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => removeOne(img.id)}
                    disabled={uploadMutation.isPending}
                    className="absolute top-0.5 left-0.5 h-5 w-5 inline-flex items-center justify-center rounded-full bg-black/70 text-white"
                    aria-label="حذف عکس"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-md border border-dashed border-neutral-300 bg-neutral-50/50 p-3 text-center text-[11px] text-neutral-500">
              عکس‌های انتخاب‌شده اینجا نشون داده می‌شن. می‌تونی چندتایی انتخاب کنی.
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={uploadMutation.isPending}
          >
            انصراف
          </Button>
          <Button
            size="sm"
            onClick={handleConfirm}
            disabled={
              staged.length === 0 ||
              uploadMutation.isPending ||
              !allUploaded
            }
          >
            {uploadMutation.isPending || anyUploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            <span>
              {anyUploading
                ? "در حال آپلود..."
                : staged.length > 0
                  ? `تأیید (${formatNumberFa(staged.length)})`
                  : "تأیید"}
            </span>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
