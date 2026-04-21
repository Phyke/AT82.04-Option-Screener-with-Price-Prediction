FROM node:24-alpine

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

EXPOSE 5173

# Default to production, can be overridden via docker-compose
ENV NODE_ENV=production

# Build the app - for dev mode, this will be skipped via command override
RUN npm run build

# For production: run the built app
# For development: this will be overridden in docker-compose to run dev server
CMD ["node", "build"]
