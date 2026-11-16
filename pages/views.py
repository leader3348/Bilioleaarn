from datetime import datetime, timedelta, timezone as datetime_timezone
import secrets

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .catalog import FANTASY_BOOKS
from .forms import BookForm, ContactForm, InvitationAccountForm, MembershipInviteForm, SignUpForm
from .models import Book, Library, LibraryBook, Loan, Membership, MembershipInvite


MAISONS = [
    {"nom": "Stark", "devise": "Winter Is Coming", "siege": "Winterfell", "region": "Le Nord"},
    {"nom": "Lannister", "devise": "Hear Me Roar!", "siege": "Castral Roc", "region": "Les Terres de l'Ouest"},
    {"nom": "Targaryen", "devise": "Fire and Blood", "siege": "Peyredragon", "region": "Les Terres de la Couronne"},
    {"nom": "Baratheon", "devise": "Ours Is the Fury", "siege": "Accalmie", "region": "Les Terres de l'Orage"},
    {"nom": "Tyrell", "devise": "Growing Strong", "siege": "Hautjardin", "region": "Le Bief"},
    {"nom": "Martell", "devise": "Unbowed, Unbent, Unbroken", "siege": "Lancehélion", "region": "Dorne"},
]


def _membership_for(user):
    return get_object_or_404(
        Membership.objects.select_related("library"),
        user=user,
    )


def _has_library_access(request, membership):
    if membership.library.has_access:
        return True
    messages.warning(request, "Votre période d'essai est terminée. Choisissez un abonnement pour continuer.")
    return False


def _can_manage(membership):
    return membership.role in (Membership.Role.OWNER, Membership.Role.LIBRARIAN)


def accueil(request):
    featured = list(Book.objects.filter(title="The Great Hunt")[:1])
    nouveautes = featured + list(Book.objects.exclude(pk__in=[book.pk for book in featured]).order_by("-created_at")[:3])
    return render(
        request,
        "pages/accueil.html",
        {
            "nom_projet": "Mnémosyne",
            "modules": ["Catalogue partagé", "Gestion des emprunts", "Équipe et rôles", "Abonnement sécurisé"],
            "nb_ressources": Book.objects.count(),
            "nouveautes": nouveautes,
        },
    )


def catalogue(request):
    serie = request.GET.get("serie", "").strip()
    recherche = request.GET.get("q", "").strip()
    books = Book.objects.all()
    if serie:
        books = books.filter(series=serie)
    if recherche:
        books = books.filter(Q(title__icontains=recherche) | Q(author__icontains=recherche) | Q(series__icontains=recherche))

    membership = None
    inventory_by_book = {}
    if request.user.is_authenticated:
        membership = Membership.objects.filter(user=request.user).select_related("library").first()
        if membership:
            inventory_by_book = {
                item.book_id: {
                    "id": item.pk,
                    "total_copies": item.total_copies,
                    "available_copies": max(item.total_copies - item.active_loan_count, 0),
                }
                for item in LibraryBook.objects.filter(library=membership.library)
                .annotate(active_loan_count=Count("loans", filter=Q(loans__returned_at__isnull=True)))
            }

    livres = [
        {"book": book, "inventory": inventory_by_book.get(book.pk)}
        for book in books
    ]
    series = Book.objects.exclude(series="").order_by("series").values_list("series", flat=True).distinct()
    return render(
        request,
        "pages/catalogue.html",
        {
            "livres": livres,
            "series": series,
            "serie_active": serie,
            "recherche": recherche,
            "membership": membership,
        },
    )


