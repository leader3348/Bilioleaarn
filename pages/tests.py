from django.test import TestCase


class BibliothequePagesTests(TestCase):
    def test_homepage_displays_new_arrivals(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Great Hunt")

    def test_catalogue_includes_new_books_and_filters_by_series(self):
        response = self.client.get("/catalogue/")

        self.assertContains(response, "The Two Towers")
        self.assertContains(response, "The Wise Man&#x27;s Fear")

        filtered_response = self.client.get("/catalogue/?serie=Mistborn")
        self.assertContains(filtered_response, "The Well of Ascension")
        self.assertNotContains(filtered_response, "The Two Towers")

    def test_homepage_uses_omar_footer_and_hides_about_page_link(self):
        response = self.client.get("/")

        self.assertContains(response, "Omar")
        self.assertNotContains(response, "ESMA Marrakech")
        self.assertNotContains(response, "À propos")
        self.assertEqual(self.client.get("/a-propos/").status_code, 404)

