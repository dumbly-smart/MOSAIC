"""Supabase access-token verification for FastAPI."""

from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient


class AuthenticationError(ValueError):
    """Raised when a bearer token cannot be trusted."""


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: str
    email: str | None
    claims: dict[str, Any]


class SupabaseJWTVerifier:
    """Verify asymmetric JWTs locally and legacy shared-secret JWTs through Auth."""

    def __init__(self, supabase_url: str, publishable_key: str, *, http_client=None):
        self.base_url = supabase_url.rstrip("/")
        self.publishable_key = publishable_key
        self.http_client = http_client or httpx.Client(timeout=10.0)
        self.jwks = PyJWKClient(f"{self.base_url}/auth/v1/.well-known/jwks.json")

    def verify(self, token: str) -> AuthenticatedUser:
        try:
            algorithm = jwt.get_unverified_header(token).get("alg", "")
            if algorithm == "HS256":
                claims = self._verify_with_auth_server(token)
            else:
                key = self.jwks.get_signing_key_from_jwt(token).key
                claims = jwt.decode(
                    token,
                    key,
                    algorithms=["RS256", "ES256", "EdDSA"],
                    audience="authenticated",
                    issuer=f"{self.base_url}/auth/v1",
                )
        except (httpx.HTTPError, jwt.PyJWTError, KeyError, ValueError) as exc:
            raise AuthenticationError("Invalid or expired Supabase access token") from exc
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("Supabase access token has no subject")
        email = claims.get("email")
        return AuthenticatedUser(subject, email if isinstance(email, str) else None, claims)

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        """Exchange credentials for a Supabase session; intended for Swagger testing."""
        try:
            response = self.http_client.post(
                f"{self.base_url}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": self.publishable_key, "Content-Type": "application/json"},
                json={"email": email, "password": password},
            )
        except httpx.HTTPError as exc:
            raise AuthenticationError("Supabase Auth is unavailable") from exc
        if response.status_code != 200:
            raise AuthenticationError("Invalid email or password")
        body = response.json()
        if not isinstance(body.get("access_token"), str):
            raise AuthenticationError("Supabase returned an invalid session")
        return body

    def _verify_with_auth_server(self, token: str) -> dict[str, Any]:
        response = self.http_client.get(
            f"{self.base_url}/auth/v1/user",
            headers={"apikey": self.publishable_key, "Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            raise AuthenticationError("Supabase rejected the access token")
        body = response.json()
        return {"sub": body["id"], "email": body.get("email"), "role": "authenticated"}
