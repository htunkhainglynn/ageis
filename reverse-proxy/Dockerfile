FROM golang:1.23-alpine AS build

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/aegis-proxy ./cmd/proxy

FROM alpine:3.22
RUN addgroup -S aegis && adduser -S -G aegis aegis
COPY --from=build /out/aegis-proxy /usr/local/bin/aegis-proxy
USER aegis
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/aegis-proxy"]
