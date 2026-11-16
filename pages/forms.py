from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Book


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="E-mail")
    library_name = forms.CharField(max_length=160, label="Nom de votre bibliothèque")

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte utilise déjà cette adresse e-mail.")
        return email


class BookForm(forms.ModelForm):
    total_copies = forms.IntegerField(
        min_value=1,
        max_value=999,
        initial=1,
        label="Nombre d'exemplaires",
    )

    class Meta:
        model = Book
        fields = ("title", "author", "published_year", "series", "volume")
        labels = {
            "title": "Titre",
            "author": "Auteur",
            "published_year": "Année de publication",
            "series": "Saga / série",
            "volume": "Tome",
        }


class MembershipInviteForm(forms.Form):
    email = forms.EmailField(label="E-mail du membre")
    role = forms.ChoiceField(
        choices=(
            ("member", "Membre"),
            ("librarian", "Bibliothécaire"),
        ),
        label="Rôle",
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class InvitationAccountForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)


class ContactForm(forms.Form):
    nom = forms.CharField(max_length=100, label="Nom")
    email = forms.EmailField(label="E-mail")
    message = forms.CharField(widget=forms.Textarea, label="Message")
