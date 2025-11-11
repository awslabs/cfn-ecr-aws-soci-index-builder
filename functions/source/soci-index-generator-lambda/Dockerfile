FROM golang:1.24-alpine AS builder

# Install only essential build dependencies
RUN apk add --no-cache \
    make \
    git \
    zip \
    gcc \
    musl-dev \
    zlib-dev \
    zlib-static

WORKDIR /build

COPY . .

RUN --mount=type=tmpfs,target=/tmp \
    GOCACHE=/tmp/go-cache GOTMPDIR=/tmp \
    make -f Makefile

FROM alpine

WORKDIR /build

COPY --from=builder /build/soci_index_generator_lambda.zip /build/

CMD mkdir -p /output/ && mv /build/soci_index_generator_lambda.zip /output/
