# from django.test import TestCase
# from django.urls import reverse 
# from django.contrib.staticfiles.testing import StaticLiveServerTestCase

# # Create your tests here.
# class LandingPage(TestCase):
#     def test_page_loads(self):
#         response = self.client.get(reverse('landing'))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "landing.html")

# class SignInPage(TestCase):
#     def test_sign_in_loads(self):
#         response = self.client.get(reverse('sign_in'))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "sign-in.html")

# class GuestPageTests(TestCase):
#     def test_guest_page_loads(self):
#         response = self.client.get(reverse('guest_home'))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "dashboards/guest-home.html")

# class PatronPageTests(TestCase):
#     def test_patron_page_loads(self):
#         response = self.client.get(reverse('patron_dashboard'))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "dashboards/patron_dashboard.html")  

from django.test import TestCase
from django.urls import reverse 
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test.utils import override_settings

@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class LandingPage(TestCase):
    def test_page_loads(self):
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "landing.html")

@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class SignInPage(TestCase):
    def test_sign_in_loads(self):
        response = self.client.get(reverse('sign_in'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "sign-in.html")

@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class GuestPageTests(TestCase):
    def test_guest_page_loads(self):
        response = self.client.get(reverse('guest_home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboards/guest-home.html")

@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class PatronPageTests(TestCase):
    def test_patron_page_loads(self):
        response = self.client.get(reverse('patron_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboards/patron_dashboard.html")