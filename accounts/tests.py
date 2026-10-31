from django.test import SimpleTestCase
from ninja.testing import TestClient
from skillsetu_backend.api import api
from accounts.schemas import (
    OAuthUrlOutSchema,
    OAuthLoginInSchema,
    OAuthAuthResponseOut
)
from accounts.api import _verify_google_token, _verify_github_token

class OAuth2AuthenticationTest(SimpleTestCase):
    def setUp(self):
        self.client = TestClient(api)

    def test_oauth_authorization_urls(self):
        response = self.client.get("/auth/oauth/urls")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("google_auth_url", data)
        self.assertIn("github_auth_url", data)
        self.assertIn("accounts.google.com", data["google_auth_url"])
        self.assertIn("github.com/login/oauth/authorize", data["github_auth_url"])

    def test_verify_google_token_mock(self):
        info = _verify_google_token("demo_google_priya_sharma")
        self.assertEqual(info["email"], "priya_sharma@gmail.com")
        self.assertIn("google_priya_sharma", info["sub"])

    def test_verify_github_token_mock(self):
        info = _verify_github_token("demo_github_ananya_dev")
        self.assertIn("ananya_dev", info["email"])
        self.assertIn("gh_ananya_dev", info["sub"])

    def test_oauth_schemas(self):
        schema = OAuthAuthResponseOut(
            access_token="test.jwt.token",
            token_type="bearer",
            role="STUDENT",
            username="priya_sharma",
            email="priya@gmail.com",
            avatar_url="https://avatar.example.com",
            is_new_user=True,
            auth_provider="GOOGLE",
            message="Success"
        )
        self.assertTrue(schema.is_new_user)
        self.assertEqual(schema.auth_provider, "GOOGLE")


