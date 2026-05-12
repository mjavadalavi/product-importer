"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { X, Camera, Upload, Loader2, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import type {
  ProductCreatedResponse,
  ProductCreateRequest,
  ProductImageIn,
} from "@/lib/api";
import { uid } from "@/lib/format";
import { uploadFile } from "@/lib/api/files";
import { InsufficientBalanceDialog } from "@/components/insufficient-balance-dialog";
import { TopupDialog } from "@/components/topup-dialog";

type SessionImage = {
  id: string;
  previewUrl: string; // object URL or data URL just for thumbnail rendering
  filename: string;
  file: File;
  fileId: string | null;
  uploading: boolean;
  error: string | null;
};

export default function CameraPage() {
  const router = useRouter();
  const { toast } = useToast();

  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const streamRef = React.useRef<MediaStream | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const [sessionImages, setSessionImages] = React.useState<SessionImage[]>([]);
  const [description, setDescription] = React.useState<string>("");
  const [popoverOpen, setPopoverOpen] = React.useState<boolean>(false);
  const [cameraError, setCameraError] = React.useState<string | null>(null);

  const [insufficientOpen, setInsufficientOpen] = React.useState<boolean>(false);
  const [requiredAmount, setRequiredAmount] = React.useState<number>(0);
  const [availableAmount, setAvailableAmount] = React.useState<number>(0);
  const [topupOpen, setTopupOpen] = React.useState<boolean>(false);

  React.useEffect(() => {
    let cancelled = false;

    async function start() {
      if (
        typeof navigator === "undefined" ||
        !navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia
      ) {
        setCameraError("دوربین در این مرورگر در دسترس نیست");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        const message =
          (err as { message?: string })?.message ||
          "دسترسی به دوربین امکان‌پذیر نیست";
        setCameraError(message);
      }
    }

    start();

    return () => {
      cancelled = true;
      const stream = streamRef.current;
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
    };
  }, []);

  // Track object URLs created with URL.createObjectURL so we can revoke them on unmount.
  const objectUrlsRef = React.useRef<string[]>([]);
  React.useEffect(() => {
    return () => {
      objectUrlsRef.current.forEach((u) => URL.revokeObjectURL(u));
      objectUrlsRef.current = [];
    };
  }, []);

  const startUploadFor = React.useCallback((entry: SessionImage) => {
    setSessionImages((prev) =>
      prev.map((s) =>
        s.id === entry.id ? { ...s, uploading: true, error: null } : s,
      ),
    );
    uploadFile(entry.file, { kind: "product_image" })
      .then((res) => {
        setSessionImages((prev) =>
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
        setSessionImages((prev) =>
          prev.map((s) =>
            s.id === entry.id ? { ...s, uploading: false, error: msg } : s,
          ),
        );
      });
  }, []);

  const addAndUpload = React.useCallback(
    (file: File, baseFilename: string) => {
      const id = uid();
      const previewUrl = URL.createObjectURL(file);
      objectUrlsRef.current.push(previewUrl);
      const entry: SessionImage = {
        id,
        previewUrl,
        filename: baseFilename,
        file,
        fileId: null,
        uploading: false,
        error: null,
      };
      setSessionImages((prev) => [...prev, entry]);
      startUploadFor(entry);
    },
    [startUploadFor],
  );

  const handleCapture = React.useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) return;
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, width, height);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const filename = `capture-${Date.now()}.jpg`;
        const file = new File([blob], filename, { type: "image/jpeg" });
        addAndUpload(file, filename);
        setPopoverOpen(true);
      },
      "image/jpeg",
      0.9,
    );
  }, [addAndUpload]);

  const handlePickFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      addAndUpload(f, f.name || `upload-${uid()}.jpg`);
    }
    setPopoverOpen(true);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRetry = (id: string) => {
    const entry = sessionImages.find((s) => s.id === id);
    if (entry) startUploadFor(entry);
  };

  const allUploaded =
    sessionImages.length > 0 &&
    sessionImages.every((s) => !!s.fileId && !s.uploading && !s.error);
  const anyUploading = sessionImages.some((s) => s.uploading);
  const anyFailed = sessionImages.some((s) => !!s.error);

  const submit = useMutation({
    mutationFn: () => {
      const images: ProductImageIn[] = sessionImages
        .filter((i) => !!i.fileId)
        .map((i) => ({ filename: i.filename, file_id: i.fileId as string }));
      const payload: ProductCreateRequest = {
        description: description || null,
        images,
      };
      return api.post<ProductCreatedResponse>("/products", payload);
    },
    onSuccess: () => {
      setSessionImages([]);
      setDescription("");
      setPopoverOpen(false);
      toast({
        title: "محصول در حال پردازش است",
        description: "می‌تونی محصول بعدی رو شروع کنی.",
      });
    },
    onError: (err: unknown) => {
      const e = err as {
        status?: number;
        message?: string;
        detail?: { required?: number; available?: number };
      };
      if (e?.status === 402) {
        const req = e.detail?.required ?? 1;
        const av = e.detail?.available ?? 0;
        setRequiredAmount(req);
        setAvailableAmount(av);
        setInsufficientOpen(true);
      } else {
        toast({
          title: "خطا در ساخت محصول",
          description: e?.message || "دوباره امتحان کن",
          variant: "destructive",
        });
      }
    },
  });

  const handleSubmit = () => {
    if (sessionImages.length === 0) {
      toast({
        title: "عکسی ثبت نشده",
        description: "حداقل یک عکس بگیر.",
        variant: "destructive",
      });
      return;
    }
    if (anyUploading) {
      toast({
        title: "صبر کن آپلود تموم بشه",
        variant: "destructive",
      });
      return;
    }
    if (anyFailed) {
      toast({
        title: "آپلود بعضی عکس‌ها ناموفق بود",
        description: "روی دکمه تلاش مجدد بزن یا عکس‌های خطادار رو حذف کن.",
        variant: "destructive",
      });
      return;
    }
    if (!allUploaded) return;
    submit.mutate();
  };

  const handleClearProduct = () => {
    setSessionImages([]);
    setDescription("");
    setPopoverOpen(false);
  };

  const handleClose = () => {
    router.push("/home");
  };

  if (cameraError) {
    return (
      <div className="fixed inset-0 flex flex-col items-center justify-center bg-black p-6 text-center">
        <Camera className="mb-4 h-12 w-12 text-white/70" />
        <h2 className="mb-2 text-lg font-semibold">دسترسی به دوربین ممکن نشد</h2>
        <p className="mb-6 max-w-xs text-sm text-white/70">{cameraError}</p>
        <div className="flex flex-col gap-3">
          <Button
            variant="secondary"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="ml-2 h-4 w-4" />
            آپلود فایل
          </Button>
          <Button variant="outline" onClick={() => router.back()}>
            بازگشت
          </Button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={handlePickFiles}
        />
        {sessionImages.length > 0 ? (
          <div className="mt-6 w-full max-w-xs">
            <Card className="bg-background/90 p-3 text-foreground backdrop-blur space-y-3">
              <div className="flex gap-1 overflow-x-auto">
                {sessionImages.slice(-4).map((img) => (
                  <ThumbWithStatus
                    key={img.id}
                    image={img}
                    onRetry={() => handleRetry(img.id)}
                  />
                ))}
              </div>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="توضیح کوتاه (اختیاری)"
                rows={2}
              />
              <Button
                className="w-full"
                onClick={handleSubmit}
                disabled={submit.isPending || !allUploaded}
              >
                {anyUploading
                  ? "در حال آپلود عکس‌ها..."
                  : "اتمام و محصول جدید"}
              </Button>
            </Card>
          </div>
        ) : null}
        <InsufficientBalanceDialog
          open={insufficientOpen}
          onOpenChange={setInsufficientOpen}
          required={requiredAmount}
          available={availableAmount}
          onTopup={() => setTopupOpen(true)}
        />
        <TopupDialog open={topupOpen} onOpenChange={setTopupOpen} />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="absolute inset-0 h-full w-full object-cover"
      />

      <Button
        variant="ghost"
        size="icon"
        onClick={handleClose}
        aria-label="بستن"
        className="absolute left-4 top-4 z-20 text-white hover:bg-white/10 hover:text-white"
      >
        <X className="h-6 w-6" />
      </Button>

      {sessionImages.length > 0 ? (
        <div className="pointer-events-none absolute left-1/2 top-4 z-20 -translate-x-1/2 rounded-full bg-black/50 px-3 py-1 text-xs text-white backdrop-blur">
          {sessionImages.length} عکس
        </div>
      ) : null}

      {popoverOpen && sessionImages.length > 0 ? (
        <div className="absolute right-4 top-4 z-20 w-[18rem] max-w-[80vw]">
          <Card className="max-w-xs space-y-3 bg-background/90 p-3 text-foreground backdrop-blur">
            <div className="flex gap-1 overflow-x-auto">
              {sessionImages.slice(-4).map((img) => (
                <ThumbWithStatus
                  key={img.id}
                  image={img}
                  onRetry={() => handleRetry(img.id)}
                />
              ))}
            </div>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="توضیح کوتاه (اختیاری)"
              rows={2}
            />
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPopoverOpen(false)}
                className="flex-1"
              >
                + عکس بیشتر
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleClearProduct}
                className="flex-1"
              >
                حذف محصول
              </Button>
            </div>
            <Button
              className="w-full"
              onClick={handleSubmit}
              disabled={submit.isPending || !allUploaded}
            >
              {submit.isPending
                ? "در حال ارسال..."
                : anyUploading
                  ? "در حال آپلود عکس‌ها..."
                  : "اتمام و محصول جدید"}
            </Button>
          </Card>
        </div>
      ) : null}

      <div className="absolute bottom-8 left-1/2 z-20 -translate-x-1/2">
        <Button
          size="icon"
          onClick={handleCapture}
          aria-label="گرفتن عکس"
          className="h-20 w-20 rounded-full border-4 border-white bg-white/20 hover:bg-white/30"
        />
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={handlePickFiles}
      />

      <InsufficientBalanceDialog
        open={insufficientOpen}
        onOpenChange={setInsufficientOpen}
        required={requiredAmount}
        available={availableAmount}
        onTopup={() => setTopupOpen(true)}
      />
      <TopupDialog open={topupOpen} onOpenChange={setTopupOpen} />
    </div>
  );
}

function ThumbWithStatus({
  image,
  onRetry,
}: {
  image: SessionImage;
  onRetry: () => void;
}) {
  return (
    <div className="relative h-12 w-12 shrink-0 rounded overflow-hidden bg-muted">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={image.previewUrl}
        alt={image.filename}
        className="h-full w-full object-cover"
      />
      {image.uploading ? (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40">
          <Loader2 className="h-4 w-4 animate-spin text-white" />
        </div>
      ) : image.error ? (
        <button
          type="button"
          onClick={onRetry}
          className="absolute inset-0 flex items-center justify-center bg-rose-600/70 text-white"
          aria-label="تلاش مجدد"
          title={image.error}
        >
          <RotateCw className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}
