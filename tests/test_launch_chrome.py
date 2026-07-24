"""
Launches Google Chrome on an Android emulator via Appium using a native
Android VIEW intent pointed directly at deviceinfo.me, then takes a plain
device screenshot.

Deliberately avoids Appium's WebView/browser automation mode
("browserName": "Chrome"), which requires a Chromedriver binary that
exactly matches the Chrome build baked into the emulator image (often an
old, fixed version on AOSP system images) and frequently fails with
"No Chromedriver found that can automate Chrome 'X.Y.Z'". Launching via
intent + taking a native screenshot needs no Chromedriver at all.

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
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, WebDriverException

APPIUM_SERVER_URL = "http://127.0.0.1:4723/wd/hub"
TARGET_URL = "https://www.deviceinfo.me"
OUTPUT_DIR = "artifacts"

CHROME_CAPABILITIES = {
    "platformName": "Android",
    "automationName": "UiAutomator2",
    "deviceName": "Android Emulator",
    "appPackage": "com.android.chrome",
    "appActivity": "com.google.android.apps.chrome.Main",
    # Launch Chrome directly to the target URL via a native VIEW intent,
    # instead of opening the app and driving the address bar by hand.
    "intentAction": "android.intent.action.VIEW",
    "optionalIntentArguments": f'-d "{TARGET_URL}"',
    "noReset": True,
    "autoGrantPermissions": True,
    "newCommandTimeout": 180,
}

# Text that can appear on Chrome's first-run screens on a fresh AVD.
# We try to dismiss these if present; if they're not there, we just move on.
DISMISS_BUTTON_TEXTS = ["Accept & continue", "No thanks", "Got it", "OK"]


def try_dismiss_first_run_dialogs(driver):
    for text in DISMISS_BUTTON_TEXTS:
        try:
            el = driver.find_element(
                AppiumBy.XPATH, f'//*[@text="{text}"]'
            )
            el.click()
            print(f"Dismissed dialog button: '{text}'")
            time.sleep(2)
        except NoSuchElementException:
            pass


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    options = UiAutomator2Options().load_capabilities(CHROME_CAPABILITIES)

    driver = None
    try:
        print(f"Connecting to Appium server and launching Chrome -> {TARGET_URL} ...")
        driver = webdriver.Remote(APPIUM_SERVER_URL, options=options)

        # Save the full session capabilities Appium/UiAutomator2 reports
        # back — includes the real device model and Android version.
        caps_path = os.path.join(OUTPUT_DIR, "appium_session_capabilities.json")
        with open(caps_path, "w") as f:
            json.dump(dict(driver.capabilities), f, indent=2, default=str)
        print(f"Saved session capabilities to {caps_path}")

        # Let Chrome finish launching and rendering the page.
        time.sleep(6)
        try_dismiss_first_run_dialogs(driver)
        time.sleep(8)

        current_package = driver.current_package
        print(f"Foreground package: {current_package}")

        # Best-effort read of the address bar text, just for a log line —
        # not required for the screenshot itself.
        try:
            url_bar = driver.find_element(AppiumBy.ID, "com.android.chrome:id/url_bar")
            print(f"Address bar shows: {url_bar.text}")
        except NoSuchElementException:
            print("Address bar element not found (non-fatal); continuing.")

        screenshot_path = os.path.join(OUTPUT_DIR, "deviceinfo_screenshot.png")
        driver.save_screenshot(screenshot_path)
        print(f"Saved screenshot to {screenshot_path}")

        if current_package != "com.android.chrome":
            print("FAILED: Chrome is not the foreground app.")
            return 1

        print("SUCCESS: Chrome launched to deviceinfo.me and screenshot was captured.")
        return 0

    except WebDriverException as exc:
        print(f"FAILED: WebDriver error while driving Chrome: {exc}")
        return 1

    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    sys.exit(main())
