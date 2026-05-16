FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY devices.toml ./
COPY electric_eye ./electric_eye
RUN uv sync

EXPOSE 8000

CMD ["uv", "run", "ee", "web", "--host", "0.0.0.0", "--port", "8000"]
