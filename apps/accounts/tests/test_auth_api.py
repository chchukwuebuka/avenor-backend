from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('auth-register')
        self.login_url = reverse('auth-login')
        self.me_url = reverse('auth-me')
        self.health_url = reverse('health-check')

    def test_health_check_endpoint(self):
        res = self.client.get(self.health_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()['status'], 'healthy')

    def test_register_user_successful(self):
        payload = {
            'email': 'new.learner@avenor.com',
            'password': 'StrongPassword123!',
            'password_confirm': 'StrongPassword123!',
            'first_name': 'Chidi',
            'last_name': 'Eze',
            'phone_number': '+2348012345678',
        }
        res = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.json()['success'])
        self.assertEqual(res.json()['data']['email'], 'new.learner@avenor.com')
        self.assertTrue(User.objects.filter(email='new.learner@avenor.com').exists())

    def test_register_password_mismatch_returns_error_envelope(self):
        payload = {
            'email': 'mismatch@avenor.com',
            'password': 'StrongPassword123!',
            'password_confirm': 'DifferentPassword123!',
            'first_name': 'Test',
            'last_name': 'User',
        }
        res = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn('password_confirm', data['errors'])

    def test_login_obtains_jwt_tokens_and_profile(self):
        User.objects.create_user(
            email='active.staff@avenor.com',
            password='StaffPassword123!',
            first_name='Kelechi',
            last_name='Nnamdi',
            is_platform_staff=True
        )
        payload = {
            'email': 'active.staff@avenor.com',
            'password': 'StaffPassword123!'
        }
        res = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertEqual(data['user']['email'], 'active.staff@avenor.com')
        self.assertTrue(data['user']['is_platform_staff'])

    def test_me_endpoint_requires_authentication(self):
        res = self.client.get(self.me_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(res.json()['success'])

    def test_me_endpoint_authenticated(self):
        user = User.objects.create_user(
            email='authenticated@avenor.com',
            password='AuthPassword123!',
            first_name='Fatima',
            last_name='Bello'
        )
        self.client.force_authenticate(user=user)
        res = self.client.get(self.me_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.json()['success'])
        self.assertEqual(res.json()['data']['email'], 'authenticated@avenor.com')
