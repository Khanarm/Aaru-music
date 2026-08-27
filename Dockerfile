# Railway-ready Docker image for AnonXMusic
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/app/.venv/bin:${PATH}"

# Install runtime libraries required by FFmpeg / native Python packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /uvx /bin/

WORKDIR /app

# Copy dependency metadata first so Railway/Docker can cache dependency layers.
COPY pyproject.toml uv.lock ./

# Install locked dependencies into /app/.venv.
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source.
COPY . .

# Do not run setup/interactive installer in Railway.
RUN chmod +x start

# This is a long-running worker; no HTTP port is required.
CMD ["./start"]
