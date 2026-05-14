import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function handler(req: NextRequest, { params }: { params: { path: string[] } }) {
  const pathSegments = params.path?.join("/") ?? "";
  const url = new URL(`${API_BASE}/api/v1/${pathSegments}`);
  for (const [k, v] of req.nextUrl.searchParams) url.searchParams.append(k, v);

  const headers = new Headers();
  const cookie = req.headers.get("cookie");
  if (cookie) headers.set("cookie", cookie);
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", "application/json");

  const init: RequestInit = { method: req.method, headers, redirect: "manual" };
  if (!["GET", "HEAD"].includes(req.method)) {
    init.body = await req.arrayBuffer();
  }

  const upstream = await fetch(url.toString(), init);

  // Redirect passthrough — rewrite backend /api/v1/* Location to /api/proxy/*
  // so the browser stays on the proxy hostname and proxy keeps handling.
  // FastAPI may emit either a relative path (/api/v1/foo/) or an absolute URL
  // built from the upstream Host header (http://product-importer-backend:8000/api/v1/foo/),
  // so we parse path-only regardless.
  if (upstream.status >= 300 && upstream.status < 400) {
    const original = upstream.headers.get("location") || "/";
    let path = original;
    try {
      // Absolute URL? extract pathname + search
      const u = new URL(original);
      path = u.pathname + u.search;
    } catch {
      // Relative path — keep as is
    }
    const rewrittenPath = path.startsWith("/api/v1/")
      ? "/api/proxy/" + path.slice("/api/v1/".length)
      : path;
    // Emit a raw redirect with a relative Location so the browser resolves it
    // against the public origin (avoids leaking the internal Next.js hostname
    // that NextResponse.redirect would bake in).
    const res = new NextResponse(null, {
      status: upstream.status,
      headers: { location: rewrittenPath },
    });
    const setCookies = upstream.headers.getSetCookie?.() ?? [];
    for (const c of setCookies) res.headers.append("set-cookie", c);
    return res;
  }

  const body = await upstream.arrayBuffer();
  const res = new NextResponse(body, { status: upstream.status });
  const upstreamContentType = upstream.headers.get("content-type");
  if (upstreamContentType) res.headers.set("content-type", upstreamContentType);
  const setCookies = upstream.headers.getSetCookie?.() ?? [];
  for (const c of setCookies) res.headers.append("set-cookie", c);
  return res;
}

export {
  handler as GET,
  handler as POST,
  handler as PATCH,
  handler as PUT,
  handler as DELETE,
};
