# Product Importer — Backend

## معماری / Architecture

FastAPI + SQLAlchemy 2.x (async) + PostgreSQL + Alembic  
httpx (outbound HTTP) | cryptography (Fernet) | python-jose (JWT) | Basalam OAuth 2.0

---

## ساختار پوشه‌ها / Folder Structure

```
backend/
├── alembic/          # migration scripts
├── app/
│   ├── api/          # FastAPI routers (v1)
│   ├── auth/         # OAuth flow, JWT helpers, session middleware
│   ├── core/         # config, exceptions, logging setup
│   ├── db/           # SQLAlchemy engine, Base, session factory
│   ├── services/     # business logic (product, ledger, basalam, ai)
│   └── schemas/      # Pydantic request/response models
├── scripts/          # one-off admin scripts
├── tests/            # pytest test suite
├── .env.example
├── alembic.ini
├── Dockerfile
└── requirements.txt
```

---

## متغیرهای محیطی / Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL asyncpg connection string |
| `SESSION_SECRET` | Secret for signing JWT session tokens |
| `FERNET_KEY` | Fernet key for encrypting stored OAuth tokens |
| `BASALAM_CLIENT_ID` | OAuth application client ID from Basalam |
| `BASALAM_CLIENT_SECRET` | OAuth application client secret from Basalam |
| `BASALAM_REDIRECT_URI` | Callback URL registered with Basalam OAuth |
| `BASALAM_AUTHORIZE_URL` | Basalam OAuth authorization endpoint |
| `BASALAM_TOKEN_URL` | Basalam OAuth token exchange endpoint |
| `BASALAM_OPENAPI_BASE` | Base URL for Basalam OpenAPI calls |
| `BASALAM_SCOPES` | Space-separated OAuth scopes to request |
| `BASALAM_BRIDGE_URL` | Optional: bridge service URL for token exchange |
| `BASALAM_BRIDGE_API_KEY` | API key sent as `x-api-key` to the bridge |
| `BASALAM_PRODUCT_STATUS` | Default status code when submitting products |
| `OPENROUTER_API_KEY` | OpenRouter API key for AI-powered enrichment |
| `OPENROUTER_TEXT_MODEL` | Model ID for text generation |
| `OPENROUTER_IMAGE_MODEL` | Model ID for image understanding |
| `COST_PER_PRODUCT` | Ledger debit per product submission (integer) |
| `SIGNUP_GIFT_AMOUNT` | Ledger credit gifted to new users on signup |
| `APP_ORIGIN` | Frontend origin for CORS and redirect after login |
| `SESSION_COOKIE_NAME` | Name of the JWT session cookie |
| `SESSION_TTL_DAYS` | JWT cookie lifetime in days |
| `COOKIE_SECURE` | Set to `true` in production (HTTPS only) |

---

## راه‌اندازی محلی / Local Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# ویرایش .env با مقادیر واقعی
# تولید FERNET_KEY:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# تولید SESSION_SECRET:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
alembic upgrade head
uvicorn app.main:app --reload
```

---

## راه‌اندازی با Docker / Docker Setup

از ریشه monorepo:

```bash
docker compose up
```

سرویس backend با `alembic upgrade head` شروع می‌کنه و روی پورت 8000 گوش می‌ده.

---

## فلوی SSO باسلام / Basalam SSO Flow

1. کاربر روی لینک ورود کلیک می‌کنه — `GET /api/v1/auth/basalam/login`
2. سرور کاربر رو به صفحه OAuth باسلام ریدایرکت می‌کنه.
3. باسلام بعد از تایید، `code` رو به `GET /api/v1/auth/basalam/callback` می‌فرسته.
4. سرور `code` رو تعویض می‌کنه:
   - اگر `BASALAM_BRIDGE_URL` تنظیم باشه: `POST ${BASALAM_BRIDGE_URL}/basalam/connect` با هدر `x-api-key`.
   - در غیر این صورت: مستقیم با `BASALAM_TOKEN_URL`.
5. یوزر در دیتابیس upsert می‌شه (ساخته یا آپدیت).
6. اگر یوزر تازه ساخته شده باشه و `SIGNUP_GIFT_AMOUNT > 0`، یک تراکنش GIFT/DEPOSIT/COMPLETED ثبت می‌شه.
7. JWT صادر می‌شه و به‌عنوان کوکی HttpOnly ست می‌شه.
8. کاربر به `${APP_ORIGIN}/home` ریدایرکت می‌شه.

---

## دفترکل / Ledger

موجودی کاربر هیچ‌وقت روی جدول User ذخیره نمی‌شه. هر بار از مجموع جدول `transactions` محاسبه می‌شه:

```
balance = SUM(amount) WHERE type=DEPOSIT - SUM(amount) WHERE type=WITHDRAW
          AND user_id = ? AND status = COMPLETED
```

**Enum ها:**

| Dimension | Values |
|---|---|
| type | `DEPOSIT`, `WITHDRAW` |
| category | `PRODUCT`, `SUBSCRIPTION`, `PAYMENT`, `REFERRAL`, `GIFT`, `REQUEST_AMOUNT` |
| status | `PENDING`, `COMPLETED`, `FAILED`, `REVERSED` |

---

## تایید شارژ / Approving a Topup

در MVP، تایید شارژ دستی است. پس از تایید پرداخت خارج از سیستم:

```bash
python -m scripts.approve_topup <user_id> <tx_id>
```

این دستور وضعیت تراکنش رو از `PENDING` به `COMPLETED` تغییر می‌ده.

---

## تست‌ها / Tests

```bash
pytest -q
```

---

## مسیرهای API اصلی / Main API Routes

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/auth/basalam/login` | Redirect to Basalam OAuth |
| GET | `/api/v1/auth/basalam/callback` | OAuth callback, sets session cookie |
| GET | `/api/v1/auth/me` | Get current authenticated user |
| POST | `/api/v1/auth/logout` | Clear session cookie |
| GET | `/api/v1/products` | List user's products |
| POST | `/api/v1/products` | Submit a new product |
| GET | `/api/v1/products/{id}` | Get product detail |
| PATCH | `/api/v1/products/{id}` | Update a product |
| POST | `/api/v1/products/{id}/resubmit` | Resubmit a failed product |
| GET | `/api/v1/ledger/transactions` | List ledger transactions |
| POST | `/api/v1/ledger/topup` | Request a topup (creates PENDING tx) |
| GET | `/api/v1/basalam/categories` | List Basalam categories |
| GET | `/api/v1/basalam/categories/{id}/attributes` | Get category attributes |
| GET | `/api/v1/support/tickets` | List support tickets |
| POST | `/api/v1/support/tickets` | Create a support ticket |

---

## مسیر ارتقا / Upgrade Path

در MVP فعلی، پردازش پس‌زمینه از طریق `FastAPI BackgroundTask` و DB polling انجام می‌شه.

مسیر ارتقا: جایگزینی با **ARQ + Redis** برای صف‌های async قابل اطمینان‌تر.
