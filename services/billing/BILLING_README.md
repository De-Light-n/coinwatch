# Billing Service

Сервіс для роботи з білінгом та інтеграцією зі Stripe. Обробляє підписки, платежі, рахунки та керування підписками.

---

## 🚀 Setup

### 1. Environment Variables

У `.env` додай змінні з префіксом `BILLING_`:

```env
# Database
BILLING_DB_URL=postgresql+asyncpg://postgres:password@postgres:5432/billing

# Stripe
BILLING_STRIPE_SECRET_KEY=sk_test_xxx
BILLING_STRIPE_WEBHOOK_SECRET=whsec_xxx
BILLING_STRIPE_PRO_PRICE_ID=price_1xxx_pro
BILLING_STRIPE_BUSINESS_PRICE_ID=price_1xxx_business

# URLs
BILLING_CHECKOUT_SUCCESS_URL=http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}
BILLING_CHECKOUT_CANCEL_URL=http://localhost:3000/cancel
BILLING_PORTAL_RETURN_URL=http://localhost:3000/account

# Services
BILLING_RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
BILLING_AUTH_SERVICE_URL=http://auth-service:8000
BILLING_SERVICE_TOKEN=supersecret123
```

### 2. Running Locally

```bash
# Activate environment
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r services/billing/pyproject.toml

# Run migrations
alembic upgrade head

# Start the service
uvicorn services.billing.app.main:app --reload --port 8001
```

---

## 📋 API Endpoints

### Authentication
All endpoints (except `/health`) require JWT token in `Authorization: Bearer <token>` header.

**Token Payload (expected):**
```json
{
  "sub": "user-uuid",
  "email": "user@example.com"
}
```

### Endpoints

#### `POST /billing/checkout`
Create Stripe Checkout Session for subscription upgrade.

