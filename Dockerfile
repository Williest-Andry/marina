FROM ocaml/opam:debian-12-ocaml-5.1 AS builder

WORKDIR /src
COPY . /src

USER root 

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential m4 pkg-config git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

USER opam

RUN opam update --yes \
 && opam install --yes ocamlfind ounit2 || true

SHELL ["/bin/bash", "-lc"]

RUN eval $(opam env) && make

RUN test -x ./marina


FROM python:3.11-slim

WORKDIR /src
COPY ./api /src/

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/marina /usr/local/bin/marina
RUN chmod +x /usr/local/bin/marina

COPY ./api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
