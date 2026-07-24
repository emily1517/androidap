"""
Launches Google Chrome on an Android emulator via Appium, navigates to
https://www.deviceinfo.me, and saves a screenshot plus the raw Appium
session capabilities (which include the real device model / Android
version reported by the emulator) so they can be inspected afterwards.

Run against a locally started Appium server:
    appium --base-path /wd/hub &
    python tests/test_launch_chrome.py
"""

import json
import os
import sys
import time

from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.common.exceptions import WebDriverException

APPIUM_SERVER_URL = "http://127.0.0.1:4723/wd/hub"
TARGET_URL = "https://www.deviceinfo.me"
OUTPUT_DIR = "artifacts"

# Using "browserName": "Chrome" (instead of appPackage/appActivity) tells
# Appium/UiAutomator2 to drive Chrome as a real browser session, so
# driver.get(url) works and Appium handles Chrome's first-run dialogs
# automatically.
CHROME_CAPABILITIES = {
    "platformName": "Android",
    "automationName": "UiAutomator2",
    "deviceName": "Android Emulator",
    "browserName": "Chrome",
    "newCommandTimeout": 180,
    "chromedriverAutodownload": True,
}


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    options = UiAutomator2Options().load_capabilities(CHROME_CAPABILITIES)

    driver = None
    try:
        print("Connecting to Appium server and launching Chrome...")
        driver = webdriver.Remote(APPIUM_SERVER_URL, options=options)

        # Save the full session capabilities Appium/UiAutomator2 reports
        # back — this includes the real device model, Android (platform)
        # version, and API level of the emulator that was actually used.
        caps_path = os.path.join(OUTPUT_DIR, "appium_session_capabilities.json")
        with open(caps_path, "w") as f:
            json.dump(dict(driver.capabilities), f, indent=2, default=str)
        print(f"Saved session capabilities to {caps_path}")
        print(f"Device model reported by Appium: {driver.capabilities.get('deviceModel')}")
        print(f"Android (platform) version: {driver.capabilities.get('platformVersion')}")

        print(f"Navigating to {TARGET_URL} ...")
        driver.get(TARGET_URL)

        # Let the page fully render (deviceinfo.me runs client-side JS to
        # detect and display the device details).
        time.sleep(8)

        screenshot_path = os.path.join(OUTPUT_DIR, "deviceinfo_screenshot.png")
        driver.save_screenshot(screenshot_path)
        print(f"Saved screenshot to {screenshot_path}")

        current_url = driver.current_url
        print(f"Current URL after navigation: {current_url}")

        if "deviceinfo" not in current_url:
            print("FAILED: Chrome did not navigate to deviceinfo.me as expected.")
            return 1

        print("SUCCESS: Chrome launched, opened deviceinfo.me, and screenshot was captured.")
        return 0

    except WebDriverException as exc:
        print(f"FAILED: WebDriver error while driving Chrome: {exc}")
        return 1

    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    sys.exit(main())
