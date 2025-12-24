# Multi-stage Dockerfile for ClouDO Next.js Frontend
# This builds the Next.js frontend in standalone mode for production

# ============================================
# Stage 1: Build Next.js
# ============================================
FROM node:22-alpine AS builder

WORKDIR /app

# Disable telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . ./

# Build Next.js for production
# Note: Next.js 'standalone' output must be enabled in next.config.ts/js
ENV NODE_ENV=production
RUN npm run build

# ============================================
# Stage 2: Runtime
# ============================================
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create a non-root user for security
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy necessary files from builder
# With output: 'standalone', Next.js puts everything in .next/standalone
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# server.js is created by next build from the standalone output
CMD ["node", "server.js"]
