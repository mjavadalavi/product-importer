"use client";

import { useMutation } from "@tanstack/react-query";
import { uploadFile, type UploadFileMeta, type UploadedFile } from "@/lib/api/files";

export function useUploadFile(): {
  uploadAsync: (args: { file: File; meta: UploadFileMeta }) => Promise<UploadedFile>;
  isUploading: boolean;
  error: Error | null;
} {
  const mutation = useMutation<UploadedFile, Error, { file: File; meta: UploadFileMeta }>({
    mutationFn: ({ file, meta }) => uploadFile(file, meta),
  });

  return {
    uploadAsync: mutation.mutateAsync,
    isUploading: mutation.isPending,
    error: mutation.error,
  };
}
