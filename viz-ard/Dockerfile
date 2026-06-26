# DNS-AID Explorer — Next.js standalone build.
# Multi-stage: install deps, build, then run from a slim runtime image.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN corepack enable && npm install

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Standalone output bundles only what's needed.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
# /app/public is optional — skip; we don't ship public assets in this app.

EXPOSE 8080
ENV PORT=8080
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
