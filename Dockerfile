FROM ocaml/opam:debian-12-ocaml-5.1 AS builder

WORKDIR /src
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential m4 pkg-config git ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src

USER opam

RUN opam update --yes \
    && opam install --yes ocamlfind ounit2 || true

SHELL ["/bin/bash", "-lc"]

RUN eval "$(opam env)" && make

RUN eval "$(opam env)" && test -x ./marina


FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/marina /usr/local/bin/marina
RUN chmod +x /usr/local/bin/marina

COPY ./api /app/
COPY ./start.sh /app/start.sh
COPY ./api/requirements.txt /app/requirements.txt

RUN chmod +x /app/start.sh

RUN pip install --no-cache-dir -r /app/requirements.txt

RUN curl -sSL -o /tmp/ngrok.tgz "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz" \
    && tar -xzf /tmp/ngrok.tgz -C /usr/local/bin/ \
    && rm /tmp/ngrok.tgz \
    && chmod +x /usr/local/bin/ngrok


EXPOSE 8081

ENTRYPOINT ["bash", "/app/start.sh"]
