# Shared base for every PKG component that needs charm-crypto (both the lab
# node software and the CA -- the CA generates MA-ABE public parameters,
# which needs the same PairingGroup machinery). Built once, tagged
# `pkg-base`; app/Dockerfile and ca/Dockerfile both FROM it, so the slow
# PBC/charm compile only happens once instead of once per component.
#
# Pinned to Ubuntu 20.04 because charm-crypto's PBC bindings predate
# OpenSSL 3.x's API changes and fail to build on newer bases.
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    flex \
    bison \
    libgmp-dev \
    libssl-dev \
    m4 \
    python3 \
    python3-pip \
    python3-dev \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN wget https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz \
    && tar -xzf pbc-0.5.14.tar.gz \
    && cd pbc-0.5.14 \
    && ./configure \
    && make \
    && make install \
    && ldconfig

RUN pip3 install --upgrade pip setuptools wheel

RUN git clone https://github.com/JHUISI/charm.git /build/charm \
    && cd /build/charm \
    && ./configure.sh \
    && pip3 install .

RUN pip3 install cryptography==41.0.7
