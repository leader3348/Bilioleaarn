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

Open <http://127.0.0.1:8000/> and create a library account. The local database is SQLite. The shared catalogue includes 240 works across eleven genres; migration `0006` adds 200 curated titles while keeping each new library's original 40-book starter inventory unchanged. The catalogue opens as a WebGL-powered Three.js library: orbit through a procedurally constructed, warmly lit wooden reading room, approach real 3D genre shelves, and pull out, inspect, and open individual books. Search, genre and A–Z navigation, distinct procedural covers, verified cover art, animated reading pages, accessibility fallbacks, and Django book detail and lending links are included. The room and book models are bundled locally; verified book-cover images are loaded from Open Library. If you edit `pages/static/pages/library-world.js`, rebuild its browser bundle with `npm install` followed by `npm run build:library`. Each book has a detail page with publication, genre and series information, library-copy availability, related volumes, and an external Open Library link to check legal reading or borrowing options. Reading pages in the 3D viewer are original, non-book-specific sample pages, not reproduced copyrighted text.

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

## Personal reading and password reset

After signing in, readers can use **My library** to organize books as currently reading, want to read, finished, or favorites; save a page bookmark and progress; and set an annual reading goal. These personal shelves are separate from a library's shared inventory and loans. Run `py manage.py migrate` after updating to create the reading-shelf and goal tables.

Registration creates the Django account, private library, owner membership, and starter inventory in one transaction. The new reader is then shown a one-time, authenticated membership certificate before entering the immersive catalogue. Login accepts either the username or a unique account email; **Stay signed in** controls whether the browser session expires when the browser closes.

Password reset is available from the login page. In local development, Django prints reset emails in the runserver console. Production uses Django's SMTP backend; configure `DJANGO_DEFAULT_FROM_EMAIL` and Django's standard `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `EMAIL_USE_TLS` environment settings for your mail provider. You can override the backend with `DJANGO_EMAIL_BACKEND`.

## Production configuration

Do not use the development defaults for a public deployment. Generate a unique `DJANGO_SECRET_KEY` (for example with `py -c "import secrets; print(secrets.token_urlsafe(64))"`), then set `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and a managed PostgreSQL `DATABASE_URL`; configure Stripe with live keys and a live recurring Price. Run `py manage.py migrate` and `py manage.py collectstatic --noinput` before serving traffic. A production Linux host can run `gunicorn config.wsgi:application`. Use managed database backups and HTTPS. Invitation links are generated in the team page and must be shared with the invited person.