def fiche_livre(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    membership = None
    inventory = None
    if request.user.is_authenticated:
        membership = Membership.objects.filter(user=request.user).select_related("library").first()
        if membership:
            inventory = (
                LibraryBook.objects.filter(library=membership.library, book=book)
                .annotate(active_loan_count=Count("loans", filter=Q(loans__returned_at__isnull=True)))
                .first()
            )
            if inventory:
                inventory._active_loan_count = inventory.active_loan_count
    series_books = (
        Book.objects.filter(series=book.series).exclude(pk=book.pk)
        if book.series
        else Book.objects.none()
    )
    return render(
        request,
        "pages/book_detail.html",
        {
            "book": book,
            "membership": membership,
            "inventory": inventory,
            "series_books": series_books[:4],
        },
    )


def maisons(request):
    return render(request, "pages/maisons.html", {"maisons": MAISONS})


def contact(request):
    nom_recu = None
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            nom_recu = form.cleaned_data["nom"]
            form = ContactForm()
    else:
        form = ContactForm()
    return render(request, "pages/contact.html", {"form": form, "nom_recu": nom_recu})


def inscription(request):
    if request.user.is_authenticated:
        return redirect("pages:dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            library = Library.objects.create(
                name=form.cleaned_data["library_name"],
                trial_ends_at=timezone.now() + timedelta(days=14),
            )
            Membership.objects.create(library=library, user=user, role=Membership.Role.OWNER)
            for title, author, year, series, volume in FANTASY_BOOKS:
                book, _ = Book.objects.get_or_create(
                    title=title,
                    author=author,
                    defaults={
                        "published_year": year,
                        "series": series,
                        "volume": volume,
                    },
                )
                LibraryBook.objects.create(library=library, book=book, total_copies=1)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Votre bibliothèque est prête. Vous bénéficiez de 14 jours d'essai gratuit.")
        return redirect("pages:dashboard")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def dashboard(request):
    membership = _membership_for(request.user)
    if not _has_library_access(request, membership):
        return redirect("pages:billing")

    inventory = list(
        LibraryBook.objects.filter(library=membership.library)
        .select_related("book")
        .annotate(active_loan_count=Count("loans", filter=Q(loans__returned_at__isnull=True)))
    )
    for item in inventory:
        item._active_loan_count = item.active_loan_count
    loans = Loan.objects.filter(
        library_book__library=membership.library,
        returned_at__isnull=True,
    ).select_related("borrower", "library_book__book")
    if membership.role == Membership.Role.MEMBER:
        loans = loans.filter(borrower=request.user)
    return render(
        request,
        "pages/dashboard.html",
        {
            "membership": membership,
            "inventory": inventory,
            "loans": loans,
            "member_count": membership.library.memberships.count(),
        },
    )


@login_required
def team(request):
    membership = _membership_for(request.user)
    if not _has_library_access(request, membership):
        return redirect("pages:billing")
    if not _can_manage(membership):
        messages.error(request, "Seuls les propriétaires et bibliothécaires peuvent gérer l'équipe.")
        return redirect("pages:dashboard")
    invite_url = request.session.pop("last_invite_url", None)
    members = membership.library.memberships.select_related("user").order_by("user__username")
    invitations = membership.library.invitations.filter(accepted_at__isnull=True)
    return render(
        request,
        "pages/team.html",
        {
            "membership": membership,
            "members": members,
            "invitations": invitations,
            "invite_url": invite_url,
            "form": MembershipInviteForm(),
        },
    )


@login_required
@require_POST
def inviter_membre(request):
    membership = _membership_for(request.user)
    if not _has_library_access(request, membership):
        return redirect("pages:billing")
    if not _can_manage(membership):
        messages.error(request, "Seuls les propriétaires et bibliothécaires peuvent inviter des membres.")
        return redirect("pages:dashboard")
    form = MembershipInviteForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "pages/team.html",
            {
                "membership": membership,
                "members": membership.library.memberships.select_related("user").order_by("user__username"),
                "invitations": membership.library.invitations.filter(accepted_at__isnull=True),
                "form": form,
            },
            status=400,
        )
    email = form.cleaned_data["email"]
    if Membership.objects.filter(library=membership.library, user__email__iexact=email).exists():
        messages.error(request, "Ce compte fait déjà partie de votre bibliothèque.")
        return redirect("pages:team")
    if Membership.objects.filter(user__email__iexact=email).exists():
        messages.error(request, "Ce compte appartient déjà à une autre bibliothèque.")
        return redirect("pages:team")

    invite = membership.library.invitations.filter(
        email__iexact=email,
        accepted_at__isnull=True,
    ).first()
    if invite is None:
        invite = MembershipInvite.objects.create(
            library=membership.library,
            email=email,
            role=form.cleaned_data["role"],
            invited_by=request.user,
        )
    elif invite.is_expired:
        invite.token = secrets.token_urlsafe(32)
        invite.created_at = timezone.now()
        invite.role = form.cleaned_data["role"]
        invite.invited_by = request.user
        invite.save(update_fields=("token", "created_at", "role", "invited_by"))
    else:
        invite.role = form.cleaned_data["role"]
        invite.invited_by = request.user
        invite.save(update_fields=("role", "invited_by"))
    request.session["last_invite_url"] = request.build_absolute_uri(
        reverse("pages:accepter_invitation", args=(invite.token,))
    )
    messages.success(request, f"Invitation créée pour {email}. Copiez le lien ci-dessous pour le partager.")
    return redirect("pages:team")


