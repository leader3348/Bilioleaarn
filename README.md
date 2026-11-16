# Mnémosyne

Mnémosyne is a Django SaaS starter for school and community libraries, styled as a classic cabinet of books. Each signup creates a private library workspace with its own inventory, members, loans, and a 14-day trial. Book metadata and verified edition links are shared in the catalog; copies and loans are scoped to each library.

## Run locally (Windows / PowerShell)

From the folder containing `manage.py`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py manage.py migrate
py manage.py test
py manage.py runserver
```

Open <http://127.0.0.1:8000/> and create a library account. The local database is SQLite. The site uses an antique-library theme; verified fantasy covers and edition links are loaded from Open Library, with an original locally served illustrated cover when no verified cover is available. Each book has a detail page with publication and series information, library-copy availability, related volumes, and an external Open Library link to check legal reading or borrowing options. Availability depends on the edition and Open Library access status. Cover images are credited on the catalog page.

## Stripe subscriptions

Create a recurring Price in Stripe, then set the test keys in the same PowerShell terminal before starting Django:

```powershell
$env:STRIPE_SECRET_KEY = "sk_test_..."
$env:STRIPE_PRICE_ID = "price_..."
$env:STRIPE_WEBHOOK_SECRET = "whsec_..."
py manage.py runserver
```

For local webhook testing, install and authenticate the Stripe CLI, then run this in another terminal:

```powershell
stripe listen --forward-to localhost:8000/webhooks/stripe/
```

Copy the `whsec_...` value printed by the CLI into `STRIPE_WEBHOOK_SECRET`. Enable these events for a production webhook endpoint at `/webhooks/stripe/`:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`

The Stripe Price ID controls the amount and currency. Card details are entered on Stripe-hosted pages and are never stored by Mnémosyne.

## Production configuration

Do not use the development defaults for a public deployment. Generate a unique `DJANGO_SECRET_KEY` (for example with `py -c "import secrets; print(secrets.token_urlsafe(64))"`), then set `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and a managed PostgreSQL `DATABASE_URL`; configure Stripe with live keys and a live recurring Price. Run `py manage.py migrate` and `py manage.py collectstatic --noinput` before serving traffic. A production Linux host can run `gunicorn config.wsgi:application`. Use managed database backups and HTTPS. Invitation links are generated in the team page and must be shared with the invited person.