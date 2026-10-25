FROM debian:bookworm-slim

RUN apt-get update  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends       bc build-essential bzip2 ca-certificates cpio file git libncurses-dev       patch perl python3 rsync sed tar unzip wget xz-utils  && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Resident-profile builds execute Buildroot as an unprivileged user.
RUN useradd --create-home --uid 1000 --shell /bin/sh vera-build
