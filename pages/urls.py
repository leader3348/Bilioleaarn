from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "pages"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("catalogue/", views.catalogue, name="catalogue"),
    path("livres/<int:book_id>/", views.fiche_livre, name="fiche_livre"),
    path("maisons/", views.maisons, name="maisons"),
    path("contact/", views.contact, name="contact"),
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="connexion"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),
    path("espace/", views.dashboard, name="dashboard"),
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
