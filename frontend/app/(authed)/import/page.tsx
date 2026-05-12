"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Check,
  Upload,
  FileSpreadsheet,
  FileArchive,
  X,
  AlertCircle,
  Info,
  Loader2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { useUploadFile } from "@/hooks/use-upload-file";
import type { UploadedFile } from "@/lib/api/files";
import { api } from "@/lib/api";
import { formatNumberFa } from "@/lib/format";
import { cn } from "@/lib/utils";

// ----- Types -----

type BulkSaveDraftsResponse = {
  created: Array<{ product_id: string; row_index: number }>;
};

type UploadedFileSummary = {
  id: string;
  filename: string;
  size_bytes: number;
};

// ----- Helpers -----

const SHEET_ACCEPT = ".xlsx,.xls,.csv";
const ZIP_ACCEPT = ".zip,application/zip,application/x-zip-compressed";

function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return "0";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let u = 0;
  while (v >= 1024 && u < units.length - 1) {
    v /= 1024;
    u += 1;
  }
  const fixed = u === 0 ? v.toFixed(0) : v.toFixed(1);
  return `${formatNumberFa(fixed)} ${units[u]}`;
}

function toSummary(f: UploadedFile): UploadedFileSummary {
  return { id: f.id, filename: f.filename, size_bytes: f.size_bytes };
}

// ----- Main page -----

