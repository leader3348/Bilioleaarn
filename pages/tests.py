from datetime import timedelta
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Book, Library, Loan, Membership, MembershipInvite, ReadingGoal, ReadingShelfEntry


class BibliothequePagesTests(TestCase):
    def test_homepage_displays_new_arrivals(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Great Hunt")

    def test_catalogue_includes_new_books_and_filters_by_series(self):
        response = self.client.get("/catalogue/")

        self.assertEqual(response.context["page_obj"].paginator.count, 240)
        self.assertContains(response, "A Game of Thrones")

        filtered_response = self.client.get("/catalogue/?serie=Mistborn")
        self.assertContains(filtered_response, "The Well of Ascension")
        self.assertNotContains(filtered_response, "The Two Towers")
        search_response = self.client.get("/catalogue/?q=The%20Two%20Towers")
        self.assertContains(search_response, "The Two Towers")
        self.assertNotContains(search_response, "The Wise Man&#x27;s Fear")

    def test_catalogue_paginates_archive_without_truncating_the_3d_collection(self):
        first_page = self.client.get("/catalogue/")
        second_page = self.client.get("/catalogue/?page=2")

        self.assertEqual(len(first_page.context["livres"]), 24)
        self.assertEqual(first_page.context["page_obj"].paginator.num_pages, 10)
        self.assertEqual(len(first_page.context["scene_books"]), 240)
        self.assertEqual(len(second_page.context["scene_books"]), 240)
        self.assertNotEqual(
            first_page.context["livres"][0]["book"].pk,
            second_page.context["livres"][0]["book"].pk,
        )

    def test_catalogue_filters_books_and_3d_shelves_by_genre(self):
        response = self.client.get("/catalogue/?genre=science_fiction")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["livres"]), 20)
        self.assertEqual({book["category"] for book in response.context["scene_books"]}, {"science_fiction"})
        self.assertContains(response, "Dune")
        self.assertNotContains(response, "The Hobbit")

    def test_catalogue_has_alphabetized_clickable_shelves_and_author_sort(self):
        response = self.client.get("/catalogue/")
        content = response.content.decode()

        self.assertContains(response, "Un monde de livres")
        self.assertContains(response, "library-books-data")
        self.assertIn('href="/catalogue/?serie=A%20Song%20of%20Ice%20and%20Fire"', content)
        self.assertIn('data-shelf="fantasy"', content)
        self.assertLess(content.index("A Song of Ice and Fire"), content.index("Arthurian fantasy"))

        author_sorted = self.client.get("/catalogue/?ordre=auteur")
        self.assertEqual(author_sorted.context["livres"][0]["book"].title, "The Dark Crystal")
        self.assertEqual(len(author_sorted.context["scene_books"]), 240)
        self.assertEqual(author_sorted.context["scene_books"][0]["title"], "The Dark Crystal")

    def test_immersive_catalogue_exposes_only_current_library_availability(self):
        self.create_library_account(self.client, "owner-one", "one@example.com", "First Library")
        book = Book.objects.get(title="The Way of Kings")

        response = self.client.get("/catalogue/")
        scene_book = next(book_data for book_data in response.context["scene_books"] if book_data["id"] == book.pk)

        self.assertEqual(scene_book["available"], 1)
        self.assertEqual(scene_book["detail"], f"/livres/{book.pk}/")

    def test_every_catalog_book_has_a_cover_image_and_local_fallback(self):
        response = self.client.get("/catalogue/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode().count('class="book-cover"'), 24)
        self.assertEqual(Book.objects.filter(openlibrary_cover_id__isnull=False).count(), 36)
        self.assertContains(response, "pages/images/book-cover-placeholder.svg")
        self.assertTrue(all(book.cover_url.endswith(".svg") or "/b/id/" in book.cover_url for book in Book.objects.all()))
        self.assertFalse(any("/b/title/" in book.cover_url for book in Book.objects.all()))
        self.assertEqual(Book.objects.filter(category=Book.Category.FANTASY).count(), 40)
        self.assertEqual(Book.objects.filter(category=Book.Category.SCIENCE_FICTION).count(), 20)
        self.assertEqual(
            list(Book.objects.values_list("category", flat=True).distinct().order_by("category")),
            [
                Book.Category.COMPUTER_SCIENCE,
                Book.Category.FANTASY,
                Book.Category.HISTORY,
                Book.Category.LITERATURE,
                Book.Category.MATHEMATICS,
                Book.Category.MYSTERY,
                Book.Category.PHILOSOPHY,
                Book.Category.PSYCHOLOGY,
                Book.Category.ROMANCE,
                Book.Category.SCIENCE,
                Book.Category.SCIENCE_FICTION,
            ],
        )
        self.assertIn("Superintelligence", {book["title"] for book in response.context["scene_books"]})
        generated_cover = self.client.get(f"/livres/{Book.objects.get(title='Dune').pk}/couverture.svg")
        self.assertEqual(generated_cover["Content-Type"], "image/svg+xml; charset=utf-8")
        self.assertContains(generated_cover, "SCIENCE-FICTION")

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

    def test_personal_reading_shelf_tracks_status_progress_favorites_and_goal(self):
        self.create_library_account(self.client, "reader-one", "reader@example.com", "Reader's Cabinet")
        book = Book.objects.get(title="The Way of Kings")
        shelf_url = f"/livres/{book.pk}/bibliotheque/"

        self.client.post(shelf_url, {"action": "status", "status": ReadingShelfEntry.Status.READING})
        self.client.post(shelf_url, {"action": "progress", "progress": 37})
        self.client.post(shelf_url, {"action": "bookmark", "bookmark_page": 128})
        self.client.post(shelf_url, {"action": "favorite", "favorite": "true"})
        entry = ReadingShelfEntry.objects.get(user__username="reader-one", book=book)

        self.assertEqual(entry.status, ReadingShelfEntry.Status.READING)
        self.assertEqual(entry.progress, 37)
        self.assertEqual(entry.bookmark_page, 128)
        self.assertTrue(entry.is_favorite)
        self.assertContains(self.client.get("/espace/"), "En cours de lecture")
        self.assertContains(self.client.get("/espace/#favorites"), "The Way of Kings")

        self.client.post("/espace/objectif/", {"books_target": 24})
        goal = ReadingGoal.objects.get(user__username="reader-one")
        self.assertEqual(goal.books_target, 24)

        self.client.post(shelf_url, {"action": "status", "status": ReadingShelfEntry.Status.FINISHED})
        entry.refresh_from_db()
        self.assertEqual(entry.progress, 100)
        self.assertIsNotNone(entry.finished_at)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_flow_sends_a_working_single_use_link(self):
        user = get_user_model().objects.create_user(
            username="reader-reset",
            email="reset@example.com",
            password="A-very-strong-test-password-2026",
        )
        response = self.client.post("/mot-de-passe/oublie/", {"email": user.email}, follow=True)

        self.assertContains(response, "vérifier votre boîte mail")
        self.assertEqual(len(mail.outbox), 1)
        reset_link = re.search(
            r"(\/mot-de-passe\/reinitialiser\/[\w-]+\/[\w-]+\/)",
            mail.outbox[0].body,
        )
        self.assertIsNotNone(reset_link)
        reset_path = reset_link.group(1)
        reset_page = self.client.get(reset_path, follow=True)
        self.assertContains(reset_page, "Nouveau mot de passe")
        reset_path = reset_page.redirect_chain[-1][0]
        response = self.client.post(
            reset_path,
            {
                "new_password1": "A-different-strong-password-2026!",
                "new_password2": "A-different-strong-password-2026!",
            },
            follow=True,
        )

        self.assertContains(response, "La clef a changé")
        user.refresh_from_db()
        self.assertTrue(user.check_password("A-different-strong-password-2026!"))

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
                "first_name": f"Lecteur {username}",
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

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/inscription/carte-de-membre/")
        certificate = self.client.get("/inscription/carte-de-membre/")
        self.assertContains(certificate, "Carte de membre")
        self.assertContains(certificate, "Lecteur owner-one")
        self.assertContains(certificate, "Dragon Library")
        library = Library.objects.get(name="Dragon Library")
        membership = Membership.objects.get(library=library)
        self.assertEqual(membership.user.username, "owner-one")
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(library.inventory.count(), 40)
        self.assertTrue(library.has_access)
        self.assertContains(self.client.get("/espace/"), "Dragon Library")
        self.assertRedirects(self.client.get("/inscription/carte-de-membre/"), "/espace/")

    def test_login_accepts_email_or_username_and_remember_me_controls_session(self):
        user = get_user_model().objects.create_user(
            username="reader-login",
            email="reader-login@example.com",
            password="A-very-strong-test-password-2026",
        )

        response = self.client.post(
            "/connexion/",
            {"username": user.email, "password": "A-very-strong-test-password-2026", "remember_me": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/espace/")
        self.assertFalse(self.client.session.get_expire_at_browser_close())

        self.client.post("/deconnexion/")
        response = self.client.post(
            "/connexion/",
            {"username": user.username, "password": "A-very-strong-test-password-2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/espace/")
        self.assertTrue(self.client.session.get_expire_at_browser_close())

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
        self.assertEqual(Book.objects.count(), 240)

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
                "category": Book.Category.FANTASY,
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