def accepter_invitation(request, token):
    invite = get_object_or_404(
        MembershipInvite.objects.select_related("library"),
        token=token,
        accepted_at__isnull=True,
    )
    if invite.is_expired:
        return render(request, "pages/invitation.html", {"expired": True}, status=410)

    if request.user.is_authenticated:
        if request.user.email.lower() != invite.email.lower():
            return render(
                request,
                "pages/invitation.html",
                {"invite": invite, "email_mismatch": True},
                status=403,
            )
        if request.method == "POST":
            with transaction.atomic():
                invite = MembershipInvite.objects.select_for_update().get(pk=invite.pk)
                existing = Membership.objects.filter(user=request.user).exclude(library=invite.library).first()
                if existing:
                    messages.error(request, "Ce compte est déjà rattaché à une autre bibliothèque.")
                    return redirect("pages:accueil")
                Membership.objects.get_or_create(
                    library=invite.library,
                    user=request.user,
                    defaults={"role": invite.role},
                )
                invite.accepted_at = timezone.now()
                invite.save(update_fields=("accepted_at",))
            messages.success(request, f"Vous avez rejoint {invite.library.name}.")
            return redirect("pages:dashboard")
        return render(request, "pages/invitation.html", {"invite": invite, "can_accept": True})

    User = get_user_model()
    if User.objects.filter(email__iexact=invite.email).exists():
        return render(
            request,
            "pages/invitation.html",
            {"invite": invite, "account_exists": True},
        )

    form = InvitationAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if User.objects.filter(email__iexact=invite.email).exists():
            form.add_error(None, "Un compte utilise déjà cette adresse. Connectez-vous pour accepter l'invitation.")
        else:
            with transaction.atomic():
                invite = MembershipInvite.objects.select_for_update().get(pk=invite.pk)
                user = form.save(commit=False)
                user.email = invite.email
                user.save()
                Membership.objects.create(library=invite.library, user=user, role=invite.role)
                invite.accepted_at = timezone.now()
                invite.save(update_fields=("accepted_at",))
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, f"Bienvenue dans {invite.library.name}.")
            return redirect("pages:dashboard")
    return render(request, "pages/invitation.html", {"invite": invite, "form": form})


@login_required
@require_POST
def emprunter(request, inventory_id):
    membership = _membership_for(request.user)
    if not _has_library_access(request, membership):
        return redirect("pages:billing")
    try:
        with transaction.atomic():
            inventory = get_object_or_404(
                LibraryBook.objects.select_for_update(),
                pk=inventory_id,
                library=membership.library,
            )
            if inventory.loans.filter(borrower=request.user, returned_at__isnull=True).exists():
                messages.info(request, "Vous avez déjà un exemplaire de ce livre en cours d'emprunt.")
            elif inventory.available_copies < 1:
                messages.error(request, "Tous les exemplaires sont actuellement empruntés.")
            else:
                Loan.objects.create(
                    library_book=inventory,
                    borrower=request.user,
                    due_date=timezone.localdate() + timedelta(days=14),
                )
                messages.success(request, "Le livre a été ajouté à vos emprunts. Le retour est prévu dans 14 jours.")
    except IntegrityError:
        messages.error(request, "Cet emprunt n'a pas pu être enregistré. Actualisez la page et réessayez.")
    return redirect("pages:catalogue")


@login_required
@require_POST
def rendre_livre(request, loan_id):
    membership = _membership_for(request.user)
    if not _has_library_access(request, membership):
        return redirect("pages:billing")
    loan = get_object_or_404(
        Loan.objects.select_related("library_book__book"),
        pk=loan_id,
        library_book__library=membership.library,
        returned_at__isnull=True,
    )
    if loan.borrower_id != request.user.pk and not _can_manage(membership):
        messages.error(request, "Vous ne pouvez retourner que vos propres emprunts.")
        return redirect("pages:dashboard")
    loan.returned_at = timezone.now()
    loan.save(update_fields=("returned_at",))
    messages.success(request, f"« {loan.library_book.book.title} » a été marqué comme rendu.")
    return redirect("pages:dashboard")


@login_required
def ajouter_livre(request):
    membership = _membership_for(request.user)
    if not _has_library_access(request, membership):
        return redirect("pages:billing")
    if not _can_manage(membership):
        messages.error(request, "Seuls les bibliothécaires peuvent modifier le catalogue.")
        return redirect("pages:dashboard")
    form = BookForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            book, created = Book.objects.get_or_create(
                title=form.cleaned_data["title"],
                author=form.cleaned_data["author"],
                defaults={
                    "published_year": form.cleaned_data["published_year"],
                    "series": form.cleaned_data["series"],
                    "volume": form.cleaned_data["volume"],
                },
            )
            inventory, added = LibraryBook.objects.get_or_create(
                library=membership.library,
                book=book,
                defaults={"total_copies": form.cleaned_data["total_copies"]},
            )
            if not added:
                inventory.total_copies += form.cleaned_data["total_copies"]
                inventory.save(update_fields=("total_copies",))
        if created:
            messages.success(request, "Le livre et ses exemplaires ont été ajoutés au catalogue.")
        else:
            messages.success(request, "Les exemplaires ont été ajoutés à votre bibliothèque.")
        return redirect("pages:dashboard")
    return render(request, "pages/book_form.html", {"form": form})


