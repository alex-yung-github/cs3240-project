from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch

User = get_user_model()

class GoogleLoginTest(TestCase):
    def setUp(self):
        self.client.logout()   # set up test database before running other tests

    @patch('cla.views.id_token.verify_oauth2_token')
    def test_google_login_default_patron(self, mock_verify_token):
        mock_verify_token.return_value = {
            'email': 'newuser@gmail.com',
            'given_name': 'New',
            'family_name': 'User',
            'iat': 1609459200,
            'exp': 9999999999,
        }

        response = self.client.post(reverse('auth_receiver'), {'credential': 'fake-token'}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboards/patron_dashboard.html')

        user = User.objects.get(email='newuser@gmail.com')
        self.assertEqual(user.role, 'patron')