#!/bin/bash
# JKO Course Automation Setup Script for Linux
# This script automates the installation process

set -e  # Exit on error

echo "================================================"
echo "JKO Course Automation Setup"
echo "================================================"
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Found Python $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists, skipping..."
else
    python3 -m venv venv
    echo "Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
echo ""
echo "Installing Playwright browsers..."
playwright install chromium
playwright install-deps chromium || {
    echo "Warning: Could not install all system dependencies."
    echo "You may need to run: sudo playwright install-deps"
}

# Create .env file if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env and add your ANTHROPIC_API_KEY"
else
    echo ".env file already exists"
fi

# Make the main script executable
chmod +x jko_course_automation.py

echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. (Optional) If using Claude API, set your API key:"
echo "   export ANTHROPIC_API_KEY='your-api-key-here'"
echo "   Or edit the .env file"
echo ""
echo "3. (Optional) If using Ollama, install and start it:"
echo "   curl -fsSL https://ollama.com/install.sh | sh"
echo "   ollama pull llava"
echo "   ollama serve"
echo ""
echo "4. Run the automation script:"
echo "   python jko_course_automation.py 'COURSE_URL'"
echo ""
echo "For more options, run:"
echo "   python jko_course_automation.py --help"
echo ""
