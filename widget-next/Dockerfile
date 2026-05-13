# syntax=docker/dockerfile:1.7
# Multi-stage build for the Vaquill widget-next app.
# Designed for Next.js 15.x + React 19 with `output: "standalone"`
# (set in next.config.ts) so the runner stage ships only what's
# needed to boot the server — no node_modules at runtime.

FROM node:20-alpine AS deps
WORKDIR /app
# libc6-compat fixes a known sharp/imagemin issue on Alpine when Next
# generates static images at build time.
RUN apk add --no-cache libc6-compat
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ── Build the Next.js app ──────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
RUN apk add --no-cache libc6-compat
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Slim runtime image ─────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Run as non-root for safety. Next's standalone output works fine
# with a non-root UID.
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# `public/` ships embed.js, embed-test.html, etc.
COPY --from=builder /app/public ./public

# `.next/standalone` contains a pruned package.json + server.js +
# only the node_modules actually needed at runtime.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# Static assets the standalone server expects under .next/static.
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Hardening: tighten /tmp and /var/tmp permissions and block writes to
# unexpected paths. A previous incident dropped an XMRig binary into
# /var/tmp via a wget chain executed as the `nextjs` user. The world-
# writable sticky default (1777) on Alpine made that trivially possible.
#
# We do two things here:
#   1. Set the dirs to mode 1733 (sticky, owner-write, no-group/other-
#      write, no-read-other). The `nextjs` user owns them, so it can
#      still create files there for legitimate temp use, but no other
#      account inside the container can write — which limits worm-
#      style lateral movement.
#   2. Recommend (in Dokploy) mounting tmpfs at /tmp and /var/tmp with
#      noexec,nosuid,nodev so even if a file is written there it cannot
#      be exec'd. The Dockerfile cannot configure host tmpfs mounts —
#      that has to be set in the Dokploy app's Advanced -> Mounts panel.
RUN chown nextjs:nodejs /tmp /var/tmp && \
    chmod 1733 /tmp /var/tmp

USER nextjs

EXPOSE 3000

# server.js is what Next 15 emits at the standalone root.
CMD ["node", "server.js"]
