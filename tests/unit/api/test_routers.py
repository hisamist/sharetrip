"""
Unit tests for HTTP routers.
Uses FastAPI TestClient with SQLite in-memory + FakeRedis — no external services.
Covers: all routers, schemas, DB models, main.py health endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from sharetrip.api.dependencies import (
    get_currency_port,
    get_db_session,
    get_redis_client,
)
from sharetrip.domain.interfaces.currency_port import CurrencyPort
from sharetrip.infrastructure.auth.jwt_service import JWTService
from sharetrip.infrastructure.db.models import Base
from sharetrip.main import app

# ─── Fakes ────────────────────────────────────────────────────────────────────


class FakeRedis:
    def __init__(self):
        self._store: dict = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ex=None):
        self._store[key] = value

    def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)


class StubCurrencyPort(CurrencyPort):
    def get_rate(self, from_currency: str, to_currency: str) -> float:
        return 1.0


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def client(db_engine):
    Session = sessionmaker(bind=db_engine)
    fake_redis = FakeRedis()

    def override_db():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_redis_client] = lambda: fake_redis
    app.dependency_overrides[get_currency_port] = lambda: StubCurrencyPort()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _register_and_login(client: TestClient, email: str = "alice@example.com") -> str:
    username = email.split("@")[0]
    client.post(
        "/auth/register",
        json={
            "username": username,
            "display_name": username.capitalize(),
            "email": email,
            "password": "s3cr3t",
        },
    )
    resp = client.post("/auth/login", json={"email": email, "password": "s3cr3t"})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Health check (main.py) ───────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_returns_healthy_status(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "env" in data


# ─── Auth router ──────────────────────────────────────────────────────────────


class TestAuthRouter:
    def test_register_returns_201_with_user_data(self, client):
        resp = client.post(
            "/auth/register",
            json={
                "username": "bob",
                "display_name": "Bob",
                "email": "bob@example.com",
                "password": "s3cr3t",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "bob"
        assert data["email"] == "bob@example.com"
        assert "id" in data
        assert "password_hash" not in data

    def test_register_includes_optional_phone(self, client):
        resp = client.post(
            "/auth/register",
            json={
                "username": "bob",
                "display_name": "Bob",
                "email": "bob@example.com",
                "password": "s3cr3t",
                "phone": "+33612345678",
            },
        )
        assert resp.status_code == 201

    def test_register_returns_422_when_email_invalid(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "bob", "display_name": "Bob", "email": "not-an-email", "password": "s3cr3t"},
        )
        assert resp.status_code == 422

    def test_register_returns_422_when_missing_required_fields(self, client):
        resp = client.post("/auth/register", json={"username": "bob"})
        assert resp.status_code == 422

    def test_register_returns_409_on_duplicate_email(self, client):
        payload = {
            "username": "bob",
            "display_name": "Bob",
            "email": "bob@example.com",
            "password": "s3cr3t",
        }
        client.post("/auth/register", json=payload)
        resp = client.post("/auth/register", json={**payload, "username": "bob2"})
        assert resp.status_code == 409

    def test_register_returns_409_on_duplicate_username(self, client):
        client.post(
            "/auth/register",
            json={"username": "alice", "display_name": "Alice", "email": "alice@example.com", "password": "s3cr3t"},
        )
        resp = client.post(
            "/auth/register",
            json={"username": "alice", "display_name": "Alice2", "email": "alice2@example.com", "password": "s3cr3t"},
        )
        assert resp.status_code == 409

    def test_login_returns_token_and_bearer_type(self, client):
        token = _register_and_login(client)
        assert token
        resp = client.post("/auth/login", json={"email": "alice@example.com", "password": "s3cr3t"})
        assert resp.json()["token_type"] == "bearer"

    def test_login_returns_401_on_wrong_password(self, client):
        client.post(
            "/auth/register",
            json={"username": "bob", "display_name": "Bob", "email": "bob@example.com", "password": "s3cr3t"},
        )
        resp = client.post("/auth/login", json={"email": "bob@example.com", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_returns_401_on_unknown_email(self, client):
        resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "any"})
        assert resp.status_code == 401

    def test_me_returns_current_user(self, client):
        token = _register_and_login(client)
        resp = client.get("/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@example.com"

    def test_me_returns_401_without_token(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_returns_401_with_garbage_token(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer not.a.valid.token"})
        assert resp.status_code == 401

    def test_me_returns_401_when_user_not_in_db(self, client):
        """Valid JWT but user_id does not exist in DB → 401."""
        jwt = JWTService(secret_key="test-secret-key-minimum-32-characters-long")
        token = jwt.create_access_token(user_id=9999, email="ghost@example.com")
        resp = client.get("/auth/me", headers=_auth(token))
        assert resp.status_code == 401


# ─── Trips router ─────────────────────────────────────────────────────────────


class TestTripsRouter:
    def test_create_trip_returns_201(self, client):
        token = _register_and_login(client)
        resp = client.post("/trips", json={"name": "Paris", "base_currency": "EUR"}, headers=_auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Paris"
        assert data["base_currency"] == "EUR"
        assert "id" in data

    def test_create_trip_returns_401_without_token(self, client):
        resp = client.post("/trips", json={"name": "Paris", "base_currency": "EUR"})
        assert resp.status_code == 401

    def test_create_trip_returns_422_when_missing_currency(self, client):
        token = _register_and_login(client)
        resp = client.post("/trips", json={"name": "Paris"}, headers=_auth(token))
        assert resp.status_code == 422

    def test_list_trips_returns_empty_for_new_user(self, client):
        token = _register_and_login(client)
        resp = client.get("/trips", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_trips_returns_created_trips(self, client):
        token = _register_and_login(client)
        client.post("/trips", json={"name": "Paris", "base_currency": "EUR"}, headers=_auth(token))
        client.post("/trips", json={"name": "Tokyo", "base_currency": "JPY"}, headers=_auth(token))
        resp = client.get("/trips", headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_trips_returns_401_without_token(self, client):
        resp = client.get("/trips")
        assert resp.status_code == 401

    def test_get_trip_returns_200(self, client):
        token = _register_and_login(client)
        trip_id = client.post("/trips", json={"name": "Paris", "base_currency": "EUR"}, headers=_auth(token)).json()["id"]
        resp = client.get(f"/trips/{trip_id}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Paris"

    def test_get_trip_returns_404_when_not_exists(self, client):
        token = _register_and_login(client)
        resp = client.get("/trips/9999", headers=_auth(token))
        assert resp.status_code == 404

    def test_get_trip_returns_403_when_not_member(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")
        trip_id = client.post(
            "/trips", json={"name": "Alice Trip", "base_currency": "EUR"}, headers=_auth(token_alice)
        ).json()["id"]
        resp = client.get(f"/trips/{trip_id}", headers=_auth(token_bob))
        assert resp.status_code == 403

    def test_list_members_returns_creator(self, client):
        token = _register_and_login(client)
        trip_id = client.post("/trips", json={"name": "Trip", "base_currency": "EUR"}, headers=_auth(token)).json()["id"]
        resp = client.get(f"/trips/{trip_id}/members", headers=_auth(token))
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) == 1
        assert "role" in members[0]
        assert "display_name" in members[0]

    def test_list_members_returns_403_when_not_member(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")
        trip_id = client.post(
            "/trips", json={"name": "Trip", "base_currency": "EUR"}, headers=_auth(token_alice)
        ).json()["id"]
        resp = client.get(f"/trips/{trip_id}/members", headers=_auth(token_bob))
        assert resp.status_code == 403

    def test_add_member_returns_204(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")
        bob_id = client.get("/auth/me", headers=_auth(token_bob)).json()["id"]
        trip_id = client.post(
            "/trips", json={"name": "Trip", "base_currency": "EUR"}, headers=_auth(token_alice)
        ).json()["id"]
        resp = client.post(f"/trips/{trip_id}/members", json={"user_id": bob_id}, headers=_auth(token_alice))
        assert resp.status_code == 204

    def test_add_member_appears_in_member_list(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")
        bob_id = client.get("/auth/me", headers=_auth(token_bob)).json()["id"]
        trip_id = client.post(
            "/trips", json={"name": "Trip", "base_currency": "EUR"}, headers=_auth(token_alice)
        ).json()["id"]
        client.post(f"/trips/{trip_id}/members", json={"user_id": bob_id}, headers=_auth(token_alice))
        members = client.get(f"/trips/{trip_id}/members", headers=_auth(token_alice)).json()
        assert len(members) == 2
        assert any(m["user_id"] == bob_id for m in members)

    def test_add_member_returns_404_when_user_not_found(self, client):
        token = _register_and_login(client)
        trip_id = client.post("/trips", json={"name": "Trip", "base_currency": "EUR"}, headers=_auth(token)).json()["id"]
        resp = client.post(f"/trips/{trip_id}/members", json={"user_id": 9999}, headers=_auth(token))
        assert resp.status_code == 404

    def test_add_member_returns_409_when_already_member(self, client):
        token = _register_and_login(client)
        user_id = client.get("/auth/me", headers=_auth(token)).json()["id"]
        trip_id = client.post("/trips", json={"name": "Trip", "base_currency": "EUR"}, headers=_auth(token)).json()["id"]
        resp = client.post(f"/trips/{trip_id}/members", json={"user_id": user_id}, headers=_auth(token))
        assert resp.status_code == 409

    def test_add_member_returns_422_when_missing_user_id(self, client):
        token = _register_and_login(client)
        trip_id = client.post("/trips", json={"name": "Trip", "base_currency": "EUR"}, headers=_auth(token)).json()["id"]
        resp = client.post(f"/trips/{trip_id}/members", json={}, headers=_auth(token))
        assert resp.status_code == 422

    def test_list_trips_shows_only_user_trips(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")
        client.post("/trips", json={"name": "Alice Trip", "base_currency": "EUR"}, headers=_auth(token_alice))
        client.post("/trips", json={"name": "Bob Trip", "base_currency": "USD"}, headers=_auth(token_bob))
        resp = client.get("/trips", headers=_auth(token_alice))
        names = [t["name"] for t in resp.json()]
        assert "Alice Trip" in names
        assert "Bob Trip" not in names


# ─── Expenses router ──────────────────────────────────────────────────────────


class TestExpensesRouter:
    @pytest.fixture()
    def trip_ctx(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")
        trip = client.post(
            "/trips", json={"name": "Tokyo", "base_currency": "EUR"}, headers=_auth(token_alice)
        ).json()
        bob_id = client.get("/auth/me", headers=_auth(token_bob)).json()["id"]
        client.post(f"/trips/{trip['id']}/members", json={"user_id": bob_id}, headers=_auth(token_alice))
        return {"trip": trip, "token_alice": token_alice, "token_bob": token_bob, "bob_id": bob_id}

    def test_add_expense_returns_201(self, client, trip_ctx):
        resp = client.post(
            f"/trips/{trip_ctx['trip']['id']}/expenses",
            json={"title": "Sushi", "amount": 100.0, "currency": "EUR", "split_type": "equal"},
            headers=_auth(trip_ctx["token_alice"]),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Sushi"
        assert data["amount_pivot"] == 100.0
        assert data["split_type"] == "equal"
        assert len(data["splits"]) == 2

    def test_add_expense_with_category(self, client, trip_ctx):
        resp = client.post(
            f"/trips/{trip_ctx['trip']['id']}/expenses",
            json={"title": "Hotel", "amount": 200.0, "currency": "EUR", "split_type": "equal", "category": "accommodation"},
            headers=_auth(trip_ctx["token_alice"]),
        )
        assert resp.status_code == 201
        assert resp.json()["category"] == "accommodation"

    def test_add_expense_with_foreign_currency(self, client, trip_ctx):
        resp = client.post(
            f"/trips/{trip_ctx['trip']['id']}/expenses",
            json={"title": "Ramen", "amount": 1500.0, "currency": "JPY", "split_type": "equal"},
            headers=_auth(trip_ctx["token_alice"]),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_currency"] == "JPY"
        assert data["exchange_rate"] == 1.0

    def test_add_expense_returns_422_on_invalid_split_type(self, client, trip_ctx):
        resp = client.post(
            f"/trips/{trip_ctx['trip']['id']}/expenses",
            json={"title": "X", "amount": 10.0, "currency": "EUR", "split_type": "INVALID"},
            headers=_auth(trip_ctx["token_alice"]),
        )
        assert resp.status_code == 422

    def test_add_expense_returns_422_when_missing_title(self, client, trip_ctx):
        resp = client.post(
            f"/trips/{trip_ctx['trip']['id']}/expenses",
            json={"amount": 10.0, "currency": "EUR", "split_type": "equal"},
            headers=_auth(trip_ctx["token_alice"]),
        )
        assert resp.status_code == 422

    def test_add_expense_returns_404_on_unknown_trip(self, client):
        token = _register_and_login(client)
        resp = client.post(
            "/trips/9999/expenses",
            json={"title": "X", "amount": 10.0, "currency": "EUR", "split_type": "equal"},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_list_expenses_returns_all_expenses(self, client, trip_ctx):
        for title in ["Lunch", "Museum", "Transport"]:
            client.post(
                f"/trips/{trip_ctx['trip']['id']}/expenses",
                json={"title": title, "amount": 30.0, "currency": "EUR", "split_type": "equal"},
                headers=_auth(trip_ctx["token_alice"]),
            )
        resp = client.get(f"/trips/{trip_ctx['trip']['id']}/expenses", headers=_auth(trip_ctx["token_alice"]))
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_expenses_includes_splits(self, client, trip_ctx):
        client.post(
            f"/trips/{trip_ctx['trip']['id']}/expenses",
            json={"title": "Dinner", "amount": 100.0, "currency": "EUR", "split_type": "equal"},
            headers=_auth(trip_ctx["token_alice"]),
        )
        resp = client.get(f"/trips/{trip_ctx['trip']['id']}/expenses", headers=_auth(trip_ctx["token_alice"]))
        splits = resp.json()[0]["splits"]
        assert len(splits) == 2
        amounts = sorted(s["amount_owed"] for s in splits)
        assert all(abs(a - 50.0) < 0.01 for a in amounts)

    def test_add_expense_returns_401_without_token(self, client, trip_ctx):
        resp = client.post(
            f"/trips/{trip_ctx['trip']['id']}/expenses",
            json={"title": "X", "amount": 10.0, "currency": "EUR", "split_type": "equal"},
        )
        assert resp.status_code == 401


# ─── Settlements router ───────────────────────────────────────────────────────


class TestSettlementsRouter:
    @pytest.fixture()
    def trip_ctx(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")
        trip = client.post(
            "/trips", json={"name": "Tokyo", "base_currency": "EUR"}, headers=_auth(token_alice)
        ).json()
        bob_id = client.get("/auth/me", headers=_auth(token_bob)).json()["id"]
        alice_id = client.get("/auth/me", headers=_auth(token_alice)).json()["id"]
        client.post(f"/trips/{trip['id']}/members", json={"user_id": bob_id}, headers=_auth(token_alice))
        return {
            "trip": trip,
            "token_alice": token_alice,
            "token_bob": token_bob,
            "alice_id": alice_id,
            "bob_id": bob_id,
        }

    def test_returns_empty_list_when_no_expenses(self, client, trip_ctx):
        resp = client.get(f"/trips/{trip_ctx['trip']['id']}/settlements", headers=_auth(trip_ctx["token_alice"]))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_transfer_when_alice_paid_for_both(self, client, trip_ctx):
        client.post(
            f"/trips/{trip_ctx['trip']['id']}/expenses",
            json={"title": "Dinner", "amount": 100.0, "currency": "EUR", "split_type": "equal"},
            headers=_auth(trip_ctx["token_alice"]),
        )
        resp = client.get(f"/trips/{trip_ctx['trip']['id']}/settlements", headers=_auth(trip_ctx["token_alice"]))
        assert resp.status_code == 200
        transfers = resp.json()
        assert len(transfers) == 1
        assert transfers[0]["from_user_id"] == trip_ctx["bob_id"]
        assert transfers[0]["to_user_id"] == trip_ctx["alice_id"]
        assert abs(transfers[0]["amount"] - 50.0) < 0.01

    def test_returns_no_transfers_when_balanced(self, client, trip_ctx):
        for token in [trip_ctx["token_alice"], trip_ctx["token_bob"]]:
            client.post(
                f"/trips/{trip_ctx['trip']['id']}/expenses",
                json={"title": "Expense", "amount": 60.0, "currency": "EUR", "split_type": "equal"},
                headers=_auth(token),
            )
        resp = client.get(f"/trips/{trip_ctx['trip']['id']}/settlements", headers=_auth(trip_ctx["token_alice"]))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_404_on_unknown_trip(self, client):
        token = _register_and_login(client)
        resp = client.get("/trips/9999/settlements", headers=_auth(token))
        assert resp.status_code == 404

    def test_returns_401_without_token(self, client):
        resp = client.get("/trips/1/settlements")
        assert resp.status_code == 401

    def test_pdf_returns_pdf_with_expenses(self, client, trip_ctx):
        client.post(
            f"/trips/{trip_ctx['trip']['id']}/expenses",
            json={"title": "Dinner", "amount": 100.0, "currency": "EUR", "split_type": "equal"},
            headers=_auth(trip_ctx["token_alice"]),
        )
        resp = client.get(
            f"/trips/{trip_ctx['trip']['id']}/settlements/pdf",
            headers=_auth(trip_ctx["token_alice"]),
        )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
        assert resp.content[:4] == b"%PDF"

    def test_pdf_returns_pdf_with_no_expenses(self, client, trip_ctx):
        resp = client.get(
            f"/trips/{trip_ctx['trip']['id']}/settlements/pdf",
            headers=_auth(trip_ctx["token_alice"]),
        )
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"

    def test_pdf_includes_correct_filename_header(self, client, trip_ctx):
        resp = client.get(
            f"/trips/{trip_ctx['trip']['id']}/settlements/pdf",
            headers=_auth(trip_ctx["token_alice"]),
        )
        assert "attachment" in resp.headers["content-disposition"]
        assert str(trip_ctx["trip"]["id"]) in resp.headers["content-disposition"]

    def test_pdf_returns_403_when_not_member(self, client, trip_ctx):
        token_stranger = _register_and_login(client, "stranger@example.com")
        resp = client.get(
            f"/trips/{trip_ctx['trip']['id']}/settlements/pdf",
            headers=_auth(token_stranger),
        )
        assert resp.status_code == 403

    def test_pdf_returns_404_on_unknown_trip(self, client):
        token = _register_and_login(client)
        resp = client.get("/trips/9999/settlements/pdf", headers=_auth(token))
        assert resp.status_code == 404
