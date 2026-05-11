FROM python:3.12-slim
# Build deps required when freesasa (SWIG-bound C extension) falls back to
# source build because no manylinux wheel matches the target arch. Using
# build-essential (gcc + g++ + make + libc6-dev) so the toolchain has both
# the compiler and the standard library headers freesasa needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Always keep basic python packaging tools fresh to avoid CVEs even in old python versions
RUN pip install --upgrade pip wheel setuptools
# Install dependencies to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy package source
COPY . /app
# Set Python path
ENV PYTHONPATH=/app
# Default command (will be overridden by entrypoint)
CMD ["bash"]
