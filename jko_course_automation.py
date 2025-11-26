#!/usr/bin/env python3
"""
JKO Course Automation Script
Automates course completion on jkodirect.jten.mil using AI vision
Supports both Claude API and Ollama for intelligent navigation and test-taking
"""

import os
import sys
import time
import base64
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List
import asyncio

from playwright.async_api import async_playwright, Page, Browser
import anthropic
import httpx


class AIProvider:
    """Base class for AI providers"""

    async def analyze_screen(self, screenshot_base64: str, prompt: str) -> str:
        raise NotImplementedError


class ClaudeProvider(AIProvider):
    """Claude API provider for vision analysis"""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    async def analyze_screen(self, screenshot_base64: str, prompt: str) -> str:
        """Analyze screenshot using Claude API"""
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": screenshot_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
            )
            return message.content[0].text
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            raise


class OllamaProvider(AIProvider):
    """Ollama provider for vision analysis"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llava"):
        self.base_url = base_url
        self.model = model

    async def analyze_screen(self, screenshot_base64: str, prompt: str) -> str:
        """Analyze screenshot using Ollama"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [screenshot_base64],
                        "stream": False
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
        except Exception as e:
            print(f"Error calling Ollama API: {e}")
            raise


class JKOCourseAutomation:
    """Main automation class for JKO courses"""

    def __init__(self, ai_provider: AIProvider, headless: bool = False, debug: bool = False):
        self.ai_provider = ai_provider
        self.headless = headless
        self.debug = debug
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        self.screenshot_count = 0

    async def start_browser(self):
        """Initialize browser and page"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        self.page = await context.new_page()

    async def close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()

    async def take_screenshot(self, name: str = "screen") -> str:
        """Take screenshot and return base64 encoded string"""
        self.screenshot_count += 1
        screenshot_path = self.screenshot_dir / f"{self.screenshot_count:04d}_{name}.png"

        screenshot_bytes = await self.page.screenshot(path=str(screenshot_path), full_page=False)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

        if self.debug:
            print(f"Screenshot saved: {screenshot_path}")

        return screenshot_base64

    async def wait_for_page_load(self, timeout: int = 30):
        """Wait for page to load"""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            await asyncio.sleep(1)  # Additional wait for dynamic content
        except Exception as e:
            if self.debug:
                print(f"Page load timeout (continuing anyway): {e}")

    async def analyze_and_decide(self, context: str) -> Dict[str, Any]:
        """Analyze current screen and decide what action to take"""
        screenshot = await self.take_screenshot("analysis")

        prompt = f"""You are automating a JKO (Joint Knowledge Online) course website.
Analyze this screenshot and determine what action should be taken next.

Context: {context}

The course interface may have:
- A "Start" button to begin the course
- "Next Lesson" button at the top to move to next lesson
- "Next Page" button to view more content in current lesson (must click through all pages before Next Lesson becomes available)
- "Suspend Lesson" to bookmark progress
- "Exit Course" to close
- Multiple choice questions with radio buttons or clickable options
- A submit button for tests
- Content pages with text and images that need to be reviewed

Respond ONLY with a JSON object (no markdown formatting, no code blocks) with this structure:
{{
    "action": "click|scroll|wait|read|answer_question|complete",
    "element": "description of what to click (if action is click)",
    "reasoning": "why you chose this action",
    "answer_index": 0 (only for answer_question action, 0-based index of the answer to select),
    "is_test": false (true if this appears to be a test/quiz question)
}}

Examples:
- If you see a "Start" button: {{"action": "click", "element": "Start button", "reasoning": "Need to start the course"}}
- If you see a "Next Page" button: {{"action": "click", "element": "Next Page button", "reasoning": "Need to view all content"}}
- If you see a "Next Lesson" button: {{"action": "click", "element": "Next Lesson button", "reasoning": "Completed current lesson"}}
- If you see a multiple choice question: {{"action": "answer_question", "element": "Question with options", "reasoning": "Need to answer test question", "answer_index": 2, "is_test": true}}
- If content is still loading: {{"action": "wait", "reasoning": "Page still loading"}}
- If at course completion: {{"action": "complete", "reasoning": "Course finished"}}

