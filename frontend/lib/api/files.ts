import type { ApiError } from "@/lib/api";

export type FileKind =
  | "product_image"
  | "bulk_sheet"
  | "bulk_zip"
  | "support_attachment"
  | "misc";

export type UploadFileMeta = {
  kind: FileKind;
  targetType?: string;
  targetId?: string;
  metadata?: Record<string, unknown>;
};

export type UploadedFileStatus = "READY" | "PROCESSING" | "FAILED" | "DELETED";

export type UploadedFile = {
  id: string;
  kind: string;
  target_type: string | null;
  target_id: string | null;
  mime: string;
  size_bytes: number;
  filename: string;
  public_url: string | null;
  status: UploadedFileStatus;
  created_at: string;
  metadata: Record<string, unknown>;
};

function extractErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const b = body as Record<string, unknown>;
  if (typeof b.message === "string" && b.message.trim()) return b.message;
  const detail = b.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Record<string, unknown>;
    if (typeof d.message === "string" && d.message.trim()) return d.message;
  }
  if (Array.isArray(detail)) {
    const first = detail[0] as Record<string, unknown> | undefined;
    if (first && typeof first.msg === "string") return first.msg;
  }
  return fallback;
}

export async function uploadFile(
  file: File,
  meta: UploadFileMeta,
): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", meta.kind);
  if (meta.targetType !== undefined) form.append("target_type", meta.targetType);
  if (meta.targetId !== undefined) form.append("target_id", meta.targetId);
  if (meta.metadata !== undefined) {
    form.append("metadata", JSON.stringify(meta.metadata));
  }

  const res = await fetch("/api/proxy/files", {
    method: "POST",
    body: form,
    credentials: "include",
    headers: { Accept: "application/json" },
  });

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {}

  if (!res.ok) {
    const err: ApiError = {
      status: res.status,
      message: extractErrorMessage(body, res.statusText),
      detail:
        body && typeof body === "object"
          ? (body as Record<string, unknown>).detail
          : undefined,
    };
    throw err;
  }

  return body as UploadedFile;
}

export async function deleteFile(fileId: string): Promise<void> {
  const res = await fetch(`/api/proxy/files/${fileId}`, {
    method: "DELETE",
    credentials: "include",
    headers: { Accept: "application/json" },
  });

  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {}
    const err: ApiError = {
      status: res.status,
      message: extractErrorMessage(body, res.statusText),
      detail:
        body && typeof body === "object"
          ? (body as Record<string, unknown>).detail
          : undefined,
    };
    throw err;
  }
}

export function getFileDownloadUrl(fileId: string): string {
  return `/api/proxy/files/${fileId}/download`;
}
