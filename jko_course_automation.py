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
        self.main_page: Optional[Page] = None  # Keep reference to main page
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

        # Check if we should screenshot the iframe content instead of main page
        screenshot_target = self.page

        # If we're in a course, try to screenshot the iframe content
        if self.main_page:
            try:
                # Check if we're in a course
                in_course = await self.check_if_in_course()

                if in_course:
                    # Try to get course content frame
                    course_frame = await self.get_course_content_frame()

                    if course_frame:
                        screenshot_target = course_frame
                        print(f"📸 Taking screenshot of course content (inside iframe)")
                    else:
                        # If no iframe, use main page
                        screenshot_target = self.main_page
                        print(f"📸 Taking screenshot of course page (main)")
                else:
                    # Not in course, use main page
                    screenshot_target = self.main_page
                    print(f"📸 Taking screenshot of main page")
            except:
                # On error, fall back to self.page
                pass

        screenshot_bytes = await screenshot_target.screenshot(path=str(screenshot_path), full_page=False)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

        if self.debug:
            print(f"Screenshot saved: {screenshot_path}")

        return screenshot_base64

    async def wait_for_page_load(self, timeout: int = 30):
        """Wait for page to load"""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            await asyncio.sleep(2)  # Additional wait for dynamic content and iframes
        except Exception as e:
            if self.debug:
                print(f"Page load timeout (continuing anyway): {e}")

    async def get_course_content_frame(self):
        """Get the course content iframe if it exists"""
        try:
            # Check for course content iframe
            content_iframe = await self.main_page.query_selector('iframe[name="text"], iframe#text, iframe.contentIframe')

            if content_iframe:
                frame = await content_iframe.content_frame()
                return frame

            return None

        except Exception as e:
            if self.debug:
                print(f"Error getting course frame: {e}")
            return None

    async def check_if_in_course(self) -> bool:
        """Check if we're currently inside a course (vs course selection page)"""
        try:
            if not self.main_page:
                print("⚠ Warning: main_page is None in check_if_in_course()")
                return False

            # Look for course player indicators on the main page
            indicators = [
                '#playerCourseTitle',
                '.content_topBar',
                'iframe[name="text"]',
                '.playerImageContainer'
            ]

            for indicator in indicators:
                try:
                    element = await self.main_page.query_selector(indicator)
                    if element:
                        if self.debug:
                            print(f"Found course indicator: {indicator}")
                        return True
                except Exception as e:
                    if self.debug:
                        print(f"Error checking indicator {indicator}: {e}")
                    continue

            # Debug: show current URL
            current_url = self.main_page.url
            if self.debug:
                print(f"Current URL: {current_url}")
                print("No course indicators found - treating as course selection page")

            return False

        except Exception as e:
            print(f"Error in check_if_in_course: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def analyze_and_decide(self, context: str) -> Dict[str, Any]:
        """Analyze current screen and decide what action to take"""
        screenshot = await self.take_screenshot("analysis")

        prompt = f"""You are automating a JKO (Joint Knowledge Online) course website.
Analyze this screenshot and determine what action should be taken next.

Context: {context}

IMPORTANT: You must actively click buttons to progress. Do NOT use "read" action unless absolutely necessary.

The interface may have:
- Course selection page with "Launch" or "Resume" buttons - CLICK THESE to enter a course
- A "Start" button to begin the course - CLICK THIS
- "Next Lesson" button at the top to move to next lesson - CLICK THIS
- "Next Page" button to view more content in current lesson - CLICK THIS (must click through all pages before Next Lesson becomes available)
- "Continue" button to proceed - CLICK THIS
- "Suspend Lesson" to bookmark progress - SKIP THIS
- "Exit Course" to close - SKIP THIS unless course is complete
- Multiple choice questions with radio buttons or clickable options - SELECT AND SUBMIT
- A submit button for tests - CLICK THIS after selecting an answer
- Content pages with text and images that need to be reviewed - click Next/Continue

ACTION PRIORITY (in order):
1. If you see "Launch" or "Resume" button - CLICK IT to enter the course
2. If you see a "Start" button - CLICK IT to begin
3. If you see "Next Page" or "Continue" button - CLICK IT to progress
4. If you see "Next Lesson" button - CLICK IT to advance
5. If you see a multiple choice question - ANSWER IT
6. If you see a "Submit" button - CLICK IT
7. Only use "read" if there are no visible buttons and content is still loading

Respond ONLY with a JSON object (no markdown formatting, no code blocks) with this structure:
{{
    "action": "click|scroll|wait|answer_question|complete",
    "element": "description of what to click (if action is click)",
    "reasoning": "why you chose this action",
    "answer_index": 0 (only for answer_question action, 0-based index of the answer to select),
    "is_test": false (true if this appears to be a test/quiz question)
}}

Examples:
- If you see a "Launch" or "Resume" button: {{"action": "click", "element": "Launch button", "reasoning": "Need to launch the course"}}
- If you see a "Start" button: {{"action": "click", "element": "Start button", "reasoning": "Need to start the course"}}
- If you see a "Next Page" button: {{"action": "click", "element": "Next Page button", "reasoning": "Need to view all content"}}
- If you see a "Continue" button: {{"action": "click", "element": "Continue button", "reasoning": "Need to continue"}}
- If you see a "Next Lesson" button: {{"action": "click", "element": "Next Lesson button", "reasoning": "Completed current lesson"}}
- If you see a multiple choice question: {{"action": "answer_question", "element": "Question with options", "reasoning": "Need to answer test question", "answer_index": 2, "is_test": true}}
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
        # First try to find in main page, then in iframe if exists
        pages_to_check = [self.main_page]

        # Check if there's a course content iframe
        course_frame = await self.get_course_content_frame()
        if course_frame:
            pages_to_check.append(course_frame)

        # Try various selectors based on description keywords
        selectors = []
        desc_lower = description.lower()

        # Determine search keyword
        search_keyword = None
        if "launch" in desc_lower:
            search_keyword = "launch"
            selectors.extend([
                "button:has-text('Launch')",
                "a:has-text('Launch')",
                "input[value*='Launch']",
                "[onclick*='launch']",
                ".launch-button",
                "#launch",
                "button:text-is('Launch')",
                "a:text-is('Launch')"
            ])
        elif "resume" in desc_lower:
            search_keyword = "resume"
            selectors.extend([
                "button:has-text('Resume')",
                "a:has-text('Resume')",
                "input[value*='Resume']",
                "[onclick*='resume']",
                ".resume-button"
            ])
        elif "start" in desc_lower:
            search_keyword = "start"
            selectors.extend([
                "button:has-text('Start')",
                "a:has-text('Start')",
                "input[value*='Start']",
                "[onclick*='start']"
            ])
        elif "next page" in desc_lower:
            search_keyword = "next"
            selectors.extend([
                "button:has-text('Next Page')",
                "a:has-text('Next Page')",
                "input[value*='Next Page']",
                ".next-page",
                "#nextPage"
            ])
        elif "next lesson" in desc_lower:
            search_keyword = "next lesson"
            selectors.extend([
                "button:has-text('Next Lesson')",
                "a:has-text('Next Lesson')",
                "input[value*='Next Lesson']",
                ".next-lesson",
                "#nextLesson"
            ])
        elif "submit" in desc_lower:
            search_keyword = "submit"
            selectors.extend([
                "button:has-text('Submit')",
                "input[type='submit']",
                "button[type='submit']",
                "a:has-text('Submit')"
            ])
        elif "continue" in desc_lower:
            search_keyword = "continue"
            selectors.extend([
                "button:has-text('Continue')",
                "a:has-text('Continue')",
                "input[value*='Continue']"
            ])

        print(f"Searching for element: {description}")
        if search_keyword:
            print(f"Keyword: '{search_keyword}'")

        # Try each page (main page and iframe if exists)
        for page_idx, page in enumerate(pages_to_check):
            if page_idx == 1:
                print("Also searching in course content iframe...")

            # Try each selector
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        # Check if element is visible
                        is_visible = await element.is_visible()
                        if is_visible:
                            if self.debug:
                                print(f"Found element with selector: {selector}")
                            await element.click()
                            print(f"✓ Clicked element with selector: {selector}")
                            await asyncio.sleep(1)
                            return True
                except Exception as e:
                    if self.debug:
                        print(f"Selector {selector} failed: {e}")
                    continue

            # If specific selectors didn't work, try finding ALL buttons and links
            if page_idx == 0:
                print(f"Specific selectors failed, searching all buttons/links...")
            try:
                all_elements = await page.query_selector_all("button, a, input[type='button'], input[type='submit'], [role='button']")
                print(f"Found {len(all_elements)} total clickable elements")

                visible_count = 0
                for element in all_elements:
                    try:
                        is_visible = await element.is_visible()
                        if not is_visible:
                            continue

                        visible_count += 1
                        text = (await element.text_content() or "").strip()
                        value = await element.get_attribute("value") or ""
                        aria_label = await element.get_attribute("aria-label") or ""
                        title = await element.get_attribute("title") or ""

                        combined_text = f"{text} {value} {aria_label} {title}".lower()

                        if self.debug and search_keyword and search_keyword.lower() in combined_text:
                            print(f"  Found potential match: text='{text}', value='{value}'")

                        # Check if search keyword matches (case-insensitive)
                        if search_keyword and search_keyword.lower() in combined_text:
                            print(f"✓ Clicking element with text: '{text or value or aria_label}'")
                            await element.click()
                            await asyncio.sleep(1)
                            return True

                    except Exception as e:
                        if self.debug:
                            print(f"Error checking element: {e}")
                        continue

                print(f"Checked {visible_count} visible elements, none matched '{search_keyword}'")

                # List all visible button texts to help debug
                if visible_count > 0:
                    print(f"\nVisible buttons on page:")
                    button_count = 0
                    for element in all_elements:
                        try:
                            if await element.is_visible():
                                text = (await element.text_content() or "").strip()
                                if text:
                                    button_count += 1
                                    print(f"  {button_count}. '{text[:50]}...' " if len(text) > 50 else f"  {button_count}. '{text}'")
                                    if button_count >= 10:  # Limit output
                                        print(f"  ... and {visible_count - 10} more")
                                        break
                        except:
                            continue

            except Exception as e:
                print(f"Error in general button search: {e}")

        print(f"✗ Could not find element: {description}")
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

    async def wait_for_user_login(self):
        """Wait for user to manually log in"""
        print("\n" + "=" * 60)
        print("MANUAL LOGIN REQUIRED")
        print("=" * 60)
        print("Please log in to JKO in the browser window.")
        print("Once logged in, navigate to the course you want to automate.")
        print("Press Enter in this terminal when you're on the course page")
        print("and ready to start automation...")
        print("=" * 60 + "\n")

        # Wait for user confirmation
        await asyncio.get_event_loop().run_in_executor(None, input)

        # Take a screenshot to confirm
        await self.take_screenshot("ready_to_start")
        print("Starting automation...\n")

    async def detect_course_list(self) -> List[Dict[str, str]]:
        """Detect available courses on the page"""
        screenshot = await self.take_screenshot("course_detection")

        prompt = """Analyze this screenshot from JKO (Joint Knowledge Online).
If you see a list of available courses, extract them.
Look for course titles, course codes (like USA-AU-01), and clickable links.

Respond ONLY with a JSON object (no markdown) with this structure:
{
    "has_courses": true/false,
    "courses": [
        {"title": "Course Name", "code": "USA-AU-01", "element_text": "visible text to click"},
        ...
    ]
}

If no course list is visible, respond with:
{"has_courses": false, "courses": []}"""

        response = await self.ai_provider.analyze_screen(screenshot, prompt)

        if self.debug:
            print(f"\nCourse detection response:\n{response}\n")

        response = response.strip()
        if response.startswith("```"):
            lines = response.split('\n')
            response = '\n'.join([l for l in lines if not l.startswith('```')])
            response = response.strip()

        try:
            result = json.loads(response)
            return result.get("courses", [])
        except:
            return []

    async def select_course_from_list(self, course_index: int) -> bool:
        """Click on a course from the detected list"""
        courses = await self.detect_course_list()

        if not courses or course_index >= len(courses):
            print(f"Could not find course at index {course_index}")
            return False

        course = courses[course_index]
        print(f"Attempting to select: {course.get('title', 'Unknown')} ({course.get('code', 'N/A')})")

        element_text = course.get('element_text', course.get('title', ''))

        # Try to find and click the course link
        try:
            # Try various selectors
            selectors = [
                f"a:has-text('{element_text}')",
                f"*:has-text('{course.get('code', '')}')",
            ]

            for selector in selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        await self.wait_for_page_load()
                        print(f"Selected course successfully")
                        return True
                except:
                    continue

        except Exception as e:
            if self.debug:
                print(f"Error selecting course: {e}")

        return False

    async def run_course(self, start_url: str = "https://jkodirect.jten.mil/",
                        max_iterations: int = 500,
                        auto_login: bool = False):
        """Main loop to complete a course"""
        print(f"Starting JKO automation...")

        await self.start_browser()

        try:
            # Navigate to JKO home page
            print(f"Navigating to: {start_url}")
            await self.page.goto(start_url)
            await self.wait_for_page_load()

            # Set main page reference
            self.main_page = self.page

            # Wait for user to log in and navigate to course
            if not auto_login:
                await self.wait_for_user_login()

            iteration = 0
            consecutive_waits = 0
            max_consecutive_waits = 3

            print("\n🤖 AI is now in control...\n")

            in_course = False

            while iteration < max_iterations:
                iteration += 1
                print(f"\n--- Iteration {iteration} ---")

                # Check if we're in a course
                in_course = await self.check_if_in_course()

                if in_course:
                    course_frame = await self.get_course_content_frame()
                    if course_frame:
                        print("🎓 Inside course (will search both main page and iframe)")
                    else:
                        print("🎓 Inside course page")
                else:
                    print("📋 On course selection page")

                # Analyze current screen
                decision = await self.analyze_and_decide(
                    f"Iteration {iteration}, {'in course content' if in_course else 'on course selection page'}"
                )

                print(f"Action: {decision.get('action')}")
                print(f"Reasoning: {decision.get('reasoning')}")

                action = decision.get("action", "wait")

                if action == "complete":
                    print("\n✓ Course completed!")
                    break

                elif action == "click":
                    element_desc = decision.get("element", "")

                    # Avoid clicking Resume/Launch buttons if we're already in a course
                    if in_course and ("resume" in element_desc.lower() or "launch" in element_desc.lower()):
                        print(f"⚠ Skipping '{element_desc}' - we're already inside a course")
                        consecutive_waits += 1
                    else:
                        success = await self.find_and_click_element(element_desc)
                        if success:
                            await self.wait_for_page_load()
                            # Update main_page reference after navigation
                            self.main_page = self.page
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
                    # "Read" is discouraged - try to find and click common buttons instead
                    print("AI suggested 'read', but trying to find clickable buttons instead...")

                    # Try common buttons in priority order
                    # Skip Resume/Launch if we're already in a course
                    if in_course:
                        buttons_to_try = [
                            "Start button",
                            "Next Page button",
                            "Continue button",
                            "Next Lesson button"
                        ]
                    else:
                        buttons_to_try = [
                            "Launch button",
                            "Resume button",
                            "Start button",
                            "Next Page button",
                            "Continue button",
                            "Next Lesson button"
                        ]

                    clicked = False

                    for button_desc in buttons_to_try:
                        print(f"\nTrying to find: {button_desc}")
                        if await self.find_and_click_element(button_desc):
                            await self.wait_for_page_load()
                            clicked = True
                            break
                        print()  # Add spacing between attempts

                    if not clicked:
                        print("No buttons found, waiting...")
                        await asyncio.sleep(2)
                        consecutive_waits += 1
                    else:
                        consecutive_waits = 0

                else:  # wait
                    print("Waiting...")
                    await asyncio.sleep(2)
                    consecutive_waits += 1

                    if consecutive_waits >= max_consecutive_waits:
                        print("\n" + "="*60)
                        print("Too many consecutive waits!")
                        print("Aggressively trying to find buttons...")
                        print("="*60)

                        # Try all common buttons in priority order
                        # Skip Resume/Launch if we're already in a course
                        if in_course:
                            print("Already in course - skipping Resume/Launch buttons")
                            buttons_to_try = [
                                "Start button",
                                "Next Page button",
                                "Continue button",
                                "Next Lesson button"
                            ]
                        else:
                            buttons_to_try = [
                                "Launch button",
                                "Resume button",
                                "Start button",
                                "Next Page button",
                                "Continue button",
                                "Next Lesson button"
                            ]

                        clicked = False

                        for button_desc in buttons_to_try:
                            print(f"\nAttempt: {button_desc}")
                            if await self.find_and_click_element(button_desc):
                                await self.wait_for_page_load()
                                clicked = True
                                consecutive_waits = 0
                                break
                            print()  # Add spacing

                        if not clicked:
                            print("\n" + "="*60)
                            print("Still no buttons found, will keep trying...")
                            print("="*60)
                            consecutive_waits = 0  # Reset to avoid infinite loop

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
        description="Automate JKO course completion using AI vision",
        epilog="""
Examples:
  # Start at JKO home page, log in manually, then let AI take over
  python jko_course_automation.py

  # Start at specific URL (still requires manual login)
  python jko_course_automation.py --start-url "https://jkodirect.jten.mil/my/courses"

  # Use Ollama instead of Claude
  python jko_course_automation.py --ai-provider ollama

  # Enable debug mode to see detailed output
  python jko_course_automation.py --debug
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--start-url",
        default="https://jkodirect.jten.mil/",
        help="URL to start at (default: https://jkodirect.jten.mil/)"
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
        help="Run browser in headless mode (not recommended for login)"
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
    await automation.run_course(
        start_url=args.start_url,
        max_iterations=args.max_iterations,
        auto_login=False
    )


if __name__ == "__main__":
    asyncio.run(main())
