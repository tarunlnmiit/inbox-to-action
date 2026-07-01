# Dockerfile for Glama MCP listing + general container use.
# Builds the inbox-to-action MCP server (stdio transport).
FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/tarunlnmiit/inbox-to-action" \
      org.opencontainers.image.description="One-pass agentic inbox triage — MCP server" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install build deps first for layer caching.
COPY pyproject.toml README.md ./
COPY inbox_to_action ./inbox_to_action

# Example config read from the working dir at runtime (real config.json is mounted).
COPY config.example.json ./

# Install the package with the MCP extra.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[mcp]"

# The MCP server exposes IO-only tools; Claude Code (the host) is the LLM, so
# no provider key is required. Gmail credentials, if used, are mounted/supplied
# at runtime. The server starts and answers introspection without any secrets.

# FastMCP serves over stdio.
CMD ["python", "-m", "inbox_to_action.mcp_server"]
