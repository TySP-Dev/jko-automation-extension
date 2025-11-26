# Quick Start Guide

Get up and running with JKO Course Automation in 5 minutes!

## Option 1: Quick Setup (Recommended)

```bash
# Run the automated setup script
./setup.sh

# Activate virtual environment
source venv/bin/activate

# Set your Claude API key
export ANTHROPIC_API_KEY='your-api-key-here'

# Run the automation
python jko_course_automation.py 'YOUR_COURSE_URL'
```

## Option 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Set API key
export ANTHROPIC_API_KEY='your-api-key-here'

# Run
python jko_course_automation.py 'YOUR_COURSE_URL'
```

## Option 3: Using Ollama (Free, Local)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download vision model
ollama pull llava

# Start Ollama (in a separate terminal)
ollama serve

# Run the automation with Ollama
python jko_course_automation.py 'YOUR_COURSE_URL' --ai-provider ollama
```

## Getting Your Course URL

1. Go to [jkodirect.jten.mil](https://jkodirect.jten.mil/)
2. Log in to your account
3. Find the course you want to automate
4. Copy the full URL from your browser's address bar
5. Use that URL with the script

Example URL format:
```
https://jkodirect.jten.mil/path/to/course/USA-AU-01
```

## First Run Example

```bash
# With visible browser (recommended for first time)
python jko_course_automation.py 'YOUR_COURSE_URL' --debug

# Watch as the AI navigates through the course
# Screenshots will be saved to screenshots/ folder
```

## Common Issues

### "playwright not found"
```bash
pip install playwright
playwright install chromium
```

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY='your-key-here'
# Or use --claude-api-key flag
```

### "Connection refused" (Ollama)
```bash
# Make sure Ollama is running
ollama serve
```

## Tips

- Use `--debug` flag to see what's happening
- Use `--headless` for background operation
- Check `screenshots/` folder if something goes wrong
- Start with a short test course first

## Need Help?

See the full [README.md](README.md) for detailed documentation.
