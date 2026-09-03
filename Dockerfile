FROM python:3.11-slim

WORKDIR /app

# Only the files needed to install the package -- no .env, no test fixtures,
# no research scripts end up in the image (see .dockerignore).
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 1000 appuser
USER appuser

ENV MCP_TRANSPORT=streamable-http
EXPOSE 8081

CMD ["plato-mcp"]
