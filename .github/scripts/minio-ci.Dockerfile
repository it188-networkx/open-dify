# Rebuild the exact MinIO source release used by the Milvus fixture.
# The original Docker Hub and Quay image tag is no longer available.
FROM golang:1.20.14-bookworm AS build
WORKDIR /src
RUN curl --fail --location \
      https://codeload.github.com/minio/minio/tar.gz/05444a0f6af8389b9bb85280fc31337c556d4300 \
      --output /tmp/minio.tar.gz \
    && echo "7b9e127c420bac936af017661667ebc3224abe13afa1699b104ffa7df9e51ad6  /tmp/minio.tar.gz" | sha256sum --check \
    && tar --extract --gzip --file /tmp/minio.tar.gz --strip-components=1 \
    && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/minio .

FROM alpine:3.21
RUN apk add --no-cache ca-certificates curl
COPY --from=build /out/minio /usr/local/bin/minio
CMD ["minio", "server", "/data"]
