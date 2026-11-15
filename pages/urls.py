from django.urls import path
from . import views

app_name = "pages"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("catalogue/", views.catalogue, name="catalogue"),
    path("maisons/", views.maisons, name="maisons"),
    path("contact/", views.contact, name="contact"),
]
