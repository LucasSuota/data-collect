# Front (build estático) + Caddy com limite de taxa. Duas etapas: o Node só existe no build.
FROM node:22-bookworm-slim AS front
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2-builder AS caddy
RUN xcaddy build --with github.com/mholt/caddy-ratelimit

FROM caddy:2
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
COPY docker/web/Caddyfile /etc/caddy/Caddyfile
COPY --from=front /frontend/dist /srv
EXPOSE 80 443
