from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views

app_name = "pages"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("catalogue/", views.catalogue, name="catalogue"),
    path("livres/<int:book_id>/couverture.svg", views.couverture_livre, name="couverture_livre"),
    path("livres/<int:book_id>/", views.fiche_livre, name="fiche_livre"),
    path("maisons/", views.maisons, name="maisons"),
    path("contact/", views.contact, name="contact"),
    path("inscription/", views.inscription, name="inscription"),
    path("inscription/carte-de-membre/", views.confirmation_inscription, name="confirmation_inscription"),
    path(
        "connexion/",
        views.MnemosyneLoginView.as_view(),
        name="connexion",
    ),
    path(
        "mot-de-passe/oublie/",
        auth_views.PasswordResetView.as_view(
            template_name="pages/password_reset_form.html",
            email_template_name="pages/password_reset_email.txt",
            subject_template_name="pages/password_reset_subject.txt",
            success_url=reverse_lazy("pages:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "mot-de-passe/confirmation/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="pages/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "mot-de-passe/reinitialiser/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="pages/password_reset_confirm.html",
            success_url=reverse_lazy("pages:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "mot-de-passe/termine/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="pages/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),
    path("espace/", views.dashboard, name="dashboard"),
    path("espace/objectif/", views.mettre_a_jour_objectif, name="objectif_lecture"),
    path("livres/<int:book_id>/bibliotheque/", views.mettre_a_jour_lecture, name="mettre_a_jour_lecture"),
    path("equipe/", views.team, name="team"),
    path("equipe/inviter/", views.inviter_membre, name="inviter_membre"),
    path("invitations/<str:token>/", views.accepter_invitation, name="accepter_invitation"),
    path("catalogue/ajouter/", views.ajouter_livre, name="ajouter_livre"),
    path("emprunts/<int:inventory_id>/emprunter/", views.emprunter, name="emprunter"),
    path("emprunts/<int:loan_id>/retourner/", views.rendre_livre, name="rendre_livre"),
    path("abonnement/", views.billing, name="billing"),
    path("abonnement/checkout/", views.creer_checkout, name="creer_checkout"),
    path("abonnement/portail/", views.ouvrir_portail_facturation, name="portail_facturation"),
    path("webhooks/stripe/", views.stripe_webhook, name="stripe_webhook"),
]
