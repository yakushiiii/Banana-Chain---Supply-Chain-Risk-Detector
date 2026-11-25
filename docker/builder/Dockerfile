FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake pkg-config && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home builder
USER builder
WORKDIR /src