# Frontend — Product Importer

Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui (new-york) + TanStack Query.
Mobile-first, Persian RTL, Vazirmatn font.

## Routes

| Path | Group | Notes |
|------|-------|-------|
| `/login` | public | تنها CTA: ورود با باسلام (SSO) |
| `/home` | `(authed)` | لیست محصولات + هدر کاربر + FAB |
| `/products/[id]` | `(authed)` | جزئیات و ویرایش محصول |
| `/payments` | `(authed)` | لیست تراکنش‌ها و افزایش موجودی |
| `/support` | `(authed)` | تیکت‌های پشتیبانی |
| `/camera` | `(fullscreen)` | دوربین تمام‌صفحه، بدون BottomNav |

Routes under `(authed)` گذرنده از `middleware.ts` (چک کوکی `pi_session`). در صورت نبود کوکی → ریدایرکت به `/login`.

## معماری

- **Proxy:** `app/api/proxy/[...path]/route.ts` همه‌ی متدها رو به FastAPI روی `NEXT_PUBLIC_API_BASE` فوروارد می‌کنه و کوکی‌های `Set-Cookie` رو از بک پاس می‌ده. نتیجه: کوکی httpOnly از بک‌اند مستقیم به مرورگر می‌رسه، بدون CORS preflight.
- **Client API:** `lib/api.ts` — wrapper تایپ‌دار با `api.get/post/patch/del` که خودش به `/api/proxy/...` می‌زنه.
- **State:** TanStack Query. هیچ Redux یا store سراسری دیگه‌ای نداریم.
- **Auth state:** سرور-side. `/auth/me` تنها منبع حقیقت.

## راه‌اندازی محلی

```bash
cd frontend
cp .env.local.example .env.local
# ویرایش .env.local: NEXT_PUBLIC_API_BASE (پیش‌فرض http://localhost:8000)
npm install
npm run dev
# باز کن: http://localhost:3000
```

## فرمان‌ها

- `npm run dev` — حالت توسعه با hot-reload روی 3000
- `npm run build` — ساخت production
- `npm run start` — اجرای production build
- `npm run lint` — eslint
- `npm run typecheck` — `tsc --noEmit`

## Docker

روی monorepo:

```bash
docker compose up
```

## اضافه کردن کامپوننت shadcn جدید

طبق روال استاندارد shadcn/ui:

```bash
npx shadcn@latest add <component-name>
```

پیکربندی در `components.json` با `style: "new-york"` و `baseColor: "neutral"`.

## فلوی کلی کاربر

1. `/login` → کلیک روی "ورود با باسلام" → `GET /api/proxy/auth/basalam/login` → ریدایرکت به Basalam OAuth → callback → کوکی `pi_session` ست می‌شه → ریدایرکت به `/home`.
2. `/home`: لیست محصولات + موجودی هدر. FAB پایین چپ → Drawer با دو دکمه‌ی "گرفتن عکس" (به `/camera`) و "آپلود فایل".
3. `/camera`: تمام‌صفحه، دوربین واقعی، دکمه‌ی شاتر بزرگ. بعد از هر شات یک تولتیپ بالا-راست (RTL) باز می‌شه با Textarea توضیح و دکمه‌های "+ عکس بیشتر" / "حذف محصول" / "اتمام و محصول جدید". با "اتمام" → POST `/products` → اگر موجودی کافی، محصول وارد صف پردازش می‌شه؛ وگرنه دیالوگ "موجودی کافی نیست" باز می‌شه.
4. `/products/[id]`: کارت با تب‌های ویرایش / تحلیل AI / نمونه قیمت / خطاها.
5. `/payments`: تراکنش‌ها + دکمه‌ی "افزایش موجودی" (مودال).
6. `/support`: لیست تیکت‌ها + دکمه‌ی "تیکت جدید".

## محدودیت‌های MVP

- ذخیره‌ی عکس‌ها روی DB به‌صورت data-URL در `ProductImage.original_url`. در نسخه‌ی بعدی به S3 منتقل می‌شه.
- درگاه پرداخت واقعی نداریم. درخواست افزایش موجودی به‌صورت دستی توسط ادمین تایید می‌شه (`scripts/approve_topup.py` در بک‌اند).
- worker پردازش محصول تک‌پروسسه‌ست (FastAPI BackgroundTask + DB polling). در production به ARQ + Redis ارتقا داده می‌شه.
