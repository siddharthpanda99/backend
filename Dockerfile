# Use an official Node.js runtime as a parent image
FROM node:16

# Create app directory
WORKDIR /app

# Copy the package.json and package-lock.json files to /app 
COPY package*.json /app

# Install dependencies
RUN npm i -g pnpm
# RUN pnpm ci --only=production && pnpm cache clean --force
RUN pnpm install

# Copy the rest of the application code to /app
COPY . /app

# Expose port 8000
EXPOSE 8000

# Start the server
CMD ["pnpm","run","dev"]