# syntax=docker/dockerfile:1.4
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm config set strict-ssl false && \
    npm config set registry http://registry.npmjs.org/ && \
    --mount=type=cache,target=/root/.npm \
    npm install --prefer-offline --no-audit --no-fund
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
