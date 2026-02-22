FROM python:3.14-slim

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY packages/src/ packages/src/

# Install the application (no cache to keep image small)
RUN uv pip install --system --no-cache .

# Run as non-root
RUN useradd --create-home appuser
USER appuser

# Entry point — reads config from environment / .env
CMD ["gas2mqtt"]
