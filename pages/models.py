import secrets
from datetime import timedelta
from urllib.parse import quote_plus

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Library(models.Model):
    class SubscriptionStatus(models.TextChoices):
        TRIALING = "trialing", "Essai"
        ACTIVE = "active", "Actif"
        PAST_DUE = "past_due", "Paiement en retard"
        CANCELED = "canceled", "Annulé"
        INCOMPLETE = "incomplete", "Incomplet"

    name = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_status = models.CharField(
        max_length=32,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIALING,
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name

    @property
    def has_access(self):
        if self.subscription_status == "active":
            return True
        return (
            self.subscription_status == "trialing"
            and self.trial_ends_at is not None
            and self.trial_ends_at > timezone.now()
        )


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Propriétaire"
        LIBRARIAN = "librarian", "Bibliothécaire"
        MEMBER = "member", "Membre"

    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="library_memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user",), name="one_library_per_user"),
        ]

    def __str__(self):
        return f"{self.user} — {self.library}"


class MembershipInvite(models.Model):
    class Role(models.TextChoices):
        LIBRARIAN = Membership.Role.LIBRARIAN, "Bibliothécaire"
        MEMBER = Membership.Role.MEMBER, "Membre"

    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_library_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("library", "email"),
                condition=models.Q(accepted_at__isnull=True),
                name="one_pending_invite_per_email",
            ),
        ]

    @property
    def is_expired(self):
        return self.created_at + timedelta(days=7) <= timezone.now()

    def __str__(self):
        return f"{self.email} — {self.library}"


class Book(models.Model):
    class Category(models.TextChoices):
        FANTASY = "fantasy", "Fantasy"
        SCIENCE_FICTION = "science_fiction", "Science-fiction"
        PHILOSOPHY = "philosophy", "Philosophie"
        HISTORY = "history", "Histoire"
        PSYCHOLOGY = "psychology", "Psychologie"
        LITERATURE = "literature", "Littérature"
        MYSTERY = "mystery", "Mystère et thriller"
        ROMANCE = "romance", "Romance"
        COMPUTER_SCIENCE = "computer_science", "Informatique"
        MATHEMATICS = "mathematics", "Mathématiques"
        SCIENCE = "science", "Sciences"

    title = models.CharField(max_length=240)
    author = models.CharField(max_length=160)
    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.FANTASY,
        db_index=True,
    )
    published_year = models.PositiveSmallIntegerField(null=True, blank=True)
    series = models.CharField(max_length=160, blank=True)
    volume = models.PositiveSmallIntegerField(default=1)
    openlibrary_work_key = models.CharField(max_length=32, blank=True)
    openlibrary_cover_id = models.PositiveBigIntegerField(null=True, blank=True)
    openlibrary_ebook_access = models.CharField(max_length=24, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("title", "author")
        constraints = [
            models.UniqueConstraint(fields=("title", "author"), name="unique_book_title_author"),
        ]

    def __str__(self):
        return f"{self.title} — {self.author}"

    @property
    def cover_url(self):
        if self.openlibrary_cover_id:
            return f"https://covers.openlibrary.org/b/id/{self.openlibrary_cover_id}-L.jpg?default=false"
        if self.pk:
            return reverse("pages:couverture_livre", args=(self.pk,))
        return "/static/pages/images/book-cover-placeholder.svg"

    @property
    def reading_url(self):
        if self.openlibrary_work_key:
            return f"https://openlibrary.org{self.openlibrary_work_key}"
        query = quote_plus(f'"{self.title}" "{self.author}"')
        return f"https://openlibrary.org/search?q={query}"


class LibraryBook(models.Model):
    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="inventory")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="library_copies")
    total_copies = models.PositiveSmallIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("book__title",)
        constraints = [
            models.UniqueConstraint(fields=("library", "book"), name="unique_book_per_library"),
            models.CheckConstraint(condition=models.Q(total_copies__gte=1), name="library_book_copies_positive"),
        ]

    @property
    def available_copies(self):
        checked_out = getattr(self, "_active_loan_count", None)
        if checked_out is None:
            checked_out = self.loans.filter(returned_at__isnull=True).count()
        return max(self.total_copies - checked_out, 0)

    def __str__(self):
        return f"{self.book} ({self.library})"


class Loan(models.Model):
    library_book = models.ForeignKey(LibraryBook, on_delete=models.CASCADE, related_name="loans")
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="book_loans")
    checked_out_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-checked_out_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("library_book", "borrower"),
                condition=models.Q(returned_at__isnull=True),
                name="one_active_copy_per_borrower",
            ),
        ]

    def __str__(self):
        return f"{self.borrower} — {self.library_book.book}"


class ReadingShelfEntry(models.Model):
    class Status(models.TextChoices):
        WANT_TO_READ = "want_to_read", "À lire"
        READING = "reading", "En cours"
        FINISHED = "finished", "Terminé"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reading_entries",
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reader_entries")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WANT_TO_READ)
    progress = models.PositiveSmallIntegerField(default=0)
    bookmark_page = models.PositiveIntegerField(null=True, blank=True)
    is_favorite = models.BooleanField(default=False)
    last_opened_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(fields=("user", "book"), name="unique_personal_reading_entry"),
            models.CheckConstraint(
                condition=models.Q(progress__gte=0, progress__lte=100),
                name="reading_progress_between_zero_and_hundred",
            ),
            models.CheckConstraint(
                condition=models.Q(bookmark_page__isnull=True) | models.Q(bookmark_page__gte=1),
                name="reading_bookmark_page_positive",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.book} ({self.get_status_display()})"


class ReadingGoal(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reading_goals",
    )
    year = models.PositiveSmallIntegerField()
    books_target = models.PositiveSmallIntegerField(default=12)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-year",)
        constraints = [
            models.UniqueConstraint(fields=("user", "year"), name="unique_reading_goal_per_year"),
            models.CheckConstraint(condition=models.Q(books_target__gte=1), name="reading_goal_target_positive"),
        ]

    def __str__(self):
        return f"{self.user} — {self.year}: {self.books_target} livres"
