"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, Plus, Upload } from "lucide-react";
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
import { fileToDataUrl } from "@/lib/format";

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
      const images: ProductImageIn[] = await Promise.all(
        files.map(async (file) => ({
          filename: file.name,
          data_url: await fileToDataUrl(file),
        })),
      );
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
              از دوربین عکس بگیر یا فایل آپلود کن
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
                {uploadMutation.isPending ? "در حال آپلود..." : "آپلود فایل"}
              </span>
            </Button>
          </div>
        </DrawerContent>
      </Drawer>
    </>
  );
}
