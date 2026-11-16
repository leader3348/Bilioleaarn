from django.db import migrations


BOOKS = [
    ("A Game of Thrones", "George R. R. Martin", 1996, "A Song of Ice and Fire", 1),
    ("A Clash of Kings", "George R. R. Martin", 1998, "A Song of Ice and Fire", 2),
    ("A Storm of Swords", "George R. R. Martin", 2000, "A Song of Ice and Fire", 3),
    ("A Feast for Crows", "George R. R. Martin", 2005, "A Song of Ice and Fire", 4),
    ("A Dance with Dragons", "George R. R. Martin", 2011, "A Song of Ice and Fire", 5),
    ("The Hobbit", "J. R. R. Tolkien", 1937, "Terre du Milieu", 1),
    ("The Fellowship of the Ring", "J. R. R. Tolkien", 1954, "Le Seigneur des Anneaux", 1),
    ("The Two Towers", "J. R. R. Tolkien", 1954, "Le Seigneur des Anneaux", 2),
    ("The Return of the King", "J. R. R. Tolkien", 1955, "Le Seigneur des Anneaux", 3),
    ("The Name of the Wind", "Patrick Rothfuss", 2007, "The Kingkiller Chronicle", 1),
    ("The Wise Man's Fear", "Patrick Rothfuss", 2011, "The Kingkiller Chronicle", 2),
    ("Mistborn: The Final Empire", "Brandon Sanderson", 2006, "Mistborn", 1),
    ("The Well of Ascension", "Brandon Sanderson", 2007, "Mistborn", 2),
    ("The Hero of Ages", "Brandon Sanderson", 2008, "Mistborn", 3),
    ("The Way of Kings", "Brandon Sanderson", 2010, "The Stormlight Archive", 1),
    ("Words of Radiance", "Brandon Sanderson", 2014, "The Stormlight Archive", 2),
    ("The Eye of the World", "Robert Jordan", 1990, "The Wheel of Time", 1),
    ("The Great Hunt", "Robert Jordan", 1990, "The Wheel of Time", 2),
    ("The Dragon Reborn", "Robert Jordan", 1991, "The Wheel of Time", 3),
    ("A Wizard of Earthsea", "Ursula K. Le Guin", 1968, "Earthsea", 1),
    ("The Tombs of Atuan", "Ursula K. Le Guin", 1970, "Earthsea", 2),
    ("The Lies of Locke Lamora", "Scott Lynch", 2006, "Gentleman Bastard", 1),
    ("Red Seas Under Red Skies", "Scott Lynch", 2007, "Gentleman Bastard", 2),
    ("The Blade Itself", "Joe Abercrombie", 2006, "The First Law", 1),
    ("Before They Are Hanged", "Joe Abercrombie", 2007, "The First Law", 2),
    ("The Last Wish", "Andrzej Sapkowski", 1993, "The Witcher", 1),
    ("Blood of Elves", "Andrzej Sapkowski", 1994, "The Witcher", 2),
    ("The Poppy War", "R. F. Kuang", 2018, "The Poppy War", 1),
    ("The Dragon Republic", "R. F. Kuang", 2019, "The Poppy War", 2),
    ("The Priory of the Orange Tree", "Samantha Shannon", 2019, "Roots of Chaos", 1),
    ("The Fifth Season", "N. K. Jemisin", 2015, "The Broken Earth", 1),
    ("The Obelisk Gate", "N. K. Jemisin", 2016, "The Broken Earth", 2),
    ("The Name of the Rose", "Umberto Eco", 1980, "Historical fantasy", 1),
    ("Jonathan Strange & Mr Norrell", "Susanna Clarke", 2004, "Standalone", 1),
    ("Good Omens", "Terry Pratchett and Neil Gaiman", 1990, "Standalone", 1),
    ("The Colour of Magic", "Terry Pratchett", 1983, "Discworld", 1),
    ("Guards! Guards!", "Terry Pratchett", 1989, "Discworld", 8),
    ("The Once and Future King", "T. H. White", 1958, "Arthurian fantasy", 1),
    ("The Last Unicorn", "Peter S. Beagle", 1968, "Standalone", 1),
    ("The Dark Crystal", "A. C. H. Smith", 1982, "Standalone", 1),
]


def seed_books(apps, schema_editor):
    Book = apps.get_model("pages", "Book")
    for title, author, year, series, volume in BOOKS:
        Book.objects.get_or_create(
            title=title,
            author=author,
            defaults={
                "published_year": year,
                "series": series,
                "volume": volume,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("pages", "0001_initial")]

    operations = [migrations.RunPython(seed_books, migrations.RunPython.noop)]