Respond with ONLY the JSON object, nothing else."""

        response = await self.ai_provider.analyze_screen(screenshot, prompt)

        if self.debug:
            print(f"\nAI Response:\n{response}\n")

        # Parse JSON response, handling potential markdown code blocks
        response = response.strip()
        if response.startswith("```"):
            # Remove markdown code blocks
            lines = response.split('\n')
            response = '\n'.join([l for l in lines if not l.startswith('```')])
            response = response.strip()

        try:
            decision = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"Failed to parse AI response as JSON: {e}")
            print(f"Response was: {response}")
            # Default to waiting if we can't parse
            decision = {"action": "wait", "reasoning": "Failed to parse AI response"}

        return decision

    async def find_and_click_element(self, description: str) -> bool:
        """Find and click an element based on AI description"""
        # Try various selectors based on description keywords
        selectors = []
        desc_lower = description.lower()

        # Common button texts
        if "start" in desc_lower:
            selectors.extend([
                "button:has-text('Start')",
                "a:has-text('Start')",
                "input[value*='Start']",
                "[onclick*='start']"
            ])
        elif "next page" in desc_lower:
            selectors.extend([
                "button:has-text('Next Page')",
                "a:has-text('Next Page')",
                "input[value*='Next Page']",
                ".next-page",
                "#nextPage"
            ])
        elif "next lesson" in desc_lower:
            selectors.extend([
                "button:has-text('Next Lesson')",
                "a:has-text('Next Lesson')",
                "input[value*='Next Lesson']",
                ".next-lesson",
                "#nextLesson"
            ])
        elif "submit" in desc_lower:
            selectors.extend([
                "button:has-text('Submit')",
                "input[type='submit']",
                "button[type='submit']",
                "a:has-text('Submit')"
            ])
        elif "continue" in desc_lower:
            selectors.extend([
                "button:has-text('Continue')",
                "a:has-text('Continue')",
                "input[value*='Continue']"
            ])

        # Try each selector
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    # Check if element is visible
                    is_visible = await element.is_visible()
                    if is_visible:
                        await element.click()
                        if self.debug:
                            print(f"Clicked element with selector: {selector}")
                        await asyncio.sleep(1)
                        return True
            except Exception as e:
                if self.debug:
                    print(f"Selector {selector} failed: {e}")
                continue

        # If specific selectors didn't work, try a more general approach
        # Look for visible buttons with text matching the description
        try:
            all_buttons = await self.page.query_selector_all("button, a, input[type='button'], input[type='submit']")
            for button in all_buttons:
                try:
                    is_visible = await button.is_visible()
                    if not is_visible:
                        continue

                    text = await button.text_content() or ""
                    value = await button.get_attribute("value") or ""
                    combined_text = (text + " " + value).lower()

                    # Check if any keyword from description matches
                    keywords = desc_lower.split()
                    if any(keyword in combined_text for keyword in keywords if len(keyword) > 3):
                        await button.click()
                        if self.debug:
                            print(f"Clicked button with text: {text or value}")
                        await asyncio.sleep(1)
                        return True
                except:
                    continue
        except Exception as e:
            if self.debug:
                print(f"General button search failed: {e}")

        print(f"Could not find element: {description}")
        return False

    async def answer_multiple_choice(self, answer_index: int) -> bool:
        """Select a multiple choice answer and submit if needed"""
        try:
            # Look for radio buttons or clickable answer options
            radio_buttons = await self.page.query_selector_all("input[type='radio']")

            if radio_buttons and answer_index < len(radio_buttons):
                # Click the radio button
                await radio_buttons[answer_index].click()
                if self.debug:
                    print(f"Selected answer {answer_index + 1} (radio button)")
                await asyncio.sleep(0.5)
                return True

            # Try looking for clickable divs/labels with answer classes
            answer_elements = await self.page.query_selector_all(
                ".answer, .option, .choice, [class*='answer'], [class*='option'], [class*='choice']"
            )

            if answer_elements and answer_index < len(answer_elements):
                await answer_elements[answer_index].click()
                if self.debug:
                    print(f"Selected answer {answer_index + 1} (clickable element)")
                await asyncio.sleep(0.5)
                return True

            print(f"Could not find answer option at index {answer_index}")
            return False

        except Exception as e:
            print(f"Error selecting answer: {e}")
            return False

    async def run_course(self, course_url: str, max_iterations: int = 500):
        """Main loop to complete a course"""
        print(f"Starting course automation for: {course_url}")

        await self.start_browser()

        try:
            # Navigate to course
            await self.page.goto(course_url)
            await self.wait_for_page_load()

            iteration = 0
            consecutive_waits = 0
            max_consecutive_waits = 3

            while iteration < max_iterations:
                iteration += 1
                print(f"\n--- Iteration {iteration} ---")

                # Analyze current screen
                decision = await self.analyze_and_decide(
                    f"Iteration {iteration}, navigating through course content"
                )

                print(f"Action: {decision.get('action')}")
                print(f"Reasoning: {decision.get('reasoning')}")

                action = decision.get("action", "wait")

                if action == "complete":
                    print("\n✓ Course completed!")
                    break

                elif action == "click":
                    element_desc = decision.get("element", "")
                    success = await self.find_and_click_element(element_desc)
                    if success:
                        await self.wait_for_page_load()
                        consecutive_waits = 0
                    else:
                        print("Click failed, will retry on next iteration")
                        await asyncio.sleep(2)

                elif action == "answer_question":
                    answer_index = decision.get("answer_index", 0)
                    print(f"Answering question with option {answer_index + 1}")

                    success = await self.answer_multiple_choice(answer_index)

                    if success:
                        # Look for submit button
                        await asyncio.sleep(1)
                        submit_clicked = await self.find_and_click_element("Submit")

                        if submit_clicked:
                            print("Submitted answer")
                            await self.wait_for_page_load()

                        consecutive_waits = 0
                    else:
                        await asyncio.sleep(2)

                elif action == "scroll":
                    await self.page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
                    await asyncio.sleep(1)
                    consecutive_waits = 0

                elif action == "read":
                    # Just wait a bit for user to "read" content
                    print("Reading content...")
                    await asyncio.sleep(2)
                    consecutive_waits = 0

                else:  # wait
                    print("Waiting...")
                    await asyncio.sleep(3)
                    consecutive_waits += 1

                    if consecutive_waits >= max_consecutive_waits:
                        print("Too many consecutive waits, trying to find Next button...")
                        # Force try to click next
                        await self.find_and_click_element("Next Page")
                        consecutive_waits = 0
                        await asyncio.sleep(2)

                # Small delay between iterations
                await asyncio.sleep(1)

            if iteration >= max_iterations:
                print(f"\n⚠ Reached maximum iterations ({max_iterations})")

        finally:
            if not self.headless:
                print("\nPress Enter to close browser...")
                input()

            await self.close_browser()


async def main():
    parser = argparse.ArgumentParser(
        description="Automate JKO course completion using AI vision"
    )
    parser.add_argument(
        "course_url",
        help="URL of the JKO course to complete"
    )
    parser.add_argument(
        "--ai-provider",
        choices=["claude", "ollama"],
        default="claude",
        help="AI provider to use (default: claude)"
    )
    parser.add_argument(
        "--claude-api-key",
        help="Claude API key (or set ANTHROPIC_API_KEY env var)"
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--ollama-model",
        default="llava",
        help="Ollama model to use (default: llava)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=500,
        help="Maximum iterations before stopping (default: 500)"
    )

    args = parser.parse_args()

    # Initialize AI provider
    if args.ai_provider == "claude":
        api_key = args.claude_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: Claude API key required. Set --claude-api-key or ANTHROPIC_API_KEY env var")
            sys.exit(1)
        ai_provider = ClaudeProvider(api_key)
        print("Using Claude API for vision analysis")
    else:
        ai_provider = OllamaProvider(args.ollama_url, args.ollama_model)
        print(f"Using Ollama ({args.ollama_model}) for vision analysis")

    # Create automation instance
    automation = JKOCourseAutomation(
        ai_provider=ai_provider,
        headless=args.headless,
        debug=args.debug
    )

    # Run the course
    await automation.run_course(args.course_url, max_iterations=args.max_iterations)


if __name__ == "__main__":
    asyncio.run(main())
