# Risk-retirement spike: confirm charm-crypto (CP-ABE) builds and runs.
# Pinned to Ubuntu 20.04 because charm-crypto's PBC bindings predate
# OpenSSL 3.x's API changes and fail to build on newer bases (22.04+, bookworm).
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

# Build PBC (Pairing-Based Cryptography) library from source — not packaged for 20.04.
WORKDIR /build
RUN wget https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz \
    && tar -xzf pbc-0.5.14.tar.gz \
    && cd pbc-0.5.14 \
    && ./configure \
    && make \
    && make install \
    && ldconfig

RUN pip3 install --upgrade pip setuptools wheel

# charm-crypto has no PyPI release compatible with this stack; install from source.
# Use pip (not `setup.py install`) -- the latter drops an egg into site-packages,
# which Ubuntu's system Python doesn't search (it only looks in dist-packages).
RUN git clone https://github.com/JHUISI/charm.git /build/charm \
    && cd /build/charm \
    && ./configure.sh \
    && pip3 install .

WORKDIR /app
COPY smoke_test.py .

CMD ["python3", "smoke_test.py"]
