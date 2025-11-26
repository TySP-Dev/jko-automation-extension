# JKO Course Automation

Automates course completion on [jkodirect.jten.mil](https://jkodirect.jten.mil/) using AI vision capabilities. The script intelligently navigates through course content, reads lessons, and answers multiple-choice tests using either Claude API or Ollama.

## Features

- **AI-Powered Navigation**: Uses vision AI to understand the screen and make intelligent decisions
- **Adaptive Course Handling**: Works with different course layouts and variations
- **Multiple Choice Test Solving**: Automatically answers quiz questions using AI analysis
- **Dual AI Provider Support**: Works with both Claude API and Ollama (local)
- **Progress Tracking**: Saves screenshots for debugging and progress monitoring
- **Linux Compatible**: Fully tested on Arch Linux (works on all Linux distros)

## Prerequisites

### System Requirements

- Python 3.8 or higher
- Linux (tested on Arch, works on Ubuntu/Debian/Fedora/etc.)
- Internet connection for JKO website access

### AI Provider Setup

Choose one of the following:

#### Option 1: Claude API (Recommended)

1. Get an API key from [Anthropic Console](https://console.anthropic.com/)
2. Set it as an environment variable:
   ```bash
   export ANTHROPIC_API_KEY='your-api-key-here'
   ```

#### Option 2: Ollama (Local/Free)

1. Install Ollama:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. Pull a vision-capable model:
   ```bash
   ollama pull llava
   ```

3. Ensure Ollama is running:
   ```bash
   ollama serve
   ```

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd Test_Project
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Linux
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

## Usage

### Basic Usage with Claude API

```bash
python jko_course_automation.py "https://jkodirect.jten.mil/path/to/course"
```

### Using Ollama (Local)

```bash
python jko_course_automation.py "https://jkodirect.jten.mil/path/to/course" --ai-provider ollama
```

### Advanced Options

```bash
# Run with debug output
python jko_course_automation.py "COURSE_URL" --debug

# Run in headless mode (no visible browser)
python jko_course_automation.py "COURSE_URL" --headless

# Use specific Ollama model
python jko_course_automation.py "COURSE_URL" --ai-provider ollama --ollama-model llava:13b

# Specify Claude API key directly
python jko_course_automation.py "COURSE_URL" --claude-api-key "sk-ant-..."

# Set maximum iterations (default: 500)
python jko_course_automation.py "COURSE_URL" --max-iterations 1000
```

### Full Command Line Options

```
usage: jko_course_automation.py [-h] [--ai-provider {claude,ollama}]
                                [--claude-api-key CLAUDE_API_KEY]
                                [--ollama-url OLLAMA_URL]
                                [--ollama-model OLLAMA_MODEL]
                                [--headless] [--debug]
                                [--max-iterations MAX_ITERATIONS]
                                course_url

positional arguments:
  course_url            URL of the JKO course to complete

optional arguments:
  -h, --help            show this help message and exit
  --ai-provider {claude,ollama}
                        AI provider to use (default: claude)
  --claude-api-key CLAUDE_API_KEY
                        Claude API key (or set ANTHROPIC_API_KEY env var)
  --ollama-url OLLAMA_URL
                        Ollama server URL (default: http://localhost:11434)
  --ollama-model OLLAMA_MODEL
                        Ollama model to use (default: llava)
  --headless            Run browser in headless mode
  --debug               Enable debug output
  --max-iterations MAX_ITERATIONS
                        Maximum iterations before stopping (default: 500)
```

## How It Works

1. **Screen Capture**: Takes screenshots of the current course page
2. **AI Analysis**: Sends screenshots to AI (Claude or Ollama) for analysis
3. **Decision Making**: AI determines the next action:
   - Click "Start" to begin course
   - Click "Next Page" to view more content
   - Click "Next Lesson" when ready to proceed
   - Answer multiple choice questions
   - Submit tests
4. **Action Execution**: Executes the AI's decision
5. **Repeat**: Continues until course is complete

## Screenshots

All screenshots are saved in the `screenshots/` directory for debugging and progress tracking.

## Troubleshooting

### Playwright Installation Issues

If you get playwright errors:
```bash
playwright install-deps  # Install system dependencies
playwright install chromium
```

### Ollama Connection Issues

Make sure Ollama is running:
```bash
systemctl status ollama  # Check status
ollama serve             # Start manually
```

Test Ollama:
```bash
curl http://localhost:11434/api/tags
```

### Claude API Issues

Verify your API key:
```bash
echo $ANTHROPIC_API_KEY
```

Test the API:
```bash
python -c "import anthropic; client = anthropic.Anthropic(); print('API key valid')"
```

### Course Not Progressing

- Use `--debug` flag to see detailed output
- Check screenshots in `screenshots/` directory
- Verify the course URL is correct
- Some courses may have unusual layouts - the AI should adapt, but complex cases may need manual intervention

### Permission Issues on Linux

If you get permission errors:
```bash
chmod +x jko_course_automation.py
```

## Important Notes

- **Educational Use**: This tool is intended for authorized educational purposes only
- **Rate Limiting**: The script includes delays to avoid overwhelming the JKO servers
- **Monitoring**: While the script is automated, it's recommended to monitor progress
- **Manual Intervention**: Some courses may require manual intervention for unusual layouts
- **Network Requirements**: Ensure stable internet connection for both JKO access and AI API calls

## Architecture

```
jko_course_automation.py
├── AIProvider (base class)
│   ├── ClaudeProvider - Uses Anthropic's Claude API
│   └── OllamaProvider - Uses local Ollama server
└── JKOCourseAutomation
    ├── Browser automation (Playwright)
    ├── Screenshot capture
    ├── AI decision making
    ├── Element interaction
    └── Course navigation logic
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License

## Disclaimer

This tool is provided for educational purposes. Users are responsible for ensuring their use complies with JKO's terms of service and applicable regulations. Always verify that automated course completion is permitted before use.

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Review screenshots in `screenshots/` directory with `--debug` flag
3. Open an issue on GitHub with debug output and screenshots
