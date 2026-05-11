export type ApiError = { status: number; message: string; detail?: unknown };

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = path.startsWith("/api/proxy") ? path : `/api/proxy${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", Accept: "application/json", ...(init.headers || {}) },
    credentials: "include",
  });
  let body: unknown = null;
  try { body = await res.json(); } catch {}
  if (!res.ok) {
    const err: ApiError = {
      status: res.status,
      message: (body as any)?.message || (body as any)?.detail || res.statusText,
      detail: (body as any)?.detail,
    };
    throw err;
  }
  return body as T;
}

export const api = {
  get<T>(path: string) { return apiFetch<T>(path, { method: "GET" }); },
  post<T>(path: string, body?: unknown) { return apiFetch<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }); },
  patch<T>(path: string, body?: unknown) { return apiFetch<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }); },
  del<T>(path: string) { return apiFetch<T>(path, { method: "DELETE" }); },
};

// Types for backend responses
export type MeResponse = {
  id: string;
  basalam_user_id: number;
  vendor_id: number | null;
  name: string;
  username: string;
  avatar_url: string | null;
  balance: number;
};

export type ProductImageIn = { filename: string; data_url: string };
export type ProductCreateRequest = { description?: string | null; images: ProductImageIn[] };
export type ProductCreatedResponse = { product_id: string; status: string };

export type ProductListItem = {
  id: string;
  status: string;
  name: string | null;
  category_title: string | null;
  price_final: number | null;
  primary_image_url: string | null;
  created_at: string;
  basalam_product_id: number | null;
};

export type ProductImageOut = {
  id: string;
  order: number;
  original_url: string | null;
  enhanced_url: string | null;
  use_enhanced: boolean;
  filename: string;
  enhancement_model: string | null;
  enhancement_error: string | null;
};

export type ProductOut = {
  id: string;
  status: string;
  name: string | null;
  brief: string | null;
  description: string | null;
  category_id: number | null;
  category_title: string | null;
  category_confidence: number | null;
  price_final: number | null;
  price_suggested: number | null;
  price_meta: Record<string, unknown> | null;
  stock: number | null;
  weight: number | null;
  package_weight: number | null;
  preparation_days: number | null;
  unit_quantity: number | null;
  unit_type: number | null;
  sku: string | null;
  attributes: Record<string, unknown> | null;
  variants: Array<Record<string, unknown>> | null;
  ai_result: Record<string, unknown> | null;
  price_samples: Array<Record<string, unknown>> | null;
  basalam_product_id: number | null;
  errors: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  images: ProductImageOut[];
};

export type Paginated<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_more: boolean;
};

export type TransactionOut = {
  id: string;
  general_type: "WITHDRAW" | "DEPOSIT";
  reference_type: "PRODUCT" | "SUBSCRIPTION" | "PAYMENT" | "REFERRAL" | "GIFT" | "REQUEST_AMOUNT";
  reference_id: number | null;
  amount: number;
  status: "PENDING" | "COMPLETED" | "FAILED" | "REVERSED";
  note: string | null;
  created_at: string;
};

export type SupportTicketOut = {
  id: string;
  subject: string;
  body: string;
  status: "OPEN" | "IN_PROGRESS" | "CLOSED";
  created_at: string;
  updated_at: string;
};
