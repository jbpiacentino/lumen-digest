# Use Node.js 20 (LTS) as the base
FROM node:20-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (needed for some build tools)
RUN apt-get update && apt-get install -y \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy package.json and package-lock.json first
# This allows Docker to cache the 'npm install' layer
COPY package*.json ./

# Install dependencies
RUN npm install

# We don't COPY the rest of the code here because docker-compose 
# will mount your local folder as a volume for development.
# For a production build, you would add: COPY . .

# Nuxt runs on port 3000 by default
EXPOSE 3000

# Set environment variables to ensure Nuxt listens on all network interfaces
ENV HOST=0.0.0.0
ENV PORT=3000
ENV NODE_ENV=development

# Start the Nuxt development server
CMD ["npm", "run", "dev"]
