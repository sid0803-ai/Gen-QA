# Sprint 1 dev image: docker-compose runs `npm run dev -- --host 0.0.0.0`
# and bind-mounts ./frontend over /app, so this Dockerfile only needs to
# produce a container with dependencies installed; source is mounted live.
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
