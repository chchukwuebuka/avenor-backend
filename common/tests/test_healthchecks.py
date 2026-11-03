from django.test import TestCase, Client


class HealthAndReadinessProbesTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_healthz_probe_status_and_payload(self):
        response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'healthy')
        self.assertEqual(data.get('platform'), 'AVENOR SaaS API')
        self.assertIn('timestamp', data)

    def test_livez_probe_liveness(self):
        response = self.client.get('/livez/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'alive')
        self.assertIn('timestamp', data)

    def test_readyz_probe_database_and_cache(self):
        response = self.client.get('/readyz/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'ready')
        self.assertIn('checks', data)
        self.assertEqual(data['checks'].get('database'), 'connected')
        self.assertIn(data['checks'].get('cache'), ('connected', 'degraded'))

    def test_legacy_api_health_endpoint(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'healthy')
