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

  const bodyBuffer =
    ["GET", "HEAD"].includes(req.method) ? undefined : await req.arrayBuffer();

  // Follow upstream redirects internally so trailing-slash 307s from FastAPI
  // do not leak Location headers that the browser would then misroute.
  // Capped at 5 hops to avoid loops.
  let currentUrl = url.toString();
  let upstream: Response | null = null;
  for (let hop = 0; hop < 5; hop++) {
    upstream = await fetch(currentUrl, {
      method: req.method,
      headers,
      redirect: "manual",
      body: bodyBuffer,
    });
    if (upstream.status < 300 || upstream.status >= 400) break;
    const loc = upstream.headers.get("location");
    if (!loc) break;
    // Resolve next URL against current request URL (handles relative + absolute)
    currentUrl = new URL(loc, currentUrl).toString();
  }
  if (!upstream) {
    return new NextResponse("upstream unreachable", { status: 502 });
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
