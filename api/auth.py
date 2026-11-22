"""Login with Supabase Auth.

The browser signs in with Supabase and sends its access token on every request
(`Authorization: Bearer ...`, or `?access_token=` for the WebSocket and <video>
URLs, which can't set headers). We verify the token's signature here and map
the Supabase user to a local user id.

When SUPABASE_URL isn't set, auth is off: everyone is the local demo user. That
keeps local development and the tests key-free.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import HTTPException, Request

from feedback import storage

AUDIENCE = "authenticated"


@dataclass
class User:
    id: int
    auth_id: str | None
    email: str | None


def auth_enabled() -> bool:
    return bool(os.getenv("SUPABASE_URL"))


@lru_cache(maxsize=1)
def _jwks() -> jwt.PyJWKClient:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def verify_token(token: str) -> dict:
    """Return the token's claims, or raise HTTPException(401)."""
    issuer = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1"
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "HS256":
            # Legacy Supabase projects sign with a shared secret.
            secret = os.getenv("SUPABASE_JWT_SECRET")
            if not secret:
                raise HTTPException(401, "Server is missing SUPABASE_JWT_SECRET for this project's tokens.")
            key = secret
        else:
            # Current projects sign with asymmetric keys published at the JWKS endpoint.
            key = _jwks().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=[alg], audience=AUDIENCE, issuer=issuer)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Your session expired. Please sign in again.")
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Please sign in again.")


def user_from_token(token: str | None) -> User:
    if not auth_enabled():
        return User(id=storage.DEMO_USER, auth_id=None, email=None)
    if not token:
        raise HTTPException(401, "Please sign in.")
    claims = verify_token(token)
    email = claims.get("email")
    return User(id=storage.user_for_auth(claims["sub"], email), auth_id=claims["sub"], email=email)


def token_from(request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.query_params.get("access_token")


def current_user(request: Request) -> User:
    """FastAPI dependency: the signed in user (or the demo user when auth is off)."""
    user = getattr(request.state, "user", None)
    if user is None:
        user = user_from_token(token_from(request))
        request.state.user = user
    return user
