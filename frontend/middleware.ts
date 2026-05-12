import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const COOKIE = process.env.SESSION_COOKIE_NAME || "pi_session";

const PROTECTED = ["/home", "/products", "/payments", "/support", "/camera", "/import"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const isProtected = PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (!isProtected) return NextResponse.next();
  const session = req.cookies.get(COOKIE);
  if (!session) {
    const loginUrl = new URL("/login", req.url);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|api/proxy|favicon.ico|fonts).*)"],
};
