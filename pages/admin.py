from django.contrib import admin

from .models import (
    Book,
    Library,
    LibraryBook,
    Loan,
    Membership,
    MembershipInvite,
    ReadingGoal,
    ReadingShelfEntry,
)


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ("name", "subscription_status", "created_at", "trial_ends_at")
    search_fields = ("name",)
    list_filter = ("subscription_status",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "series", "published_year")
    list_filter = ("category",)
    search_fields = ("title", "author", "series")


@admin.register(LibraryBook)
class LibraryBookAdmin(admin.ModelAdmin):
    list_display = ("library", "book", "total_copies")
    search_fields = ("library__name", "book__title")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "library", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("user__username", "library__name")


@admin.register(MembershipInvite)
class MembershipInviteAdmin(admin.ModelAdmin):
    list_display = ("email", "library", "role", "created_at", "accepted_at")
    list_filter = ("role", "accepted_at")
    search_fields = ("email", "library__name")


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("library_book", "borrower", "checked_out_at", "due_date", "returned_at")
    list_filter = ("returned_at",)
    search_fields = ("borrower__username", "library_book__book__title", "library_book__library__name")


@admin.register(ReadingShelfEntry)
class ReadingShelfEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "status", "progress", "is_favorite", "updated_at")
    list_filter = ("status", "is_favorite")
    search_fields = ("user__username", "book__title", "book__author")


@admin.register(ReadingGoal)
class ReadingGoalAdmin(admin.ModelAdmin):
    list_display = ("user", "year", "books_target", "updated_at")
    list_filter = ("year",)
    search_fields = ("user__username",)
