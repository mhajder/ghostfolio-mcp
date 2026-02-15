FROM python:3.13-alpine3.23 AS builder

RUN pip install --root-user-action=ignore --no-cache-dir --upgrade pip \
    && pip install --root-user-action=ignore --no-cache-dir uv

ENV UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --all-extras --no-install-project --no-dev

COPY pyproject.toml uv.lock LICENSE README.md run_server.py ./
COPY src/ ./src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --all-extras --no-dev


FROM python:3.13-alpine3.23
LABEL org.opencontainers.image.title="Ghostfolio MCP Server" \
      org.opencontainers.image.description="MCP server for Ghostfolio management" \
      org.opencontainers.image.url="https://github.com/mhajder/ghostfolio-mcp" \
      org.opencontainers.image.source="https://github.com/mhajder/ghostfolio-mcp" \
      org.opencontainers.image.vendor="Mateusz Hajder" \
      org.opencontainers.image.licenses="AGPL-3.0"
ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache ca-certificates \
    && addgroup -g 1000 appuser \
    && adduser -D -u 1000 -G appuser appuser

COPY --from=builder --chown=appuser:appuser /app /app

WORKDIR /app

USER appuser

ENV PATH="/app/.venv/bin:$PATH"

HEALTHCHECK \
  --interval=15s \
  --timeout=5s \
  --start-period=5s \
  --retries=3 \
  CMD nc -z 127.0.0.1 8000 || exit 1

ENV MCP_TRANSPORT=http
ENV MCP_HTTP_HOST=0.0.0.0
ENV MCP_HTTP_PORT=8000

EXPOSE 8000

ENTRYPOINT ["ghostfolio-mcp"]
