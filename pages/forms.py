from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Book, ReadingGoal, ReadingShelfEntry


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label="Nom complet")
    email = forms.EmailField(label="E-mail")
    library_name = forms.CharField(max_length=160, label="Nom de votre bibliothèque")

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("first_name", "username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte utilise déjà cette adresse e-mail.")
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.update({"autocomplete": "name"})
        self.fields["username"].widget.attrs.update({"autocomplete": "username"})
        self.fields["username"].widget.attrs.pop("autofocus", None)
        self.fields["email"].widget.attrs.update({"autocomplete": "email"})
        self.fields["library_name"].widget.attrs.update({"autocomplete": "organization"})
        self.fields["password1"].widget.attrs.update({"autocomplete": "new-password"})
        self.fields["password2"].widget.attrs.update({"autocomplete": "new-password"})


class MnemosyneAuthenticationForm(AuthenticationForm):
    remember_me = forms.BooleanField(label="Rester connecté", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "E-mail ou nom d'utilisateur"
        self.fields["username"].widget.attrs.update({"autocomplete": "username"})
        self.fields["username"].widget.attrs.pop("autofocus", None)
        self.fields["password"].widget.attrs.update({"autocomplete": "current-password"})

    def clean(self):
        identifier = self.cleaned_data.get("username", "")
        if "@" not in identifier:
            return super().clean()
        matching_usernames = list(
            get_user_model().objects.filter(email__iexact=identifier)
            .values_list("username", flat=True)[:2]
        )
        if len(matching_usernames) == 1:
            self.cleaned_data["username"] = matching_usernames[0]
        return super().clean()


class BookForm(forms.ModelForm):
    total_copies = forms.IntegerField(
        min_value=1,
        max_value=999,
        initial=1,
        label="Nombre d'exemplaires",
    )

    class Meta:
        model = Book
        fields = ("title", "author", "category", "published_year", "series", "volume")
        labels = {
            "title": "Titre",
            "author": "Auteur",
            "category": "Genre",
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


class ReadingEntryActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=(
            ("status", "Mettre à jour le statut"),
            ("favorite", "Mettre à jour les favoris"),
            ("progress", "Enregistrer la progression"),
            ("bookmark", "Enregistrer le marque-page"),
            ("remove", "Retirer de ma bibliothèque"),
        ),
        widget=forms.HiddenInput,
    )
    status = forms.ChoiceField(choices=ReadingShelfEntry.Status.choices, required=False)
    favorite = forms.BooleanField(required=False)
    progress = forms.IntegerField(required=False, min_value=0, max_value=100)
    bookmark_page = forms.IntegerField(required=False, min_value=1)


class ReadingGoalForm(forms.ModelForm):
    books_target = forms.IntegerField(
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={"min": 1, "max": 365, "inputmode": "numeric"}),
    )

    class Meta:
        model = ReadingGoal
        fields = ("books_target",)
        labels = {"books_target": "Livres à lire cette année"}
