# Product Importer

ابزار SaaS موبایل‌محور برای غرفه‌داران باسلام: کاربر با باسلام SSO وارد می‌شه، با دوربین گوشی از محصول عکس می‌گیره، AI تحلیل و بهبود تصویر می‌ده، دسته‌بندی و ویژگی‌ها پیشنهاد می‌شه، قیمت از بازار باسلام استخراج می‌شه، و در نهایت بعد از تایید کاربر روی غرفه ثبت می‌شه. اعتبار سنجی موجودی با یک دفترکل (ledger) دو‌طرفه انجام می‌شه و هیچ ستون balance روی User نداریم.

## معماری

```
repo/
  backend/       FastAPI + SQLAlchemy 2.x async + Postgres + Alembic + httpx
                 OAuth (Basalam) + Fernet token encryption + JWT cookie session
                 Ledger service (transactions table → balance)
                 Background worker (FOR UPDATE SKIP LOCKED) برای پردازش محصول
  frontend/      Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui
                 TanStack Query، Proxy route handler به بک، middleware برای auth gate
                 موبایل-اول، Persian RTL، Vazirmatn، Camera fullscreen
  docs/PRD.md    PRD اصلی محصول
  docker-compose.yml
```

تفکیک کامل وظایف هر سرویس:
- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)

## شروع سریع با Docker

```bash
cp backend/.env.example backend/.env
# پر کردن BASALAM_CLIENT_ID/SECRET/REDIRECT_URI و OPENROUTER_API_KEY و کلیدهای SESSION/FERNET
cp frontend/.env.local.example frontend/.env.local

docker compose up --build
```

سپس مرورگر: `http://localhost:3000` → کلیک "ورود با باسلام".

## شروع محلی بدون Docker

دو ترمینال جدا.

ترمینال ۱ (Postgres):
```bash
docker run --rm -p 5432:5432 -e POSTGRES_USER=importer -e POSTGRES_PASSWORD=importer -e POSTGRES_DB=importer postgres:16-alpine
```

ترمینال ۲ (Backend):
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # ویرایش .env طبق دستورالعمل backend/README.md
alembic upgrade head
uvicorn app.main:app --reload
```

ترمینال ۳ (Frontend):
```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

## ساختار دفترکل

تنها جدول حساب: `transactions`.

| ستون | نوع | شرح |
|------|-----|-----|
| general_type | WITHDRAW \| DEPOSIT | جهت تراکنش |
| reference_type | PRODUCT \| SUBSCRIPTION \| PAYMENT \| REFERRAL \| GIFT \| REQUEST_AMOUNT | منبع |
| reference_id | bigint nullable | شناسه‌ی موجودیت مرجع (در صورت وجود) |
| amount | numeric(14,0) | همیشه مثبت — علامت از general_type |
| status | PENDING \| COMPLETED \| FAILED \| REVERSED |  |
| idempotency_key | unique partial | جلوگیری از کسر دوبار |

موجودی = `SUM(amount * sign(general_type)) FILTER (status = COMPLETED)`.

تایید topup در MVP دستیه:
```bash
cd backend
.venv/bin/python -m scripts.approve_topup <user_id>           # لیست PENDING
.venv/bin/python -m scripts.approve_topup <user_id> <tx_id>   # تایید
```

## مسیرهای API

| Method | Path |
|--------|------|
| GET | `/api/v1/auth/basalam/login` |
| GET | `/api/v1/auth/basalam/callback` |
| GET | `/api/v1/auth/me` |
| POST | `/api/v1/auth/logout` |
| POST | `/api/v1/products` |
| GET | `/api/v1/products` |
| GET | `/api/v1/products/{id}` |
| PATCH | `/api/v1/products/{id}` |
| POST | `/api/v1/products/{id}/resubmit` |
| GET | `/api/v1/ledger/transactions` |
| POST | `/api/v1/ledger/topup` |
| GET | `/api/v1/basalam/categories` |
| GET | `/api/v1/basalam/categories/{id}/attributes` |
| GET | `/api/v1/support/tickets` |
| POST | `/api/v1/support/tickets` |

## فلوی Basalam SSO

1. کاربر روی "ورود با باسلام" در `/login` کلیک می‌کنه.
2. مرورگر می‌ره به `/api/proxy/auth/basalam/login` → Next.js به FastAPI فوروارد می‌کنه.
3. FastAPI یه `state` می‌سازه، توی کوکی `oauth_state` می‌ذاره، و کاربر رو 302 می‌کنه به Basalam OAuth.
4. Basalam بعد از اجازه‌ی کاربر، با `code` به `BASALAM_REDIRECT_URI` (پیش‌فرض `http://localhost:8000/api/v1/auth/basalam/callback`) برمی‌گردونه.
5. سرور `state` رو می‌سنجه، `code` رو با Basalam OAuth (یا `BASALAM_BRIDGE_URL/basalam/connect` اگر set باشه) معامله می‌کنه و access/refresh token می‌گیره.
6. کاربر در DB upsert می‌شه (`basalam_user_id` به‌عنوان natural key). توکن‌ها Fernet-encrypted ذخیره می‌شن.
7. اگر اولین ورود باشه و `SIGNUP_GIFT_AMOUNT > 0` باشه، یه `DEPOSIT GIFT COMPLETED` با اون مقدار درج می‌شه.
8. JWT کوکی `pi_session` HttpOnly صادر می‌شه و کاربر به `${APP_ORIGIN}/home` ریدایرکت می‌شه.

## فلوی ساخت محصول

1. کاربر روی FAB می‌زنه → "گرفتن عکس" → `/camera` تمام‌صفحه.
2. شات می‌گیره (می‌تونه چند شات پشت سر هم). توضیح می‌نویسه.
3. "اتمام و محصول جدید" → `POST /products` با `images: [...]` و `description`.
4. بک‌اند: `ledger.withdraw(user, PRODUCT, cost)` — اگر کم باشه 402 برمی‌گرده و فرانت دیالوگ "موجودی کافی نیست" نشون می‌ده.
5. اگر کافی باشه، Product در DB با status=PROCESSING ساخته می‌شه و یک ImportJob توی صف میره.
6. Worker (در همون process در MVP) Job رو می‌کشه و `processing.process_product_job(...)` اجرا می‌کنه:
   - AI تحلیل و بهبود عکس (OpenRouter).
   - گرفتن دسته‌بندی + ویژگی‌های الزامی از باسلام.
   - استخراج قیمت بازار با الگوریتم weighted-median روی وزن و نوع محصول.
   - validation. اگر چیزی کم باشه: status=READY + persist errors + bailing out (کاربر باید ویرایش کنه).
   - اگر همه چی ok باشه: upload عکس + create_product → status=SUBMITTED + complete_transaction.
   - اگر شکست بخوره: status=FAILED + reverse_transaction.

## تست

بک‌اند:
```bash
cd backend && .venv/bin/pytest -q
```

فرانت (type-check):
```bash
cd frontend && npm run typecheck
```

## انتشار روی GitHub

این repo زیر `github.com/mjavadalavi/product-importer` منتشر می‌شه.

```bash
git init
git add -A
git commit -m "feat: SSO + ledger + Next.js rewrite"
gh repo create mjavadalavi/product-importer --public --source=. --remote=origin --push
```

## ریسک‌ها و TODOهای آینده

- درگاه پرداخت واقعی (الان stub توسط ادمین).
- ذخیره عکس روی S3 (الان data-URL در DB).
- queue روی ARQ + Redis برای multi-process.
- token refresh خودکار وقتی expired شد.
- frontend Playwright smoke (login → camera → submit → see result).
