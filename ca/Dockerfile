# The CA node: identity issuance + lab coordination. No blockchain here --
# built on ../base for charm-crypto (needed only to generate MA-ABE public
# parameters) plus a thin Flask HTTP layer.
FROM pkg-base

COPY requirements.txt /build/requirements.txt
RUN pip3 install -r /build/requirements.txt

WORKDIR /ca
COPY . .

CMD ["python3", "app.py"]