export default function ImportPage() {
  const router = useRouter();
  const { toast } = useToast();

  const sheetUpload = useUploadFile();
  const zipUpload = useUploadFile();

  const [sheetFile, setSheetFile] = React.useState<UploadedFileSummary | null>(
    null,
  );
  const [zipFile, setZipFile] = React.useState<UploadedFileSummary | null>(null);

  const [submitting, setSubmitting] = React.useState(false);
  const [submitErrors, setSubmitErrors] = React.useState<string[]>([]);

  const isBusy =
    submitting || sheetUpload.isUploading || zipUpload.isUploading;

  const handlePickSheet = async (file: File) => {
    if (sheetUpload.isUploading) return;
    setSubmitErrors([]);
    try {
      const res = await sheetUpload.uploadAsync({
        file,
        meta: { kind: "bulk_sheet" },
      });
      setSheetFile(toSummary(res));
    } catch (err) {
      const msg =
        (err as { message?: string })?.message ||
        "خطا در بارگذاری فایل شیت";
      toast({
        title: "ناتوان در بارگذاری فایل شیت",
        description: msg,
        variant: "destructive",
      });
    }
  };

  const handlePickZip = async (file: File) => {
    if (zipUpload.isUploading) return;
    setSubmitErrors([]);
    try {
      const res = await zipUpload.uploadAsync({
        file,
        meta: { kind: "bulk_zip" },
      });
      setZipFile(toSummary(res));
    } catch (err) {
      const msg =
        (err as { message?: string })?.message ||
        "خطا در بارگذاری فایل ZIP";
      toast({
        title: "ناتوان در بارگذاری فایل ZIP",
        description: msg,
        variant: "destructive",
      });
    }
  };

  const removeSheet = () => {
    if (sheetUpload.isUploading || submitting) return;
    setSheetFile(null);
  };

  const removeZip = () => {
    if (zipUpload.isUploading || submitting) return;
    setZipFile(null);
  };

  const onConfirm = async () => {
    if (submitting || !sheetFile) return;
    setSubmitting(true);
    setSubmitErrors([]);
    try {
      const res = await api.post<BulkSaveDraftsResponse>(
        "/products/bulk/save-drafts-from-files",
        {
          sheet_file_id: sheetFile.id,
          zip_file_id: zipFile?.id ?? null,
        },
      );
      toast({
        title: `${formatNumberFa(res.created.length)} پیش‌نویس ذخیره شد`,
      });
      router.push("/home");
    } catch (err) {
      const e = err as { message?: string; detail?: unknown };
      const errs: string[] = [];
      if (Array.isArray(e?.detail)) {
        for (const d of e.detail as Array<Record<string, unknown>>) {
          if (typeof d?.message === "string") errs.push(d.message as string);
          else if (typeof d?.msg === "string") errs.push(d.msg as string);
          else errs.push(JSON.stringify(d));
        }
      } else if (typeof e?.message === "string") {
        errs.push(e.message);
      } else {
        errs.push("خطا در ذخیره پیش‌نویس‌ها");
      }
      setSubmitErrors(errs);
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = !!sheetFile && !isBusy;

  return (
    <main className="px-4 py-4 max-w-3xl mx-auto flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/home">
            <ArrowLeft className="h-4 w-4" />
            <span>بازگشت به خانه</span>
          </Link>
        </Button>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <FileSpreadsheet className="h-4 w-4" />
          <span>ورود گروهی محصولات</span>
        </div>
      </div>

      <Card className="p-5 flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-base font-semibold">۱. آپلود فایل اکسل</h1>
          <p className="text-xs text-muted-foreground leading-6">
            یک فایل با پسوند xlsx، xls یا csv انتخاب کن. اولین شیت به‌عنوان داده
            خوانده می‌شود و ردیف اول هدر در نظر گرفته می‌شود. ستون‌ها به‌صورت
            خودکار از روی عنوان شناسایی می‌شوند.
          </p>
        </div>

        <FilePickerBox
          accept={SHEET_ACCEPT}
          uploading={sheetUpload.isUploading}
          disabled={isBusy && !sheetUpload.isUploading}
          file={sheetFile}
          onPick={handlePickSheet}
          onRemove={removeSheet}
          icon={<FileSpreadsheet className="h-8 w-8 text-muted-foreground" />}
          uploadingLabel="در حال بارگذاری فایل..."
          idleLabel="فایل را اینجا رها کن یا کلیک کن"
          hintLabel="پسوندهای مجاز: xlsx، xls، csv"
        />
      </Card>

      <Card className="p-5 flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-base font-semibold">
            ۲. آپلود ZIP عکس‌ها (اختیاری)
          </h2>
          <p className="text-xs text-muted-foreground leading-6">
            این فایل باید شامل پوشه‌ی <code className="font-mono">images/</code>{" "}
            باشد و نام فایل‌های هر ردیف باید با ستون «نام فایل عکس‌ها در ZIP» در
            شیت مطابقت داشته باشد.
          </p>
        </div>

        <FilePickerBox
          accept={ZIP_ACCEPT}
          uploading={zipUpload.isUploading}
          disabled={isBusy && !zipUpload.isUploading}
          file={zipFile}
          onPick={handlePickZip}
          onRemove={removeZip}
          icon={<FileArchive className="h-8 w-8 text-muted-foreground" />}
          uploadingLabel="در حال بارگذاری ZIP..."
          idleLabel="فایل ZIP را اینجا رها کن یا کلیک کن"
          hintLabel="پسوند مجاز: zip"
        />
      </Card>

      <Card className="p-5 flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-base font-semibold">۳. تأیید و ذخیره</h2>
          <p className="text-xs text-muted-foreground leading-6">
            با تأیید نهایی، شیت روی سرور پردازش می‌شود و هر ردیف به‌صورت
            پیش‌نویس ذخیره می‌گردد. ثبت نهایی روی باسلام بعد از تأیید در صفحه‌ی
            خانه انجام می‌شه.
          </p>
        </div>

        <div className="rounded-md border border-amber-200 bg-amber-50 text-amber-900 p-3 text-xs leading-6 flex items-start gap-1.5">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <span>
            نگاشت ستون‌ها به‌صورت خودکار از روی عنوان ستون و نام‌های جایگزین
            انجام می‌شود. اگر ستونی شناسایی نشد، عنوان آن را در شیت اصلاح کن.
          </span>
        </div>

        {submitErrors.length > 0 ? (
          <div className="rounded-md border border-rose-200 bg-rose-50 text-rose-800 p-3 text-xs leading-6 flex flex-col gap-1">
            <div className="font-semibold flex items-center gap-1.5">
              <AlertCircle className="h-4 w-4" />
              خطا در ذخیره
            </div>
            <ul className="list-disc pr-4">
              {submitErrors.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <Button
          size="lg"
          onClick={onConfirm}
          disabled={!canSubmit}
          className="w-full"
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          <span>
            {submitting
              ? "در حال ذخیره..."
              : sheetUpload.isUploading || zipUpload.isUploading
                ? "در انتظار اتمام بارگذاری..."
                : "ثبت و ذخیره پیش‌نویس‌ها"}
          </span>
        </Button>
      </Card>
    </main>
  );
}

// ----- File picker box -----

function FilePickerBox({
  accept,
  uploading,
  disabled,
  file,
  onPick,
  onRemove,
  icon,
  uploadingLabel,
  idleLabel,
  hintLabel,
}: {
  accept: string;
  uploading: boolean;
  disabled: boolean;
  file: UploadedFileSummary | null;
  onPick: (f: File) => void;
  onRemove: () => void;
  icon: React.ReactNode;
  uploadingLabel: string;
  idleLabel: string;
  hintLabel: string;
}) {
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = React.useState(false);

  const blocked = disabled || uploading;

  const triggerPick = () => {
    if (blocked) return;
    inputRef.current?.click();
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (blocked) return;
    const f = e.dataTransfer.files?.[0];
    if (f) onPick(f);
  };

  if (file && !uploading) {
    return (
      <div className="rounded-xl border bg-muted/30 p-4 flex items-center gap-3">
        <div className="shrink-0">{icon}</div>
        <div className="flex-1 min-w-0 flex flex-col gap-0.5">
          <div className="text-sm font-medium truncate">{file.filename}</div>
          <div className="text-xs text-muted-foreground">
            {formatBytes(file.size_bytes)}
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          disabled={disabled}
          className="text-rose-600 hover:text-rose-700 shrink-0"
          aria-label="حذف فایل"
        >
          <X className="h-4 w-4" />
          <span>حذف</span>
        </Button>
      </div>
    );
  }

  return (
    <div
      onClick={triggerPick}
      onDragOver={(e) => {
        e.preventDefault();
        if (!blocked) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      className={cn(
        "border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center gap-3 transition-colors",
        blocked
          ? "opacity-60 cursor-not-allowed border-muted-foreground/30"
          : "cursor-pointer",
        !blocked && dragOver
          ? "border-primary bg-primary/5"
          : !blocked
            ? "border-muted-foreground/30 hover:bg-muted/40"
            : "",
      )}
      aria-disabled={blocked}
    >
      {uploading ? (
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      ) : (
        <Upload className="h-8 w-8 text-muted-foreground" />
      )}
      <div className="text-sm font-medium">
        {uploading ? uploadingLabel : idleLabel}
      </div>
      <div className="text-xs text-muted-foreground">{hintLabel}</div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        disabled={blocked}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
          if (inputRef.current) inputRef.current.value = "";
        }}
      />
    </div>
  );
}
