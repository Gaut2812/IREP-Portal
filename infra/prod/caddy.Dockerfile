# Caddy with the open-source rate-limit module (github.com/mholt/caddy-ratelimit), for the per-IP
# limits on sign-in and OTP in the Caddyfile. Build context: infra/prod.
FROM caddy:2.10-builder AS builder
RUN xcaddy build --with github.com/mholt/caddy-ratelimit@v0.1.0

FROM caddy:2.10-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
