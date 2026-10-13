"""Integration tests for the authentication flow."""
from __future__ import annotations


def test_register_login_refresh_cycle(client):
    register = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@vision3d.dev", "username": "alice", "password": "StrongPass123!"},
    )
    assert register.status_code == 201
    data = register.json()
    assert data["user"]["email"] == "alice@vision3d.dev"
    assert data["user"]["role"] == "user"
    assert data["tokens"]["access_token"]
    assert data["tokens"]["refresh_token"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@vision3d.dev", "password": "StrongPass123!"},
    )
    assert login.status_code == 200
    assert login.json()["tokens"]["access_token"]

    refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": data["tokens"]["refresh_token"]}
    )
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]


def test_duplicate_registration_rejected(client):
    payload = {"email": "dup@vision3d.dev", "username": "dupuser", "password": "StrongPass123!"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_wrong_password_returns_401(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "bob@vision3d.dev", "username": "bobuser", "password": "StrongPass123!"},
    )
    response = client.post(
        "/api/v1/auth/login", json={"email": "bob@vision3d.dev", "password": "NopeNope123!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"


def test_protected_route_requires_token(client):
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/projects").status_code == 401


def test_password_strength_enforced(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@vision3d.dev", "username": "weakuser", "password": "short"},
    )
    assert response.status_code in (400, 422)
    assert response.json()["error"]["code"] == "validation_error"


def test_me_endpoint(auth_headers, client):
    response = client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "tester"
    assert response.json()["metrics"]["projects_created"] == 0


def test_update_profile_requires_valid_username(client, auth_headers):
    bad = client.patch(
        "/api/v1/users/me", headers=auth_headers, json={"username": "not valid!"}
    )
    assert bad.status_code == 422
    good = client.patch(
        "/api/v1/users/me", headers=auth_headers, json={"preferences": {"theme": "dark"}}
    )
    assert good.status_code == 200
    assert good.json()["preferences"]["theme"] == "dark"
