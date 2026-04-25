"""
Integration tests for the HTTP API layer.
Uses FastAPI TestClient + SQLite in-memory + FakeRedis + StubCurrencyPort.
No external services required.
"""

import pytest
from fastapi.testclient import TestClient
from sharetrip.api.dependencies import (
    get_currency_port,
    get_db_session,
    get_redis_client,
)
from sharetrip.domain.interfaces.currency_port import CurrencyPort
from sharetrip.infrastructure.db.models import Base
from sharetrip.main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ─── Fakes ────────────────────────────────────────────────────────────────────


class FakeRedis:
    """Dict-based Redis stub — no TTL enforcement needed for tests."""

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
    """Always returns 1.0 — keeps amount_pivot == amount in tests."""

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
    """TestClient with all external dependencies overridden."""
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
    """Register a user and return the JWT access token."""
    client.post(
        "/auth/register",
        json={
            "username": email.split("@")[0],
            "display_name": email.split("@")[0].capitalize(),
            "email": email,
            "password": "s3cr3t",
        },
    )
    resp = client.post("/auth/login", json={"email": email, "password": "s3cr3t"})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Validation (422) ─────────────────────────────────────────────────────────


class TestValidation:
    def test_should_return_422_when_register_missing_email(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "bob", "display_name": "Bob", "password": "s3cr3t"},
        )
        assert resp.status_code == 422

    def test_should_return_422_when_register_missing_username(self, client):
        resp = client.post(
            "/auth/register",
            json={
                "display_name": "Bob",
                "email": "bob@example.com",
                "password": "s3cr3t",
            },
        )
        assert resp.status_code == 422

    def test_should_return_422_when_register_missing_password(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "bob", "display_name": "Bob", "email": "bob@example.com"},
        )
        assert resp.status_code == 422

    def test_should_return_422_when_create_trip_missing_currency(self, client):
        token = _register_and_login(client)
        resp = client.post("/trips", json={"name": "Paris"}, headers=_auth(token))
        assert resp.status_code == 422

    def test_should_return_422_when_create_trip_missing_name(self, client):
        token = _register_and_login(client)
        resp = client.post("/trips", json={"base_currency": "EUR"}, headers=_auth(token))
        assert resp.status_code == 422

    def test_should_return_422_when_expense_invalid_split_type(self, client):
        token = _register_and_login(client)
        trip_id = client.post(
            "/trips",
            json={"name": "Trip", "base_currency": "EUR"},
            headers=_auth(token),
        ).json()["id"]
        resp = client.post(
            f"/trips/{trip_id}/expenses",
            json={
                "title": "Dinner",
                "amount": 100.0,
                "currency": "EUR",
                "split_type": "INVALID",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_should_return_422_when_expense_missing_title(self, client):
        token = _register_and_login(client)
        trip_id = client.post(
            "/trips",
            json={"name": "Trip", "base_currency": "EUR"},
            headers=_auth(token),
        ).json()["id"]
        resp = client.post(
            f"/trips/{trip_id}/expenses",
            json={"amount": 100.0, "currency": "EUR", "split_type": "equal"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_should_return_422_when_add_member_missing_user_id(self, client):
        token = _register_and_login(client)
        trip_id = client.post(
            "/trips",
            json={"name": "Trip", "base_currency": "EUR"},
            headers=_auth(token),
        ).json()["id"]
        resp = client.post(f"/trips/{trip_id}/members", json={}, headers=_auth(token))
        assert resp.status_code == 422


# ─── Auth ─────────────────────────────────────────────────────────────────────


class TestAuth:
    def test_should_return_201_when_registration_is_valid(self, client):
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

    def test_should_return_409_when_email_already_registered(self, client):
        payload = {
            "username": "bob",
            "display_name": "Bob",
            "email": "bob@example.com",
            "password": "s3cr3t",
        }
        client.post("/auth/register", json=payload)
        resp = client.post(
            "/auth/register",
            json={**payload, "username": "bob2"},
        )
        assert resp.status_code == 409

    def test_should_return_token_when_credentials_are_valid(self, client):
        client.post(
            "/auth/register",
            json={
                "username": "alice",
                "display_name": "Alice",
                "email": "alice@example.com",
                "password": "s3cr3t",
            },
        )
        resp = client.post("/auth/login", json={"email": "alice@example.com", "password": "s3cr3t"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert resp.json()["token_type"] == "bearer"

    def test_should_return_401_when_password_is_wrong(self, client):
        client.post(
            "/auth/register",
            json={
                "username": "alice",
                "display_name": "Alice",
                "email": "alice@example.com",
                "password": "s3cr3t",
            },
        )
        resp = client.post("/auth/login", json={"email": "alice@example.com", "password": "wrong"})
        assert resp.status_code == 401

    def test_should_return_current_user_when_token_is_valid(self, client):
        token = _register_and_login(client)
        resp = client.get("/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@example.com"

    def test_should_return_401_when_token_is_missing(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_should_return_429_after_too_many_login_attempts(self, client):
        client.post(
            "/auth/register",
            json={
                "username": "victim",
                "display_name": "Victim",
                "email": "victim@example.com",
                "password": "s3cr3t",
            },
        )
        for _ in range(5):
            client.post(
                "/auth/login",
                json={"email": "victim@example.com", "password": "s3cr3t"},
            )
        resp = client.post(
            "/auth/login", json={"email": "victim@example.com", "password": "s3cr3t"}
        )
        assert resp.status_code == 429


# ─── Trips ────────────────────────────────────────────────────────────────────


class TestTrips:
    def test_should_return_201_when_trip_is_created(self, client):
        token = _register_and_login(client)
        resp = client.post(
            "/trips",
            json={"name": "Tokyo 2025", "base_currency": "EUR"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Tokyo 2025"
        assert data["base_currency"] == "EUR"
        assert "id" in data

    def test_should_return_trip_when_it_exists(self, client):
        token = _register_and_login(client)
        trip_id = client.post(
            "/trips",
            json={"name": "Paris", "base_currency": "EUR"},
            headers=_auth(token),
        ).json()["id"]

        resp = client.get(f"/trips/{trip_id}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Paris"

    def test_should_return_404_when_trip_does_not_exist(self, client):
        token = _register_and_login(client)
        resp = client.get("/trips/9999", headers=_auth(token))
        assert resp.status_code == 404

    def test_should_return_401_when_creating_trip_without_token(self, client):
        resp = client.post("/trips", json={"name": "Tokyo", "base_currency": "EUR"})
        assert resp.status_code == 401

    def test_should_return_403_when_user_is_not_a_member(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")

        trip_id = client.post(
            "/trips",
            json={"name": "Alice Trip", "base_currency": "EUR"},
            headers=_auth(token_alice),
        ).json()["id"]

        resp = client.get(f"/trips/{trip_id}", headers=_auth(token_bob))
        assert resp.status_code == 403


# ─── My Trips ─────────────────────────────────────────────────────────────────


class TestMyTrips:
    def test_should_return_empty_list_when_user_has_no_trips(self, client):
        token = _register_and_login(client)
        resp = client.get("/trips", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_should_return_only_my_trips(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")

        client.post(
            "/trips",
            json={"name": "Paris", "base_currency": "EUR"},
            headers=_auth(token_alice),
        )
        client.post(
            "/trips",
            json={"name": "Tokyo", "base_currency": "JPY"},
            headers=_auth(token_alice),
        )
        client.post(
            "/trips",
            json={"name": "NYC", "base_currency": "USD"},
            headers=_auth(token_bob),
        )

        resp = client.get("/trips", headers=_auth(token_alice))
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()}
        assert names == {"Paris", "Tokyo"}

    def test_should_include_trip_when_added_as_member(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")
        bob_id = client.get("/auth/me", headers=_auth(token_bob)).json()["id"]

        trip = client.post(
            "/trips",
            json={"name": "Paris", "base_currency": "EUR"},
            headers=_auth(token_alice),
        ).json()
        client.post(
            f"/trips/{trip['id']}/members",
            json={"user_id": bob_id},
            headers=_auth(token_alice),
        )

        resp = client.get("/trips", headers=_auth(token_bob))
        assert resp.status_code == 200
        assert any(t["name"] == "Paris" for t in resp.json())

    def test_should_return_401_when_not_authenticated(self, client):
        resp = client.get("/trips")
        assert resp.status_code == 401


# ─── Members ──────────────────────────────────────────────────────────────────


class TestMembers:
    @pytest.fixture()
    def setup(self, client):
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")
        trip = client.post(
            "/trips",
            json={"name": "Tokyo", "base_currency": "EUR"},
            headers=_auth(token_alice),
        ).json()
        alice_id = client.get("/auth/me", headers=_auth(token_alice)).json()["id"]
        bob_id = client.get("/auth/me", headers=_auth(token_bob)).json()["id"]
        return {
            "trip": trip,
            "token_alice": token_alice,
            "token_bob": token_bob,
            "alice_id": alice_id,
            "bob_id": bob_id,
        }

    def test_should_list_creator_as_member(self, client, setup):
        resp = client.get(
            f"/trips/{setup['trip']['id']}/members", headers=_auth(setup["token_alice"])
        )
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) == 1
        assert members[0]["user_id"] == setup["alice_id"]
        assert members[0]["display_name"] == "Alice"
        assert "role" in members[0]

    def test_should_list_all_members_after_adding(self, client, setup):
        client.post(
            f"/trips/{setup['trip']['id']}/members",
            json={"user_id": setup["bob_id"]},
            headers=_auth(setup["token_alice"]),
        )
        resp = client.get(
            f"/trips/{setup['trip']['id']}/members", headers=_auth(setup["token_alice"])
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        user_ids = {m["user_id"] for m in resp.json()}
        assert user_ids == {setup["alice_id"], setup["bob_id"]}

    def test_should_return_404_when_adding_unknown_user(self, client, setup):
        resp = client.post(
            f"/trips/{setup['trip']['id']}/members",
            json={"user_id": 9999},
            headers=_auth(setup["token_alice"]),
        )
        assert resp.status_code == 404

    def test_should_return_409_when_user_already_member(self, client, setup):
        resp = client.post(
            f"/trips/{setup['trip']['id']}/members",
            json={"user_id": setup["alice_id"]},
            headers=_auth(setup["token_alice"]),
        )
        assert resp.status_code == 409

    def test_should_return_403_when_non_member_lists_members(self, client, setup):
        resp = client.get(
            f"/trips/{setup['trip']['id']}/members", headers=_auth(setup["token_bob"])
        )
        assert resp.status_code == 403

    def test_should_allow_any_member_to_add_another(self, client, setup):
        """Bob (once a member) can add a third user."""
        token_charlie = _register_and_login(client, "charlie@example.com")
        charlie_id = client.get("/auth/me", headers=_auth(token_charlie)).json()["id"]

        client.post(
            f"/trips/{setup['trip']['id']}/members",
            json={"user_id": setup["bob_id"]},
            headers=_auth(setup["token_alice"]),
        )
        resp = client.post(
            f"/trips/{setup['trip']['id']}/members",
            json={"user_id": charlie_id},
            headers=_auth(setup["token_bob"]),
        )
        assert resp.status_code == 204


# ─── Expenses ─────────────────────────────────────────────────────────────────


class TestExpenses:
    @pytest.fixture()
    def setup(self, client):
        """Register two users, create a trip with both as members, return context."""
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")

        # Alice creates trip (she becomes member automatically)
        trip = client.post(
            "/trips",
            json={"name": "Tokyo", "base_currency": "EUR"},
            headers=_auth(token_alice),
        ).json()

        # Add Bob as member — need Bob's user id
        bob_id = client.get("/auth/me", headers=_auth(token_bob)).json()["id"]
        client.post(
            f"/trips/{trip['id']}/members",
            json={"user_id": bob_id},
            headers=_auth(token_alice),
        )

        return {"trip": trip, "token_alice": token_alice, "token_bob": token_bob}

    def test_should_return_201_when_expense_is_added(self, client, setup):
        resp = client.post(
            f"/trips/{setup['trip']['id']}/expenses",
            json={
                "title": "Sushi dinner",
                "amount": 120.0,
                "currency": "EUR",
                "split_type": "equal",
            },
            headers=_auth(setup["token_alice"]),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Sushi dinner"
        assert data["amount_pivot"] == 120.0
        assert data["split_type"] == "equal"
        assert len(data["splits"]) == 2  # Alice + Bob split equally

    def test_should_return_correct_split_amounts_for_equal_split(self, client, setup):
        client.post(
            f"/trips/{setup['trip']['id']}/expenses",
            json={
                "title": "Hotel",
                "amount": 200.0,
                "currency": "EUR",
                "split_type": "equal",
            },
            headers=_auth(setup["token_alice"]),
        )
        resp = client.get(
            f"/trips/{setup['trip']['id']}/expenses",
            headers=_auth(setup["token_alice"]),
        )
        assert resp.status_code == 200
        splits = resp.json()[0]["splits"]
        amounts = sorted(s["amount_owed"] for s in splits)
        assert all(abs(a - 100.0) < 0.01 for a in amounts)

    def test_should_list_all_expenses_for_trip(self, client, setup):
        trip_id = setup["trip"]["id"]
        for title in ["Lunch", "Museum", "Transport"]:
            client.post(
                f"/trips/{trip_id}/expenses",
                json={
                    "title": title,
                    "amount": 30.0,
                    "currency": "EUR",
                    "split_type": "equal",
                },
                headers=_auth(setup["token_alice"]),
            )

        resp = client.get(f"/trips/{trip_id}/expenses", headers=_auth(setup["token_alice"]))
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_should_return_404_when_adding_expense_to_unknown_trip(self, client):
        token = _register_and_login(client)
        resp = client.post(
            "/trips/9999/expenses",
            json={
                "title": "X",
                "amount": 10.0,
                "currency": "EUR",
                "split_type": "equal",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_should_apply_exchange_rate_when_currency_differs_from_base(self, client):
        """StubCurrencyPort returns 1.0, so amount_pivot == amount regardless of currency."""
        token = _register_and_login(client)
        trip_id = client.post(
            "/trips",
            json={"name": "Japan", "base_currency": "EUR"},
            headers=_auth(token),
        ).json()["id"]

        resp = client.post(
            f"/trips/{trip_id}/expenses",
            json={
                "title": "Ramen",
                "amount": 1500.0,
                "currency": "JPY",
                "split_type": "equal",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_currency"] == "JPY"
        assert data["exchange_rate"] == 1.0
        assert data["amount_pivot"] == 1500.0


# ─── Settlements ──────────────────────────────────────────────────────────────


class TestSettlements:
    @pytest.fixture()
    def setup(self, client):
        """Two users, one trip, Alice pays for both."""
        token_alice = _register_and_login(client, "alice@example.com")
        token_bob = _register_and_login(client, "bob@example.com")

        trip = client.post(
            "/trips",
            json={"name": "Tokyo", "base_currency": "EUR"},
            headers=_auth(token_alice),
        ).json()

        bob_id = client.get("/auth/me", headers=_auth(token_bob)).json()["id"]
        client.post(
            f"/trips/{trip['id']}/members",
            json={"user_id": bob_id},
            headers=_auth(token_alice),
        )

        alice_id = client.get("/auth/me", headers=_auth(token_alice)).json()["id"]

        return {
            "trip": trip,
            "token_alice": token_alice,
            "token_bob": token_bob,
            "alice_id": alice_id,
            "bob_id": bob_id,
        }

    def test_should_return_empty_list_when_no_expenses(self, client, setup):
        resp = client.get(
            f"/trips/{setup['trip']['id']}/settlements",
            headers=_auth(setup["token_alice"]),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_should_return_transfer_when_alice_paid_for_both(self, client, setup):
        """Alice pays 100 split equally → Bob owes Alice 50."""
        client.post(
            f"/trips/{setup['trip']['id']}/expenses",
            json={
                "title": "Dinner",
                "amount": 100.0,
                "currency": "EUR",
                "split_type": "equal",
            },
            headers=_auth(setup["token_alice"]),
        )

        resp = client.get(
            f"/trips/{setup['trip']['id']}/settlements",
            headers=_auth(setup["token_alice"]),
        )
        assert resp.status_code == 200
        transfers = resp.json()
        assert len(transfers) == 1
        assert transfers[0]["from_user_id"] == setup["bob_id"]
        assert transfers[0]["to_user_id"] == setup["alice_id"]
        assert abs(transfers[0]["amount"] - 50.0) < 0.01

    def test_should_return_no_transfers_when_expenses_are_balanced(self, client, setup):
        """Alice pays 60, Bob pays 60, equal split → zero net."""
        client.post(
            f"/trips/{setup['trip']['id']}/expenses",
            json={
                "title": "Lunch",
                "amount": 60.0,
                "currency": "EUR",
                "split_type": "equal",
            },
            headers=_auth(setup["token_alice"]),
        )
        client.post(
            f"/trips/{setup['trip']['id']}/expenses",
            json={
                "title": "Dinner",
                "amount": 60.0,
                "currency": "EUR",
                "split_type": "equal",
            },
            headers=_auth(setup["token_bob"]),
        )

        resp = client.get(
            f"/trips/{setup['trip']['id']}/settlements",
            headers=_auth(setup["token_alice"]),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_should_accumulate_across_multiple_expenses(self, client, setup):
        """Alice pays 60 + 40 = 100 total → Bob owes 50."""
        for amount in [60.0, 40.0]:
            client.post(
                f"/trips/{setup['trip']['id']}/expenses",
                json={
                    "title": "Expense",
                    "amount": amount,
                    "currency": "EUR",
                    "split_type": "equal",
                },
                headers=_auth(setup["token_alice"]),
            )

        resp = client.get(
            f"/trips/{setup['trip']['id']}/settlements",
            headers=_auth(setup["token_alice"]),
        )
        transfers = resp.json()
        assert len(transfers) == 1
        assert abs(transfers[0]["amount"] - 50.0) < 0.01

    def test_should_return_404_when_trip_does_not_exist(self, client):
        token = _register_and_login(client)
        resp = client.get("/trips/9999/settlements", headers=_auth(token))
        assert resp.status_code == 404

    def test_should_return_401_when_token_is_missing(self, client):
        resp = client.get("/trips/1/settlements")
        assert resp.status_code == 401

    def test_should_return_pdf_with_expenses(self, client, setup):
        client.post(
            f"/trips/{setup['trip']['id']}/expenses",
            json={
                "title": "Dinner",
                "amount": 100.0,
                "currency": "EUR",
                "split_type": "equal",
            },
            headers=_auth(setup["token_alice"]),
        )
        resp = client.get(
            f"/trips/{setup['trip']['id']}/settlements/pdf",
            headers=_auth(setup["token_alice"]),
        )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
        assert resp.content[:4] == b"%PDF"

    def test_should_return_pdf_when_no_expenses(self, client, setup):
        resp = client.get(
            f"/trips/{setup['trip']['id']}/settlements/pdf",
            headers=_auth(setup["token_alice"]),
        )
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"

    def test_should_return_403_on_pdf_when_not_member(self, client, setup):
        token_stranger = _register_and_login(client, "stranger@example.com")
        resp = client.get(
            f"/trips/{setup['trip']['id']}/settlements/pdf",
            headers=_auth(token_stranger),
        )
        assert resp.status_code == 403
