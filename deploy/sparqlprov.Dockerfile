FROM rust:1.97.1-bookworm AS build
WORKDIR /build

COPY Cargo.toml Cargo.lock ./
COPY src/ ./src/

RUN cargo build --locked --release \
    --features server \
    --bin sparql-proof-server

FROM debian:bookworm-slim

COPY --from=build /build/target/release/sparql-proof-server /usr/local/bin/sparql-proof-server
COPY LICENSE /usr/share/licenses/sparqlprov/LICENSE

USER 10001:10001
ENV SPARQL_PROOF_ADDR=0.0.0.0:3000
EXPOSE 3000

ENTRYPOINT ["sparql-proof-server"]