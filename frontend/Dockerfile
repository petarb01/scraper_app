# ---- build stage ----
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- serve stage ----
FROM nginx:1.27-alpine AS serve

# Remove default nginx static content
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# nginx config: forward all routes to index.html (SPA routing)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
