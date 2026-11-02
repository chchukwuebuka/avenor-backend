import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()

class UserModelTests(TestCase):
    def test_create_user_with_email_successful(self):
        email = 'instructor@avenor.com'
        password = 'SecurePassword123!'
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name='Amara',
            last_name='Okonkwo'
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_platform_staff)
        self.assertIsInstance(user.id, uuid.UUID)
        self.assertEqual(user.get_full_name(), 'Amara Okonkwo')

    def test_email_is_normalized_and_lowercased(self):
        user = User.objects.create_user(
            email='LEARNER.TEST@AVENOR.COM',
            password='TestPassword123!',
            first_name='David',
            last_name='Adeyemi'
        )
        self.assertEqual(user.email, 'learner.test@avenor.com')

    def test_create_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email='',
                password='Password123!',
                first_name='Test',
                last_name='User'
            )

    def test_create_superuser_successful(self):
        superuser = User.objects.create_superuser(
            email='admin@avenor.com',
            password='AdminPassword123!',
            first_name='Platform',
            last_name='Admin'
        )
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_platform_staff)
        self.assertTrue(superuser.email_verified)
