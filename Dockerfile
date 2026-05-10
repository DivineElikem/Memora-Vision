# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set the working directory
WORKDIR /app

# Install system dependencies for OpenCV and other libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/

# Copy the dependency files
COPY backend/pyproject.toml .
# If you have a lockfile, copy it too:
# COPY backend/uv.lock .

# Install dependencies using uv
# --system installs into the system python environment instead of a venv
RUN /uv/bin/uv pip install --system .

# Copy the rest of the application
COPY backend/ .

# Create data directory for SQLite and uploads
RUN mkdir -p data/uploads data/keyframes

# Expose the port the app runs on
EXPOSE $PORT

# Command to run the application
# Use the PORT environment variable provided by Render
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