**Request:**
```json
{
  "plan": "pro"  // or "business"
}
```

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/pay/...",
  "session_id": "cs_test_xxx"
}
```

**HTTP Status:**
- `200` - Success
- `400` - Invalid plan
- `401` - Unauthorized
- `402` - Card declined
- `502` - Stripe error

---

#### `POST /billing/portal`
Create Stripe Customer Portal session for subscription management.

**Response:**
```json
{
  "portal_url": "https://billing.stripe.com/..."
}
```

**Features available in portal:**
- Update payment method
- View invoices
- Cancel subscription
- Change subscription plan

---

#### `GET /billing/subscriptions/me`
Get current user's subscription status.

**Response:**
```json
{
  "id": "sub-uuid",
  "plan": "pro",  // or "business" or "free"
  "status": "active",  // or "past_due", "canceled", "trialing", "incomplete"
  "current_period_start": "2024-01-01T00:00:00Z",
  "current_period_end": "2024-02-01T00:00:00Z",
  "cancel_at_period_end": false,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

#### `POST /billing/cancel`
Cancel user's subscription at the end of current billing period.

**Response:**
```json
{
  "status": "canceled",
  "subscription_id": "sub_xxx",
  "cancel_at_period_end": true
}
```

User retains access until current period ends.

---

#### `GET /billing/invoices`
Get user's invoice history with pagination.

**Query Parameters:**
- `limit` (default: 10, max: 100) - Items per page
- `offset` (default: 0) - Pagination offset

**Response:**
```json
{
  "invoices": [
    {
      "id": "in_xxx",
      "number": "INV-0001",
      "amount_paid": 9900,  // cents
      "currency": "usd",
      "status": "paid",
      "created": 1704067200,  // Unix timestamp
      "pdf_url": "https://invoices.stripe.com/..."
    }
  ],
  "total": 5,
  "limit": 10,
  "offset": 0
}
```

---

## 🧪 Testing with Stripe Test Cards

Use these test card numbers for development. Always use **4242** for the expiry month/year and any 3-digit CVC.

### Success Scenario
- **Card:** `4242 4242 4242 4242`
- **Status:** Payment succeeds
- **Use:** Testing successful checkout flow

### Authentication Required
- **Card:** `4000 0027 6000 3184`
- **Status:** Requires 3D Secure authentication
- **Use:** Testing 3DS flow

### Card Declined
- **Card:** `4000 0000 0000 0002`
- **Status:** Card declined
- **Use:** Testing error handling for declined cards

### Insufficient Funds
- **Card:** `4000 0000 0000 9995`
- **Status:** Card has insufficient funds
- **Use:** Testing specific decline codes

### Test API Keys

Get test keys from Stripe Dashboard:
1. Login to [Stripe Dashboard](https://dashboard.stripe.com)
2. Switch to Test Mode (top-right toggle)
3. Go to Developers → API Keys
4. Copy `Secret key` for `BILLING_STRIPE_SECRET_KEY`

---

## 🗄️ Database Models

### Customer
Stores Stripe customer ID linked to user.

```python
user_id: UUID (primary key)
stripe_customer_id: str (unique, indexed)
email: str
created_at: datetime
```

### Subscription
Active subscription record for user.

```python
id: UUID (primary key)
user_id: UUID (foreign key → Customer.user_id)
stripe_subscription_id: str (unique, indexed)
plan: PlanEnum ("pro" | "business")
status: StatusEnum ("active" | "past_due" | "canceled" | "trialing" | "incomplete")
current_period_start: datetime
current_period_end: datetime
cancel_at_period_end: bool
created_at: datetime
updated_at: datetime
```

### Invoice
Stores invoice records.

```python
id: UUID (primary key)
user_id: UUID
stripe_invoice_id: str (unique)
amount_cents: int
currency: str
status: InvoiceStatus ("paid" | "open" | "failed" | "void")
pdf_url: str (optional)
created_at: datetime
```

### WebhookEvent
Stores processed webhook events.

```python
id: UUID (primary key)
stripe_event_id: str (unique, indexed)
event_type: str
payload: JSON
processed_at: datetime
```

---

## 🔧 Service Architecture

### Layers

1. **Router** (`routers/billing.py`)
   - HTTP endpoints
   - Request/response validation
   - Error handling

2. **Service** (`services/subscription_service.py`)
   - Business logic
   - Database operations
   - Orchestration

3. **Stripe Integration** (`services/stripe_service.py`)
   - Stripe API wrapper
   - Async execution with error handling
   - Exception mapping

4. **Models** (`models/`)
   - SQLAlchemy ORM models
   - Pydantic schemas for API

---

## 🚨 Error Handling

The service maps Stripe errors to appropriate HTTP status codes:

| Error | HTTP Status | Description |
|-------|-------------|-------------|
| `CardError` | 402 | Card declined or invalid |
| `RateLimitError` | 429 | Too many requests to Stripe |
| `AuthenticationError` | 401 | Invalid Stripe API key |
| `InvalidRequestError` | 400 | Invalid request parameters |
| `StripeError` | 502 | General Stripe API error |

---

## 🔒 Webhooks (Production-Grade)

Stripe sends webhooks for every subscription/payment state change. The endpoint is **heavily hardened**:

- **Signature verification** — every payload is verified with `stripe.Webhook.construct_event`
- **Idempotency** — events are deduplicated via the `webhook_events` table (Stripe guarantees at-least-once delivery)
- **Fast ACK** — endpoint responds `200` in `< 5 sec` and processes asynchronously via `BackgroundTasks`
- **No PII in logs** — only `event_id`, `event_type`, and `processed=true/false` are logged

### Supported events

| Event | Action | RabbitMQ event |
|-------|--------|----------------|
| `checkout.session.completed` | Create/update `Subscription`, map plan from `price_id` | `subscription.changed` |
| `customer.subscription.updated` | Update `Subscription` status & period | `subscription.changed` |
| `customer.subscription.deleted` | Set status `canceled`, plan `free` | `subscription.changed` |
| `invoice.paid` | Save `Invoice` record | `invoice.paid` |
| `invoice.payment_failed` | — | `payment.failed` |
| Other | Log and ACK | — |

### Local testing with Stripe CLI

```bash
# 1. Install Stripe CLI (https://stripe.com/docs/stripe-cli)

# 2. Forward webhooks to local billing service
stripe listen --forward-to http://localhost:8001/webhooks/stripe
#    ^ This prints a webhook signing secret (whsec_xxx).
#      Put it in .env as BILLING_STRIPE_WEBHOOK_SECRET=whsec_xxx

# 3. Trigger test events
stripe trigger checkout.session.completed
stripe trigger invoice.paid
stripe trigger customer.subscription.updated
stripe trigger customer.subscription.deleted
stripe trigger invoice.payment_failed
```

> ⚠️ **Security**: Never log raw webhook payloads — they contain PII.

---

## 📝 Logging

Uses `structlog` for structured logging. Key events logged:

- `checkout_endpoint_success` - Successful checkout creation
- `checkout_card_error` - Card declined
- `portal_endpoint_success` - Portal session created
- `cancel_subscription_success` - Subscription canceled
- `get_invoices_success` - Invoices fetched

Example log output:
```json
{
  "event": "checkout_endpoint_success",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "plan": "pro",
  "session_id": "cs_test_xxx",
  "timestamp": "2024-01-15T10:30:45.123456Z"
}
```

---

## 🔄 Future: Webhook Processing

When webhooks are implemented, this service will handle:

- `customer.subscription.created` - New subscription
- `customer.subscription.updated` - Subscription changed
- `customer.subscription.deleted` - Subscription canceled
- `invoice.payment_succeeded` - Invoice paid
- `invoice.payment_failed` - Payment failed

See `services/webhook_service.py` for webhook handling.

---

## 📚 References

- [Stripe Python SDK](https://stripe.com/docs/libraries/python)
- [Stripe Checkout](https://stripe.com/docs/payments/checkout)
- [Stripe Billing Portal](https://stripe.com/docs/billing/subscriptions/integrating-portal)
- [Stripe Test Cards](https://stripe.com/docs/testing)
