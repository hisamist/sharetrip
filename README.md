# ShareTrip

![CI/CD Pipeline](https://github.com/hisamist/sharetrip/actions/workflows/ci.yaml/badge.svg)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=hisamist_sharetrip&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=hisamist_sharetrip)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=hisamist_sharetrip&metric=coverage)](https://sonarcloud.io/summary/new_code?id=hisamist_sharetrip)
![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Alpine%20190MB-blue?logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

**ShareTrip** est une API REST de gestion de dépenses partagées pour groupes de voyage.

Pendant un voyage en groupe, chaque membre peut enregistrer ses dépenses dans **n'importe quelle devise** (EUR, JPY, USD...). ShareTrip convertit automatiquement les montants dans la devise de base du voyage grâce à l'API Frankfurter. Toutes les dépenses sont stockées et à la fin du voyage, l'algorithme calcule **qui doit rembourser qui et combien**, selon la méthode de répartition choisie :

- **Égale** — chaque membre paye la même part
- **Pourcentage** — répartition selon le poids de chaque membre
- **Hybride** — répartition personnalisée par dépense

Le résultat est affiché via l'API ou exporté en **PDF téléchargeable**, minimisant le nombre de virements nécessaires entre membres.

Construit avec **FastAPI**, **PostgreSQL**, **Redis** — architecture **Clean Architecture**.

---

## Table des matières

- [Lancer le projet](#lancer-le-projet)
- [Architecture](#architecture)
- [Design Patterns](#design-patterns)
- [API](#api)
- [Tests](#tests)
- [Qualité de code](#qualité-de-code)
- [Docker](#docker)
- [CI/CD Pipeline](#cicd-pipeline)
- [Choix justifiés](#choix-justifiés)

---

## Lancer le projet

```bash
# 1. Cloner et configurer
git clone https://github.com/hisamist/sharetrip.git
cd sharetrip
cp .env.example .env   # Remplir les valeurs

# 2. Lancer (dev)
docker compose up

# 3. Accéder à l'API
open http://localhost:8000/docs
```

**Prérequis :** Docker + Docker Compose

---

## Architecture

ShareTrip suit la **Clean Architecture** — le domaine métier ne dépend d'aucun framework.

```
src/sharetrip/
├── domain/               ← Entités & règles métier (zéro dépendance externe)
│   ├── entities/         ← Trip, Expense, User, Membership
│   ├── interfaces/       ← Ports abstraits (TripRepository, CurrencyPort)
│   └── services/         ← Split strategies, logique de calcul
├── use_cases/            ← Cas d'utilisation (AddExpense, ComputeSettlements...)
├── infrastructure/       ← Adapters concrets (SQL, Redis, JWT, PDF)
│   ├── db/               ← SQLAlchemy ORM
│   ├── cache/            ← Redis decorator
│   ├── auth/             ← JWT + bcrypt
│   └── notifications/    ← Observer pattern
└── api/                  ← FastAPI routers, schemas, dépendances
```

**Flux d'une requête :**
```
HTTP Request → FastAPI Router → Use Case → Domain → Repository → PostgreSQL
                                                   ↓
                                              Redis Cache
```

---

## Design Patterns

### 1. Repository Pattern
**Pourquoi :** Découpler la logique métier de la base de données. Les use cases dépendent d'une interface abstraite `TripRepository`, pas de SQLAlchemy.  
**Bénéfice :** Les tests utilisent SQLite in-memory sans changer une ligne de code métier.

```python
class TripRepository(ABC):
    @abstractmethod
    def get_trip(self, trip_id: int) -> Trip | None: ...
    @abstractmethod
    def add_member(self, membership: Membership) -> Membership: ...
```

### 2. Strategy Pattern
**Pourquoi :** Le calcul de répartition des dépenses varie selon le type (égal, pourcentage, hybride). Chaque stratégie est interchangeable sans modifier le code client.

```python
class EqualSplitter(SplitStrategy): ...
class PercentageSplitter(SplitStrategy): ...
class HybridSplitter(SplitStrategy): ...
# SplitFactory choisit la stratégie selon split_type
```

### 3. Decorator Pattern (Cache)
**Pourquoi :** Ajouter du cache Redis sur le repository sans modifier `SQLTripRepository`. `CachedTripRepository` wrappe l'implémentation SQL et intercepte les lectures.

```python
CachedTripRepository(inner=SQLTripRepository(session), redis=redis)
# Stratégie cache-aside : READ depuis Redis, WRITE invalide le cache
```

### 4. Observer Pattern
**Pourquoi :** Notifier des systèmes tiers lors de la création d'une dépense (logs, alertes budget) sans coupler le use case aux notifieurs.

```python
AddExpenseUseCase(observers=[LogNotificationObserver()])
# Extensible : ajouter un EmailObserver sans toucher au use case
```

### 5. Adapter Pattern (Port & Adapter)
**Pourquoi :** Isoler l'API de taux de change externe (Frankfurter). `CurrencyPort` est l'interface — l'adapter peut être swappé (mock en tests, autre fournisseur en prod).

---

## API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/auth/register` | Créer un compte |
| `POST` | `/auth/login` | Connexion → JWT (rate limit 5/min) |
| `GET` | `/trips` | Mes voyages |
| `POST` | `/trips` | Créer un voyage |
| `GET` | `/trips/{id}/members` | Membres du groupe |
| `POST` | `/trips/{id}/members` | Ajouter un membre |
| `POST` | `/trips/{id}/expenses` | Enregistrer une dépense |
| `GET` | `/trips/{id}/expenses` | Liste des dépenses |
| `GET` | `/trips/{id}/settlements` | Calcul des remboursements |
| `GET` | `/trips/{id}/settlements/pdf` | Export PDF |

Documentation interactive : `http://localhost:8000/docs`

---

## Tests

**158 tests** — structure AAA systématique, nommage `should [résultat] when [condition]`

```bash
# Lancer tous les tests
python -m pytest

# Avec couverture
python -m pytest --cov=src --cov-report=html
```

| Type | Fichiers | Description |
|------|----------|-------------|
| Unitaires | `tests/unit/` | Logique métier isolée, stubs pour dépendances |
| Intégration | `tests/integration/` | Routes HTTP + SQLite in-memory + FakeRedis |

**Couverture :** > 80% — seuil CI : ≥ 70%

**Pourquoi SQLite en tests ?**  
Isolation, rapidité, zéro infrastructure. Les tests d'intégration testent la vraie chaîne HTTP→UseCase→Repository. SQLite est suffisant car `SQLTripRepository` abstrait le dialecte SQL.

---

## Qualité de code

```bash
# Linter + formatter
task lint          # ruff check
task format        # ruff format

# Pre-commit (automatique avant chaque commit)
pre-commit install
```

**Ruff — règles activées et justifiées :**

| Règle | Justification |
|-------|--------------|
| `E/W` | PEP 8 — standard Python |
| `F` | Pyflakes — imports inutilisés, noms indéfinis |
| `I` | isort — ordre des imports cohérent |
| `B` | Bugbear — bugs courants et mauvaises pratiques |
| `UP` | Pyupgrade — syntaxe Python moderne (`X \| Y` vs `Union`) |
| `C90` | McCabe — complexité cyclomatique max 10 |
| `B008` | Ignoré — pattern `Depends()` de FastAPI intentionnel |

**SonarCloud :** Quality Gate configurée (0 bugs, 0 vulnérabilités, duplication < 3%, coverage ≥ 70%)

---

## Docker

```bash
# Développement (hot-reload)
docker compose up

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Image finale : 190MB** (cible < 200MB) ✅

| Critère sécurité | Implémentation |
|-----------------|----------------|
| Non-root | `USER appuser` (appgroup/appuser) |
| Multi-stage | builder (uv + Alpine) → production (Alpine slim) |
| Pas de secrets | `.env` exclu du build, variables au runtime |
| HEALTHCHECK | `wget /health` toutes les 30s |
| Filesystem read-only | `read_only: true` + `tmpfs: /tmp` en prod |
| Pinning versions | Tags exacts (pas `:latest`) |
| Scan vulnérabilités | Trivy intégré dans CI (CRITICAL/HIGH → fail) |

---

## CI/CD Pipeline

### Pipeline CI (`.github/workflows/ci.yaml`)

Jobs **parallèles** :
```
lint ──────────────────────┐
unit-tests + coverage ─────┤→ build → docker-build → scan image
integration-tests ─────────┘
security-deps (Trivy fs) ──────────────────────────────────────
sonarcloud ← needs: unit-tests
```

| Job | Description |
|-----|-------------|
| `lint` | ruff format + ruff check |
| `unit-tests` | 158 tests, coverage ≥ 70%, artifact XML |
| `integration-tests` | Routes HTTP, SQLite in-memory |
| `security-deps` | Trivy scan filesystem |
| `sonarcloud` | Quality Gate bloquante |
| `build` | Vérification imports Python |
| `docker-build` | Build + push GHCR avec tag SHA |
| `security-image` | Trivy scan image Docker depuis GHCR |

**Cache :** `pip` via `actions/setup-python` + layers Docker via `type=gha`

**Image Docker :** pushée sur `ghcr.io/hisamist/sharetrip:latest` et `ghcr.io/hisamist/sharetrip:{sha}` à chaque merge sur `main`.

### Pipeline CD (`.github/workflows/cd.yaml`)

| Environnement | Déclencheur | Approbation |
|--------------|-------------|-------------|
| **Staging** | Auto sur merge `main` | Aucune |
| **Production** | `workflow_dispatch` ou tag release | Manuelle requise |

---

## Choix justifiés

**Pourquoi Clean Architecture ?**  
Le domaine métier (calcul de répartition, gestion des membres) ne doit pas dépendre de FastAPI ou SQLAlchemy. Si on change d'ORM ou de framework, seule la couche infrastructure change.

**Pourquoi l'algorithme minimize-transfers pour les settlements ?**  
Avec N membres, une approche naïve génère O(N²) transferts. L'algorithme greedy sur créditeurs/débiteurs minimise le nombre de virements, réduisant la friction pour les utilisateurs.

**Pourquoi Redis pour le cache ?**  
Les taux de change (TTL 24h) et les membres d'un trip (TTL 5min) sont lus fréquemment et changent rarement. Le cache évite des appels DB et API répétés sans impacter la cohérence.

**Pourquoi 70% comme seuil de couverture ?**  
La couverture 100% est coûteuse et souvent inutile (getters, constructeurs). 70% couvre la logique métier critique (strategies, use cases) tout en restant atteignable. Notre couverture réelle est > 80%.

**Pourquoi uv dans le Dockerfile ?**  
`uv` est 10-100x plus rapide que `pip` pour la résolution et l'installation des dépendances. Le `uv.lock` garantit des builds reproductibles.

**IaC — non implémenté**  
Terraform/Ansible nécessitent un provider cloud configuré (AWS, GCP...). Sans environnement cloud disponible pour ce projet, l'IaC n'a pas été implémentée. Les fichiers Docker Compose `docker-compose.prod.yml` remplissent le rôle d'infrastructure déclarative pour le déploiement local/VM.

**Monitoring — partiellement implémenté**  
- Health check endpoint : `GET /health` ✅  
- HEALTHCHECK Docker : `wget /health` toutes les 30s ✅  
- Logs structurés JSON : non implémentés (amélioration future)  
- Dashboard Grafana/Prometheus : non implémentés

---

## Structure du repo

```
sharetrip/
├── src/sharetrip/          # Code source
├── tests/                  # 158 tests (unit + integration)
├── .github/workflows/      # CI + CD pipelines
├── Dockerfile              # Multi-stage Alpine build
├── docker-compose.yml      # Base (dev + prod)
├── docker-compose.override.yml  # Dev (hot-reload)
├── docker-compose.prod.yml # Production (resource limits)
├── sonar-project.properties
├── pyproject.toml          # Deps + ruff config
└── .env.example            # Template de configuration
```
