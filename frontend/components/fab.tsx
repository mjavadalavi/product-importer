"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, FileSpreadsheet, Plus, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { useToast } from "@/hooks/use-toast";
import {
  api,
  type ProductCreateRequest,
  type ProductCreatedResponse,
  type ProductImageIn,
} from "@/lib/api";
import { uploadFile } from "@/lib/api/files";

type ApiErrorShape = {
  status?: number;
  message?: string;
  detail?: unknown;
};

export function FAB({
  onInsufficient,
}: {
  onInsufficient?: (required: number, available: number) => void;
}) {
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const [open, setOpen] = React.useState(false);

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      const uploaded = await Promise.all(
        files.map((file) =>
          uploadFile(file, { kind: "product_image" }).then((res) => ({
            filename: file.name,
            file_id: res.id,
          })),
        ),
      );
      const images: ProductImageIn[] = uploaded.map((u) => ({
        filename: u.filename,
        file_id: u.file_id,
      }));
      const body: ProductCreateRequest = { description: null, images };
      return api.post<ProductCreatedResponse>("/products", body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      setOpen(false);
      toast({
        title: "محصول در حال پردازش است",
      });
    },
    onError: (err: unknown) => {
      const e = err as ApiErrorShape;
      if (e?.status === 402) {
        const detail = (e.detail || {}) as {
          required?: number;
          available?: number;
        };
        setOpen(false);
        onInsufficient?.(detail.required ?? 0, detail.available ?? 0);
        return;
      }
      toast({
        title: "خطا در آپلود",
        description: e?.message || "مشکلی پیش آمد.",
        variant: "destructive",
      });
    },
  });

  const handleCamera = () => {
    setOpen(false);
    router.push("/camera");
  };

  const handlePickFile = () => {
    fileInputRef.current?.click();
  };

  const handleDownloadTemplate = async () => {
    try {
      const res = await fetch("/api/proxy/products/template", {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "basalam-products-template.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast({
        title: "نمونه دانلود شد",
        description: "فایل را پر کن و از همین بخش آپلود کن.",
      });
    } catch (err) {
      const message =
        (err as { message?: string })?.message || "خطا در دانلود نمونه";
      toast({
        title: "دانلود ناموفق بود",
        description: message,
        variant: "destructive",
      });
    }
  };

  const handleFilesChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    // reset input so same file can be re-selected later
    e.target.value = "";
    uploadMutation.mutate(files);
  };

  return (
    <>
      <Button
        type="button"
        size="icon"
        variant="default"
        aria-label="افزودن محصول"
        className="fixed bottom-20 left-4 z-30 h-14 w-14 rounded-full shadow-lg"
        onClick={() => setOpen(true)}
      >
        <Plus className="h-6 w-6" />
      </Button>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={handleFilesChange}
      />

      <Drawer open={open} onOpenChange={setOpen}>
        <DrawerContent>
          <DrawerHeader>
            <DrawerTitle>افزودن محصول</DrawerTitle>
            <DrawerDescription>
              یک روش ورود محصول انتخاب کن
            </DrawerDescription>
          </DrawerHeader>
          <div className="grid gap-2 p-4 pt-0">
            <Button
              type="button"
              variant="default"
              onClick={handleCamera}
              disabled={uploadMutation.isPending}
            >
              <Camera className="h-4 w-4" />
              <span>گرفتن عکس</span>
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handlePickFile}
              disabled={uploadMutation.isPending}
            >
              <Upload className="h-4 w-4" />
              <span>
                {uploadMutation.isPending
                  ? "در حال آپلود..."
                  : "آپلود عکس از گالری"}
              </span>
            </Button>
            <div className="my-1 h-px bg-neutral-200" />
            <div className="rounded-md bg-neutral-50 p-3 flex flex-col gap-2">
              <div className="text-xs font-medium text-neutral-700">
                ورود گروهی با اکسل
              </div>
              <p className="text-[11px] text-neutral-500 leading-5">
                می‌تونی چند محصول رو با یک فایل اکسل وارد کنی. اول نمونه رو
                دانلود کن، پر کن، و بعد آپلود کن.
              </p>
              <Button
                type="button"
                variant="secondary"
                onClick={handleDownloadTemplate}
                disabled={uploadMutation.isPending}
              >
                <FileSpreadsheet className="h-4 w-4" />
                <span>دانلود نمونه اکسل</span>
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setOpen(false);
                  router.push("/import");
                }}
                disabled={uploadMutation.isPending}
              >
                <Upload className="h-4 w-4" />
                <span>آپلود فایل اکسل پر شده</span>
              </Button>
            </div>
          </div>
        </DrawerContent>
      </Drawer>
    </>
  );
}
