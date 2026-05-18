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
- [IaC — Infrastructure as Code](#iac--infrastructure-as-code)
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
| Intégration HTTP | `tests/integration/test_api.py` | Routes HTTP + SQLite in-memory + FakeRedis |
| Intégration Repository | `tests/integration/test_sql_trip_repository.py` | CRUD SQLite in-memory |
| Migrations PostgreSQL | `tests/integration/test_real_db.py` | Smoke test Alembic sur vrai PostgreSQL |

**Couverture :** > 80% — seuil CI : ≥ 70%

### Justification : Pourquoi utiliser à la fois SQLite et PostgreSQL en CI ?

Le pipeline utilise une stratégie de test à double niveau (SQLite et PostgreSQL) exécutée en parallèle pour optimiser les ressources et le temps de retour (feedback loop) :

1. **Job `unit-tests` (SQLite in-memory) — Objectif : Vitesse.**
   Ce job s'exécute instantanément (sans latence d'infrastructure). Il sert de premier filtre "Fail-Fast" pour détecter immédiatement les régressions purement logicielles et algorithmiques (ex : calcul des répartitions de dépenses, logique d'authentification).

2. **Job `integration-tests-db` (PostgreSQL Service) — Objectif : Fidélité Production.**
   Ce job attend l'initialisation d'un vrai conteneur PostgreSQL. Il sert à valider ce que SQLite ne peut pas voir : la validité des scripts de migration Alembic (`upgrade head` / `downgrade base`), la stricte conformité des types SQL (contraintes, clés étrangères) et l'intégrité opérationnelle de la chaîne globale avant l'envoi de l'image Docker sur GHCR.

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
| `unit-tests` | Tests unitaires + intégration HTTP (SQLite), coverage ≥ 70%, artifact XML |
| `integration-tests-db` | Smoke test migrations Alembic sur PostgreSQL 16 éphémère |
| `security-deps` | Trivy scan filesystem (CRITICAL/HIGH → fail) |
| `sonarcloud` | Quality Gate bloquante (needs: unit-tests) |
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

## IaC — Infrastructure as Code

### Terraform — Provisionnement (Docker provider)

**Prérequis :** Terraform ≥ 1.6 + Docker Desktop

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Remplir postgres_password et jwt_secret_key dans terraform.tfvars

terraform init
terraform plan -var-file=terraform.tfvars   # Preview
terraform apply -var-file=terraform.tfvars  # Créer l'infra
terraform destroy -var-file=terraform.tfvars # Supprimer
```

| Ressource | Description |
|-----------|-------------|
| `docker_network` | Réseau isolé `sharetrip_production` |
| `docker_volume` × 2 | Persistance PostgreSQL + Redis |
| `docker_container` postgres | PostgreSQL 16 avec healthcheck `pg_isready` |
| `docker_container` redis | Redis 7 avec AOF persistence |
| `docker_container` app | API ShareTrip avec toutes les env vars câblées |

**Structure :**
```
terraform/
├── providers.tf          # kreuzwerker/docker ~> 3.0, backend local
├── variables.tf          # Variables (secrets sans default → enforced)
├── main.tf               # Appel du module
├── outputs.tf            # app_url, api_docs_url, noms des conteneurs
├── terraform.tfvars.example
└── modules/sharetrip-stack/
    ├── main.tf           # Toutes les ressources Docker
    ├── variables.tf
    └── outputs.tf
```

**State :** local (`terraform.tfstate`) — pour un déploiement réel, migrer vers un backend remote :
```hcl
backend "s3" { bucket = "..." key = "sharetrip/terraform.tfstate" }
```

**CI :** `terraform plan` s'exécute automatiquement sur chaque PR pour prévisualiser les changements avant merge.

---

### Ansible — Configuration & Déploiement

**Prérequis :** `pip install ansible` (Linux/Mac/WSL)

```bash
cd ansible

# Déploiement complet (idempotent)
ansible-playbook playbooks/deploy.yml

# Dry-run — aucune modification appliquée
ansible-playbook playbooks/deploy.yml --check
```

| Rôle | Responsabilité |
|------|----------------|
| `common` | Installe Docker et ses dépendances sur le serveur cible |
| `sharetrip` | Crée `/opt/sharetrip`, template `.env` (Jinja2), démarre les conteneurs, exécute `alembic upgrade head` |
| `nginx` | Configure le reverse proxy (port 80 → 8000) avec suppression des logs `/health` |

**Inventaire :** `localhost` (connection: local) pour les tests — changer `ansible_host` pour un serveur distant.

**Idempotence :** relancer le playbook ne casse rien — les tâches utilisent `state: started/present` et les handlers ne se déclenchent que si `.env` a changé.

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


## Pipeline CI/CD (GitHub Actions)

Le pipeline `.github/workflows/ci.yaml` a été conçu selon une approche de validation progressive (Fail-Fast) et sécurisée, structurée en jobs parallèles puis séquentiels.

* **Stratégie de parallélisation (Lint, Tests, Sécurité) :**
  Les étapes de Lint (`ruff`), de tests unitaires, de tests d'intégration (SQLite et PostgreSQL) et de scan de vulnérabilités du système de fichiers (`Trivy fs`) s'exécutent en parallèle. *Justification :* Cela permet de minimiser le temps de retour (feedback loop) pour le développeur. Si le code est mal formaté ou contient une faille, le pipeline échoue immédiatement sans attendre la fin des tests de base de données.

* **Double niveau de tests d'intégration (SQLite et PostgreSQL) :**
  Le pipeline sépare les tests d'intégration rapides via SQLite in-memory, et les tests de production via un conteneur de service PostgreSQL (`postgres:16-alpine`) éphémère. *Justification :* Les tests SQLite valident instantanément la logique globale des cas d'utilisation, tandis que le job `integration-tests-db` garantit la stricte compatibilité des requêtes SQL et du comportement des transactions avec le vrai moteur de base de données de production.

* **Optimisation agressive du Cache (Pip et Docker Layers) :**
  - **Python (`cache: pip`) :** Utilisation de l'intégration native de `actions/setup-python@v5` pour mettre en cache le répertoire de téléchargement de `pip`.
  - **Docker (`cache-from/to: type=gha`) :** Le job `docker-build` utilise le cache natif de GitHub Actions pour conserver les couches (layers) inchangées du Dockerfile.
  *Justification :* Cela évite de télécharger à nouveau les paquets Python et de recompiler les étapes de l'image Docker à chaque commit, réduisant la durée globale du pipeline de plus de 5 minutes à moins de 1 minute 30.

* **Sécurité en deux étapes (Scan Trivy FS vs Image) :**
  - **`security-deps` (Avant build) :** Analyse le code source et le fichier de verrouillage des dépendances.
  - **`security-image` (Après build) :** Scanne l'image Docker finale finale poussée sur GHCR (`ghcr.io`).
  *Justification :* Cette approche garantit qu'aucune vulnérabilité (`CRITICAL` ou `HIGH`) n'est introduite par nos bibliothèques Python tierces, ni par les paquets système OS (Alpine) inclus dans l'image finale. L'argument `exit-code: 1` bloque strictement le déploiement en cas de détection.

* **Qualité de code (SonarCloud Gate) :**
  Le job `sonarcloud` dépend de la réussite de `unit-tests` et récupère l'artéfact `coverage.xml`. *Justification :* Cela évite de consommer des crédits d'analyse SonarCloud si la couverture minimale requise de 70% n'est pas atteinte localement, assurant une gouvernance stricte de la qualité du code avant d'autoriser la mise en production.

**Pourquoi Terraform + Docker provider (sans cloud) ?**
Le provider `kreuzwerker/docker` permet de démontrer le workflow Terraform complet (init → plan → apply → destroy) sans nécessiter de compte cloud. L'infrastructure est déclarée en code, versionnée, et reproductible. Un `terraform plan` s'exécute automatiquement sur chaque PR pour prévisualiser les changements d'infrastructure avant merge.

**Pourquoi Ansible en complément de Terraform ?**
Terraform provisionne les ressources (conteneurs, réseau, volumes). Ansible configure le serveur cible et déploie l'application : installation de Docker, génération du `.env` via Jinja2, démarrage des conteneurs, exécution des migrations Alembic. La séparation est claire — Terraform gère le *quoi*, Ansible gère le *comment*.

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
├── tests/                  # Tests (unit + integration + migrations)
├── .github/workflows/      # CI + CD pipelines
├── terraform/              # IaC — provisionnement Docker
│   ├── modules/sharetrip-stack/
│   └── terraform.tfvars.example
├── ansible/                # IaC — configuration & déploiement
│   ├── inventory/
│   ├── playbooks/
│   └── roles/              # common, sharetrip, nginx
├── Dockerfile              # Multi-stage Alpine build
├── docker-compose.yml      # Base (dev + prod)
├── docker-compose.override.yml  # Dev (hot-reload)
├── docker-compose.prod.yml # Production (resource limits)
├── sonar-project.properties
├── pyproject.toml          # Deps + ruff config
└── .env.example            # Template de configuration
```
