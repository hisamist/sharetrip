# Final image size: ~190MB (target: < 200MB) — verified with `docker image ls`
# ========== STAGE 1: Builder ==========
# Use the official uv image which includes the uv binary for high-speed dependency management
FROM ghcr.io/astral-sh/uv:python3.13-alpine AS builder

# Install build-time system dependencies (e.g., for compiling database drivers)
RUN apk add --no-cache build-base postgresql-dev

WORKDIR /app

# Optimization: Copy only dependency files first to leverage Docker build cache
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment (.venv)
# --frozen: ensures uv.lock is not modified during the build
# --no-dev: excludes development dependencies like pytest or ruff
# --mount=type=cache: persists the uv cache across builds to speed up re-installation
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ========== STAGE 2: Production ==========
# Use a clean Python Alpine image for the final runtime to minimize image size
FROM python:3.13-alpine AS production

# Install runtime-only system dependencies
# libpq: required for PostgreSQL connectivity
# libgcc/libstdc++: required for compiled binaries (like Pydantic's Rust core)
RUN apk add --no-cache libpq libgcc libstdc++

# Ensure Python logs are sent straight to the terminal without buffering
ENV PYTHONUNBUFFERED=1

# Add the virtual environment created in the builder stage to the system PATH
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# SECURITY: Create a non-privileged user and group to run the application safely
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Copy only the pre-installed virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy the application source code and set ownership to the non-root user
COPY --chown=appuser:appgroup src/ ./src/

# OPTIMIZATION: Manually remove unnecessary files to further reduce image weight
RUN find /app/.venv -depth \
    \( \
        \( -type d -a \( -name __pycache__ -o -name test -o -name tests -o -name docs \) \) \
        -o \
        \( -type f -a \( -name '*.pyc' -o -name '*.pyo' -o -name '*.dist-info' \) \) \
    \) -exec rm -rf '{}' +

# Switch to the non-root user for security
USER appuser

# Document that the container listens on port 8000
EXPOSE 8000

# Liveness check: Ensure the container is actually serving requests
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

# Start the application using Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
