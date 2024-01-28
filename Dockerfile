# Use the official Node.js LTS image as the base image
FROM node:lts-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy package.json, pnpm-lock.yaml, and tsconfig.json to the working directory
COPY . ./

# Add bash to enter into container for debugging
RUN apk add --no-cache bash

# Install pnpm
RUN npm install -g pnpm ts-node tsx typescript

# Install dependencies
RUN pnpm install

# Expose the port your app is running on
EXPOSE 8000

# Command to run the app
CMD ["pnpm", "run", "dev"]