@login_required
def billing(request):
    membership = _membership_for(request.user)
    return render(
        request,
        "pages/billing.html",
        {
            "membership": membership,
            "owner": Membership.objects.filter(
                library=membership.library,
                role=Membership.Role.OWNER,
            ).select_related("user").first(),
            "stripe_configured": bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRICE_ID),
            "is_owner": membership.role == Membership.Role.OWNER,
        },
    )


@login_required
@require_POST
def creer_checkout(request):
    membership = _membership_for(request.user)
    if membership.role != Membership.Role.OWNER:
        messages.error(request, "Seul le propriétaire de la bibliothèque peut gérer l'abonnement.")
        return redirect("pages:billing")
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PRICE_ID:
        messages.error(request, "La facturation n'est pas configurée. Ajoutez STRIPE_SECRET_KEY et STRIPE_PRICE_ID.")
        return redirect("pages:billing")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    checkout_params = {
        "mode": "subscription",
        "line_items": [{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        "success_url": request.build_absolute_uri(reverse("pages:billing")) + "?success=1",
        "cancel_url": request.build_absolute_uri(reverse("pages:billing")) + "?canceled=1",
        "client_reference_id": str(membership.library_id),
        "metadata": {"library_id": str(membership.library_id)},
        "subscription_data": {"metadata": {"library_id": str(membership.library_id)}},
    }
    if membership.library.stripe_customer_id:
        checkout_params["customer"] = membership.library.stripe_customer_id
    else:
        checkout_params["customer_email"] = request.user.email
    try:
        session = stripe.checkout.Session.create(**checkout_params)
    except stripe.StripeError as exc:
        messages.error(request, f"Stripe n'a pas pu créer la session de paiement : {exc.user_message or str(exc)}")
        return redirect("pages:billing")
    return redirect(session.url)


@login_required
@require_POST
def ouvrir_portail_facturation(request):
    membership = _membership_for(request.user)
    if membership.role != Membership.Role.OWNER:
        messages.error(request, "Seul le propriétaire de la bibliothèque peut gérer l'abonnement.")
        return redirect("pages:billing")
    if not settings.STRIPE_SECRET_KEY or not membership.library.stripe_customer_id:
        messages.error(request, "Aucun compte de facturation Stripe actif n'est associé à cette bibliothèque.")
        return redirect("pages:billing")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.billing_portal.Session.create(
            customer=membership.library.stripe_customer_id,
            return_url=request.build_absolute_uri(reverse("pages:billing")),
        )
    except stripe.StripeError as exc:
        messages.error(request, f"Le portail de facturation n'a pas pu être ouvert : {exc.user_message or str(exc)}")
        return redirect("pages:billing")
    return redirect(session.url)


def _sync_subscription(subscription):
    metadata = subscription.get("metadata") or {}
    library_id = metadata.get("library_id")
    query = Library.objects.all()
    if library_id:
        library = query.filter(pk=library_id).first()
    else:
        library = query.filter(stripe_subscription_id=subscription.get("id")).first()
    if library is None:
        return
    library.subscription_status = subscription.get("status", "incomplete")
    library.stripe_subscription_id = subscription.get("id", "")
    customer = subscription.get("customer")
    library.stripe_customer_id = customer.get("id") if isinstance(customer, dict) else (customer or "")
    trial_end = subscription.get("trial_end")
    library.trial_ends_at = (
        datetime.fromtimestamp(trial_end, tz=datetime_timezone.utc)
        if trial_end
        else None
    )
    library.save(
        update_fields=(
            "subscription_status",
            "stripe_subscription_id",
            "stripe_customer_id",
            "trial_ends_at",
        )
    )


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse("Stripe webhook is not configured.", status=503)
    signature = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponseBadRequest("Invalid Stripe webhook signature or payload.")

    event_type = event.get("type")
    payload = event.get("data", {}).get("object", {})
    if event_type in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        _sync_subscription(payload)
    elif event_type == "checkout.session.completed":
        subscription_id = payload.get("subscription")
        if subscription_id:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            subscription = stripe.Subscription.retrieve(subscription_id)
            _sync_subscription(subscription)
    elif event_type == "invoice.payment_failed":
        subscription_id = payload.get("subscription")
        if subscription_id:
            Library.objects.filter(stripe_subscription_id=subscription_id).update(
                subscription_status="past_due",
            )
    return HttpResponse(status=200)
