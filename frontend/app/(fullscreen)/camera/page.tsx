"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { X, Camera, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import type {
  ProductCreatedResponse,
  ProductCreateRequest,
} from "@/lib/api";
import { uid, fileToDataUrl } from "@/lib/format";
import { InsufficientBalanceDialog } from "@/components/insufficient-balance-dialog";
import { TopupDialog } from "@/components/topup-dialog";

type SessionImage = {
  id: string;
  dataUrl: string;
  filename: string;
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
    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    const id = uid();
    setSessionImages((prev) => [
      ...prev,
      { id, dataUrl, filename: `capture-${id}.jpg` },
    ]);
    setPopoverOpen(true);
  }, []);

  const handlePickFiles = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const next: SessionImage[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      try {
        const dataUrl = await fileToDataUrl(f);
        const id = uid();
        next.push({ id, dataUrl, filename: f.name || `upload-${id}.jpg` });
      } catch {
        // skip files that fail to read
      }
    }
    if (next.length > 0) {
      setSessionImages((prev) => [...prev, ...next]);
      setPopoverOpen(true);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const submit = useMutation({
    mutationFn: () => {
      const payload: ProductCreateRequest = {
        description: description || null,
        images: sessionImages.map((i) => ({
          filename: i.filename,
          data_url: i.dataUrl,
        })),
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
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    key={img.id}
                    src={img.dataUrl}
                    alt={img.filename}
                    className="h-12 w-12 rounded object-cover"
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
                disabled={submit.isPending}
              >
                اتمام و محصول جدید
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
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={img.id}
                  src={img.dataUrl}
                  alt={img.filename}
                  className="h-12 w-12 rounded object-cover"
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
              disabled={submit.isPending}
            >
              {submit.isPending ? "در حال ارسال..." : "اتمام و محصول جدید"}
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
