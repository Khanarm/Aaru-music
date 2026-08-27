# Railway-ready Docker image for AnonXMusic
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/app/.venv/bin:${PATH}"

# Runtime/native libraries required by FFmpeg, OpenCV and Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        git \
        gcc \
        g++ \
        make \
        libc6-dev \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /uvx /bin/

WORKDIR /app

# Dependency files first for Docker layer caching
COPY pyproject.toml uv.lock ./

# Install exactly the locked environment
RUN uv sync --frozen --no-install-project --no-dev

# Copy application
COPY . .

# Make Railway worker entrypoint executable
RUN chmod +x start

# Start the Telegram music bot
CMD ["./start"]
