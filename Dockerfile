FROM python:3.14-alpine3.24 AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --all-extras --no-install-project --no-dev --no-editable

COPY pyproject.toml uv.lock LICENSE README.md ./
COPY src/ ./src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --all-extras --no-dev --no-editable


FROM python:3.14-alpine3.24
LABEL org.opencontainers.image.title="Ghostfolio MCP Server" \
      org.opencontainers.image.description="MCP server for Ghostfolio management" \
      org.opencontainers.image.url="https://github.com/mhajder/ghostfolio-mcp" \
      org.opencontainers.image.source="https://github.com/mhajder/ghostfolio-mcp" \
      org.opencontainers.image.vendor="Mateusz Hajder" \
      org.opencontainers.image.licenses="AGPL-3.0" \
      io.modelcontextprotocol.server.name="io.github.mhajder/ghostfolio-mcp"
ENV PYTHONUNBUFFERED=1

RUN addgroup -g 10001 appuser \
    && adduser -D -u 10001 -G appuser appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

COPY --from=builder /app/.venv /app/.venv

WORKDIR /app

USER 10001:10001

ENV PATH="/app/.venv/bin:$PATH"

# OAuth state for OIDC; mount a volume on /data to persist it
ENV FASTMCP_HOME=/data

HEALTHCHECK \
  --interval=15s \
  --timeout=10s \
  --start-period=5s \
  --retries=3 \
  CMD ["python", "-m", "ghostfolio_mcp.healthcheck"]

ENV MCP_TRANSPORT=http
ENV MCP_HTTP_HOST=0.0.0.0
ENV MCP_HTTP_PORT=8000

EXPOSE 8000

ENTRYPOINT ["ghostfolio-mcp"]
