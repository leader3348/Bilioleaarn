from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Book, Library, Loan, Membership, MembershipInvite


class BibliothequePagesTests(TestCase):
    def test_homepage_displays_new_arrivals(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Great Hunt")

    def test_catalogue_includes_new_books_and_filters_by_series(self):
        response = self.client.get("/catalogue/")

        self.assertContains(response, "The Two Towers")
        self.assertContains(response, "The Wise Man&#x27;s Fear")

        filtered_response = self.client.get("/catalogue/?serie=Mistborn")
        self.assertContains(filtered_response, "The Well of Ascension")
        self.assertNotContains(filtered_response, "The Two Towers")

    def test_every_catalog_book_has_a_cover_image_and_local_fallback(self):
        response = self.client.get("/catalogue/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode().count('class="book-cover"'), 40)
        self.assertEqual(response.content.decode().count("covers.openlibrary.org/b/id/"), 36)
        self.assertContains(response, "pages/images/book-cover-placeholder.svg")
        self.assertTrue(all(book.cover_url for book in Book.objects.all()))
        self.assertFalse(any("/b/title/" in book.cover_url for book in Book.objects.all()))

    def test_book_detail_shows_book_facts_and_legal_reading_options(self):
        book = Book.objects.get(title="The Hobbit")

        response = self.client.get(f"/livres/{book.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Hobbit")
        self.assertContains(response, "J. R. R. Tolkien")
        self.assertContains(response, "1937")
        self.assertContains(response, "Vérifier l’emprunt numérique")
        self.assertContains(response, "openlibrary.org/works/OL27482W")
        self.assertEqual(book.reading_url, "https://openlibrary.org/works/OL27482W")
        self.assertContains(response, "Collection")
        self.assertEqual(self.client.get("/livres/999999/").status_code, 404)

    def test_book_detail_only_shows_current_library_inventory(self):
        self.create_library_account(self.client, "owner-one", "one@example.com", "First Library")
        book = Book.objects.get(title="The Way of Kings")

        response = self.client.get(f"/livres/{book.pk}/")

        self.assertContains(response, "First Library")
        self.assertContains(response, "1 exemplaire")
        self.assertContains(response, "Emprunter cet exemplaire")

    def test_homepage_uses_omar_footer_and_hides_about_page_link(self):
        response = self.client.get("/")

        self.assertContains(response, "Omar")
        self.assertNotContains(response, "ESMA Marrakech")
        self.assertNotContains(response, "À propos")
        self.assertEqual(self.client.get("/a-propos/").status_code, 404)

    def create_library_account(self, client, username, email, library_name):
        return client.post(
            "/inscription/",
            {
                "username": username,
                "email": email,
                "library_name": library_name,
                "password1": "A-very-strong-test-password-2026",
                "password2": "A-very-strong-test-password-2026",
            },
        )

    def test_signup_creates_private_library_with_seeded_fantasy_catalog(self):
        response = self.create_library_account(
            self.client,
            "owner-one",
            "owner@example.com",
            "Dragon Library",
        )

        self.assertRedirects(response, "/espace/")
        library = Library.objects.get(name="Dragon Library")
        membership = Membership.objects.get(library=library)
        self.assertEqual(membership.user.username, "owner-one")
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(library.inventory.count(), 40)
        self.assertTrue(library.has_access)
        self.assertContains(self.client.get("/espace/"), "Dragon Library")

    def test_loan_workflow_is_scoped_to_library(self):
        self.create_library_account(self.client, "owner-one", "one@example.com", "First Library")
        first_library = Library.objects.get(name="First Library")
        first_inventory = first_library.inventory.get(book__title="The Way of Kings")

        borrow_response = self.client.post(f"/emprunts/{first_inventory.pk}/emprunter/")
        self.assertRedirects(borrow_response, "/catalogue/")
        loan = Loan.objects.get(library_book=first_inventory)
        self.assertEqual(loan.borrower.username, "owner-one")
        self.assertEqual(first_inventory.available_copies, 0)

        self.client.post(f"/emprunts/{first_inventory.pk}/emprunter/")
        self.assertEqual(Loan.objects.filter(library_book=first_inventory, returned_at__isnull=True).count(), 1)

        second_client = self.client_class()
        self.create_library_account(second_client, "owner-two", "two@example.com", "Second Library")
        self.assertEqual(
            second_client.post(f"/emprunts/{first_inventory.pk}/emprunter/").status_code,
            404,
        )
        self.assertEqual(
            second_client.post(f"/emprunts/{loan.pk}/retourner/").status_code,
            404,
        )

        self.client.post(f"/emprunts/{loan.pk}/retourner/")
        loan.refresh_from_db()
        self.assertIsNotNone(loan.returned_at)
        self.assertEqual(first_inventory.available_copies, 1)

    @override_settings(STRIPE_SECRET_KEY="", STRIPE_PRICE_ID="")
    def test_checkout_reports_missing_stripe_configuration(self):
        self.create_library_account(self.client, "owner-one", "owner@example.com", "Dragon Library")

        response = self.client.post("/abonnement/checkout/", follow=True)

        self.assertContains(response, "La facturation n&#x27;est pas configurée")
        self.assertEqual(Book.objects.count(), 40)

    @override_settings(STRIPE_SECRET_KEY="sk_test_example", STRIPE_PRICE_ID="price_monthly")
    @patch("pages.views.stripe.checkout.Session.create")
    def test_owner_checkout_starts_stripe_subscription(self, create_session):
        create_session.return_value = SimpleNamespace(url="https://checkout.stripe.test/session")
        self.create_library_account(self.client, "owner-one", "owner@example.com", "Dragon Library")

        response = self.client.post("/abonnement/checkout/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://checkout.stripe.test/session")
        params = create_session.call_args.kwargs
        self.assertEqual(params["mode"], "subscription")
        self.assertEqual(params["line_items"], [{"price": "price_monthly", "quantity": 1}])
        self.assertEqual(params["metadata"]["library_id"], str(Library.objects.get(name="Dragon Library").pk))

    def test_owner_can_invite_a_reader_to_their_workspace(self):
        self.create_library_account(self.client, "owner-one", "owner@example.com", "Dragon Library")
        response = self.client.post(
            "/equipe/inviter/",
            {"email": "reader@example.com", "role": Membership.Role.MEMBER},
        )

        self.assertRedirects(response, "/equipe/")
        invite = MembershipInvite.objects.get(email="reader@example.com")
        invitation_url = f"/invitations/{invite.token}/"
        invite_client = self.client_class()
        self.assertContains(invite_client.get(invitation_url), "Dragon Library")
        acceptance = invite_client.post(
            invitation_url,
            {
                "username": "reader-one",
                "password1": "A-very-strong-test-password-2026",
                "password2": "A-very-strong-test-password-2026",
            },
        )

        self.assertRedirects(acceptance, "/espace/")
        member = get_user_model().objects.get(username="reader-one")
        membership = Membership.objects.get(user=member)
        self.assertEqual(membership.library.name, "Dragon Library")
        self.assertEqual(membership.role, Membership.Role.MEMBER)
        invite.refresh_from_db()
        self.assertIsNotNone(invite.accepted_at)

    def test_librarian_can_add_inventory_copies(self):
        self.create_library_account(self.client, "owner-one", "owner@example.com", "Dragon Library")

        response = self.client.post(
            "/catalogue/ajouter/",
            {
                "title": "The Ember Archive",
                "author": "A. Testwriter",
                "published_year": 2024,
                "series": "Ember Archive",
                "volume": 1,
                "total_copies": 3,
            },
        )

        self.assertRedirects(response, "/espace/")
        inventory = Library.objects.get(name="Dragon Library").inventory.get(
            book__title="The Ember Archive",
        )
        self.assertEqual(inventory.total_copies, 3)

    def test_expired_invitation_cannot_be_accepted(self):
        self.create_library_account(self.client, "owner-one", "owner@example.com", "Dragon Library")
        invite = MembershipInvite.objects.create(
            library=Library.objects.get(name="Dragon Library"),
            email="reader@example.com",
            role=MembershipInvite.Role.MEMBER,
            invited_by=get_user_model().objects.get(username="owner-one"),
        )
        MembershipInvite.objects.filter(pk=invite.pk).update(
            created_at=timezone.now() - timedelta(days=8),
        )

        response = self.client_class().get(f"/invitations/{invite.token}/")

        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "Ce lien n'est plus valide", status_code=410)

    def test_expired_trial_blocks_library_operations_but_keeps_billing_access(self):
        self.create_library_account(self.client, "owner-one", "owner@example.com", "Dragon Library")
        library = Library.objects.get(name="Dragon Library")
        library.trial_ends_at = timezone.now() - timedelta(days=1)
        library.save(update_fields=("trial_ends_at",))
        inventory = library.inventory.get(book__title="The Way of Kings")

        self.assertRedirects(self.client.get("/espace/"), "/abonnement/")
        self.assertRedirects(self.client.post(f"/emprunts/{inventory.pk}/emprunter/"), "/abonnement/")
        self.assertFalse(Loan.objects.filter(library_book=inventory).exists())
        self.assertEqual(self.client.get("/abonnement/").status_code, 200)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
    def test_stripe_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            "/webhooks/stripe/",
            data="{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid",
        )

        self.assertEqual(response.status_code, 400)

