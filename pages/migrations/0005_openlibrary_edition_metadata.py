from django.db import migrations, models


OPEN_LIBRARY_BOOKS = {
    "A Game of Thrones": ("/works/OL257943W", 9269962, "borrowable"),
    "A Clash of Kings": ("/works/OL257939W", 8231751, "borrowable"),
    "A Storm of Swords": ("/works/OL257914W", 15124196, "borrowable"),
    "A Feast for Crows": ("/works/OL257948W", 6501256, "borrowable"),
    "A Dance with Dragons": ("/works/OL1955906W", 11298743, "printdisabled"),
    "The Hobbit": ("/works/OL27482W", 14627509, "borrowable"),
    "The Fellowship of the Ring": ("/works/OL27513W", 14627060, "borrowable"),
    "The Two Towers": ("/works/OL27479W", 14627564, "borrowable"),
    "The Return of the King": ("/works/OL27455W", 14627062, "borrowable"),
    "The Name of the Wind": ("/works/OL8479867W", 11480483, "borrowable"),
    "The Wise Man's Fear": ("/works/OL8479869W", 8294024, "borrowable"),
    "Mistborn: The Final Empire": ("/works/OL25870671W", None, "no_ebook"),
    "The Well of Ascension": ("/works/OL5738150W", 14658341, "borrowable"),
    "The Hero of Ages": ("/works/OL5738154W", 14658094, "borrowable"),
    "The Way of Kings": ("/works/OL15358691W", 14658316, "printdisabled"),
    "Words of Radiance": ("/works/OL16813053W", 14658334, "printdisabled"),
    "The Eye of the World": ("/works/OL7924103W", 980232, "borrowable"),
    "The Great Hunt": ("/works/OL7924135W", 182352, "borrowable"),
    "The Dragon Reborn": ("/works/OL7924143W", 603239, "printdisabled"),
    "A Wizard of Earthsea": ("/works/OL59798W", 13617691, "borrowable"),
    "The Tombs of Atuan": ("/works/OL59801W", 6633403, "printdisabled"),
    "The Lies of Locke Lamora": ("/works/OL8369445W", 6307636, "printdisabled"),
    "Red Seas Under Red Skies": ("/works/OL21156920W", 12439889, "no_ebook"),
    "The Blade Itself": ("/works/OL8400950W", 14543422, "printdisabled"),
    "Before They Are Hanged": ("/works/OL8400946W", 14595640, "borrowable"),
    "The Last Wish": ("/works/OL42560110W", None, "no_ebook"),
    "The Poppy War": ("/works/OL19351054W", 8463552, "no_ebook"),
    "The Dragon Republic": ("/works/OL19629129W", 8539487, "no_ebook"),
    "The Priory of the Orange Tree": ("/works/OL20157354W", 8802446, "printdisabled"),
    "The Fifth Season": ("/works/OL17363125W", 8133598, "printdisabled"),
    "The Obelisk Gate": ("/works/OL17842279W", 8138324, "printdisabled"),
    "The Name of the Rose": ("/works/OL37535473W", 15023290, "printdisabled"),
    "Jonathan Strange & Mr Norrell": ("/works/OL5703422W", 525391, "printdisabled"),
    "The Colour of Magic": ("/works/OL453657W", 14647238, "borrowable"),
    "Guards! Guards!": ("/works/OL453735W", 13095550, "borrowable"),
    "The Once and Future King": ("/works/OL1388028W", 6630521, "printdisabled"),
    "The Last Unicorn": ("/works/OL26459W", 294651, "printdisabled"),
    "The Dark Crystal": ("/works/OL17077051W", 8790014, "borrowable"),
}


def populate_edition_metadata(apps, schema_editor):
    Book = apps.get_model("pages", "Book")
    for title, (work_key, cover_id, ebook_access) in OPEN_LIBRARY_BOOKS.items():
        Book.objects.filter(title=title).update(
            openlibrary_work_key=work_key,
            openlibrary_cover_id=cover_id,
            openlibrary_ebook_access=ebook_access,
        )


class Migration(migrations.Migration):
    dependencies = [("pages", "0004_remove_membership_unique_library_membership_and_more")]

    operations = [
        migrations.AddField(
            model_name="book",
            name="openlibrary_work_key",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="book",
            name="openlibrary_cover_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="book",
            name="openlibrary_ebook_access",
            field=models.CharField(blank=True, max_length=24),
        ),
        migrations.RunPython(populate_edition_metadata, migrations.RunPython.noop),
    ]
