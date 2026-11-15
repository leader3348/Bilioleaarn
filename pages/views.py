from django.shortcuts import render

from .forms import ContactForm

LIVRES = [
    {"titre": "A Game of Thrones", "auteur": "George R. R. Martin", "annee": 1996, "serie": "A Song of Ice and Fire", "tome": 1},
    {"titre": "A Clash of Kings", "auteur": "George R. R. Martin", "annee": 1998, "serie": "A Song of Ice and Fire", "tome": 2},
    {"titre": "A Storm of Swords", "auteur": "George R. R. Martin", "annee": 2000, "serie": "A Song of Ice and Fire", "tome": 3},
    {"titre": "A Feast for Crows", "auteur": "George R. R. Martin", "annee": 2005, "serie": "A Song of Ice and Fire", "tome": 4},
    {"titre": "A Dance with Dragons", "auteur": "George R. R. Martin", "annee": 2011, "serie": "A Song of Ice and Fire", "tome": 5},
    {"titre": "The Hobbit", "auteur": "J. R. R. Tolkien", "annee": 1937, "serie": "Terre du Milieu", "tome": 1},
    {"titre": "The Fellowship of the Ring", "auteur": "J. R. R. Tolkien", "annee": 1954, "serie": "Le Seigneur des Anneaux", "tome": 1},
    {"titre": "The Name of the Wind", "auteur": "Patrick Rothfuss", "annee": 2007, "serie": "The Kingkiller Chronicle", "tome": 1},
    {"titre": "Mistborn: The Final Empire", "auteur": "Brandon Sanderson", "annee": 2006, "serie": "Mistborn", "tome": 1},
    {"titre": "The Eye of the World", "auteur": "Robert Jordan", "annee": 1990, "serie": "The Wheel of Time", "tome": 1},
    {"titre": "A Wizard of Earthsea", "auteur": "Ursula K. Le Guin", "annee": 1968, "serie": "Earthsea", "tome": 1},
    {"titre": "The Two Towers", "auteur": "J. R. R. Tolkien", "annee": 1954, "serie": "Le Seigneur des Anneaux", "tome": 2},
    {"titre": "The Return of the King", "auteur": "J. R. R. Tolkien", "annee": 1955, "serie": "Le Seigneur des Anneaux", "tome": 3},
    {"titre": "The Wise Man's Fear", "auteur": "Patrick Rothfuss", "annee": 2011, "serie": "The Kingkiller Chronicle", "tome": 2},
    {"titre": "The Well of Ascension", "auteur": "Brandon Sanderson", "annee": 2007, "serie": "Mistborn", "tome": 2},
    {"titre": "The Hero of Ages", "auteur": "Brandon Sanderson", "annee": 2008, "serie": "Mistborn", "tome": 3},
    {"titre": "The Great Hunt", "auteur": "Robert Jordan", "annee": 1990, "serie": "The Wheel of Time", "tome": 2},
]

MAISONS = [
    {"nom": "Stark", "devise": "Winter Is Coming", "siege": "Winterfell", "region": "Le Nord"},
    {"nom": "Lannister", "devise": "Hear Me Roar!", "siege": "Castral Roc", "region": "Les Terres de l'Ouest"},
    {"nom": "Targaryen", "devise": "Fire and Blood", "siege": "Peyredragon", "region": "Les Terres de la Couronne"},
    {"nom": "Baratheon", "devise": "Ours Is the Fury", "siege": "Accalmie", "region": "Les Terres de l'Orage"},
    {"nom": "Tyrell", "devise": "Growing Strong", "siege": "Hautjardin", "region": "Le Bief"},
    {"nom": "Martell", "devise": "Unbowed, Unbent, Unbroken", "siege": "Lancehélion", "region": "Dorne"},
]


def accueil(request):
    contexte = {
        "nom_projet": "BiblioLearn",
        "modules": ["Catalogue", "Comptes et rôles", "Emprunts", "Mini-cours"],
        "nb_ressources": len(LIVRES),
        "nouveautes": LIVRES[-4:],
    }
    return render(request, "pages/accueil.html", contexte)


def catalogue(request):
    saga = request.GET.get("serie")
    livres = [l for l in LIVRES if l["serie"] == saga] if saga else LIVRES
    series = sorted({l["serie"] for l in LIVRES})
    return render(request, "pages/catalogue.html", {"livres": livres, "series": series, "serie_active": saga})


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
