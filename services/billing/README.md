Billing Service
Complete billing microservice with Stripe integration, async processing, and RabbitMQ event publishing.
🚀 Quick Start
1. Copy the template
Copy service-template into services/billing/.
2. Environment Variables
Add to your .env with the BILLING_ prefix:
env
BILLING_DB_URL=postgresql+asyncpg://postgres:STAS%201217@postgres:5432/billing
BILLING_STRIPE_SECRET_KEY=sk_test_xxx
BILLING_STRIPE_WEBHOOK_SECRET=whsec_xxx
BILLING_STRIPE_PRO_PRICE_ID=price_xxx
BILLING_STRIPE_BUSINESS_PRICE_ID=price_xxx
BILLING_RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
BILLING_AUTH_SERVICE_URL=http://auth-service:8000
BILLING_SERVICE_TOKEN=supersecret123
3. Local Development
bash
# Install dependencies
pip install -r requirements.txt  # or use Poetry / uv

# Run the service
uvicorn app.main:app --host 0.0.0.0 --port 8000
🧪 Testing
Run all tests
bash
cd services/billing
pytest tests/ -v
Run with coverage
bash
pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=70
SQLite for tests
Tests use aiosqlite so you don't need a running PostgreSQL instance:
bash
pip install aiosqlite
🔒 Webhook Security
Table
Feature	Implementation
Signature verification	stripe.Webhook.construct_event(payload, sig, secret) → 400 on invalid
Idempotency	event.id checked against webhook_events table; duplicates return 200 immediately
Fast response	Endpoint returns 200 in < 5s; processing happens in BackgroundTasks
PII protection	Raw payload is never logged. Only event_id, type, and processed are logged
🌐 Webhook Local Testing with Stripe CLI
bash
# Terminal 1: forward Stripe webhooks to local service
stripe listen --forward-to http://localhost:8000/webhooks/stripe
# Copy the webhook signing secret (whsec_xxx) into your .env

# Terminal 2: trigger test events
stripe trigger checkout.session.completed
stripe trigger invoice.paid
stripe trigger customer.subscription.updated
stripe trigger customer.subscription.deleted
stripe trigger invoice.payment_failed
📡 Architecture
Event Publishing
Events are published to RabbitMQ topic exchange billing.events via the EventPublisher class:
Exchange: billing.events (topic, durable)
Message properties: delivery_mode=2 (persistent), content_type=application/json
Payload envelope: {event_id, version: 1, timestamp, ...payload}
Connection: aio_pika.connect_robust with auto-reconnect
Sequence Diagram: Subscription Flow
Mermaid
Code
Preview
Auth Service
RabbitMQ
Stripe
Billing Service
User
Auth Service
RabbitMQ
Stripe
Billing Service
User
POST /billing/checkout {plan: "pro"}
Create Customer + Checkout Session
session.url
Redirect to Stripe Checkout
Complete payment
webhook: checkout.session.completed
Verify signature + idempotency
Create/Update Subscription in DB
Publish subscription.changed
Consume event, update user plan
💳 Stripe Test Cards
Table
Card Number	Scenario
4242 4242 4242 4242	Success
4000 0000 0000 0002	Card declined
4000 0025 0000 3155	Requires 3D Secure (requires_action)
4000 0000 0000 0341	Insufficient funds
📋 Handled Webhook Events
Table
Event Type	Action
checkout.session.completed	Retrieve subscription, create/update Subscription, publish subscription.changed
customer.subscription.updated	Update status/plan/period, publish subscription.changed
customer.subscription.deleted	Set status=canceled, plan=free, publish subscription.changed
invoice.paid	Save Invoice to DB, publish invoice.paid
invoice.payment_failed	Publish payment.failed for notifications
Other events	Logged and ACK'd
🛠️ Troubleshooting
Table
Problem	Solution
Invalid signature	Check BILLING_STRIPE_WEBHOOK_SECRET matches the one from stripe listen
ModuleNotFoundError: No module named 'jwt'	Install pyjwt: pip install pyjwt
ModuleNotFoundError: No module named 'aio_pika'	Install aio_pika: pip install aio-pika
PostgreSQL lagging in tests	Tests use SQLite by default via aiosqlite
429 rate_limit_reached	You hit the hourly rate limit on your Kimi plan; wait 3 hours or upgrade
Docker container fails to start	Rebuild: docker compose up -d --build billing-service
🔌 API Endpoints
Table
Method	Path	Description
POST	/billing/checkout	Create Stripe checkout session
POST	/billing/portal	Create customer portal session
GET	/billing/subscriptions/me	Get current user's subscription
POST	/billing/cancel	Cancel at period end
GET	/billing/invoices	List invoices
POST	/webhooks/stripe	Stripe webhook handler
GET	/health	Health check