# Next.js web app. Build context: the repository root (the web app type-imports packages/api-client).
# NEXT_PUBLIC_API_URL is baked in at build time, so rebuild when the domain changes.
FROM node:22-slim AS build
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /repo
COPY packages/api-client packages/api-client
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml apps/web/
WORKDIR /repo/apps/web
RUN pnpm install --frozen-lockfile
COPY apps/web ./
RUN rm -rf .next node_modules/.cache test-results test-results-demo
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN test -n "$NEXT_PUBLIC_API_URL" && pnpm build && pnpm prune --prod

FROM node:22-slim
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /repo/apps/web/package.json ./
COPY --from=build --chown=node:node /repo/apps/web/node_modules ./node_modules
COPY --from=build --chown=node:node /repo/apps/web/.next ./.next
COPY --from=build --chown=node:node /repo/apps/web/public ./public
COPY --from=build --chown=node:node /repo/apps/web/next.config.ts ./
USER node
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "-p", "3000", "-H", "0.0.0.0"]
