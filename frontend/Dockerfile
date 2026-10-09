FROM node:22-slim

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1 \
    WATCHPACK_POLLING=true \
    CHOKIDAR_USEPOLLING=true

# Install dependencies first so code edits don't invalidate this layer.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

EXPOSE 3000
# `npm run dev` listens on 0.0.0.0:3000 and proxies /api to BACKEND_ORIGIN (set by docker compose).
CMD ["npm", "run", "dev"]
