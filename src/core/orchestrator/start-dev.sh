#!/bin/bash

# ClouDO Development Startup Script
# Starts both Azure Function App and Next.js frontend

set -e

echo "🚀 Starting ClouDO Development Environment..."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+ first."
    exit 1
fi

# Install Next.js dependencies if needed
if [ ! -d "frontend-nextjs/node_modules" ]; then
    echo "📦 Installing Next.js dependencies..."
    cd frontend-nextjs
    npm install
    cd ..
fi

# Create .env.local if it doesn't exist
if [ ! -f "frontend-nextjs/.env.local" ]; then
    echo "📝 Creating .env.local from example..."
    cp frontend-nextjs/.env.local.example frontend-nextjs/.env.local
fi

# Start Next.js in background
echo -e "${BLUE}▶️  Starting Next.js on http://localhost:3000${NC}"
cd frontend-nextjs
npm run dev > ../nextjs.log 2>&1 &
NEXTJS_PID=$!
cd ..

# Wait for Next.js to start
echo "⏳ Waiting for Next.js to be ready..."
sleep 5

# Check if Next.js started successfully
if ! ps -p $NEXTJS_PID > /dev/null; then
    echo "❌ Next.js failed to start. Check nextjs.log for details."
    cat nextjs.log
    exit 1
fi

echo -e "${GREEN}✅ Next.js started (PID: $NEXTJS_PID)${NC}"

# Start Azure Function App
echo -e "${BLUE}▶️  Starting Azure Function App on http://localhost:7071${NC}"
export NEXTJS_URL=http://localhost:3000
func start

# Cleanup on exit
trap "echo '🛑 Stopping services...'; kill $NEXTJS_PID 2>/dev/null; exit" INT TERM EXIT
