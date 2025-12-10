#!/bin/bash

# Check if uv is installed, if not install it
if command -v uv &> /dev/null; then
    echo "uv is installed"
else
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv .venv
fi
# Activate virtual environment
source .venv/bin/activate

echo "Starting the application..."

# python3 src/app.py &
uv run python src/app.py &
BACKEND_PID=$!
# Give the backend some time to start
sleep 3
echo ""
echo "✓ ScribeTwin is running!\n"
echo " Click:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the application."
trap "kill $BACKEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait