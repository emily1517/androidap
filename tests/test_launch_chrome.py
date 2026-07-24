"""
Launches Google Chrome on an Android emulator via Appium, navigates to
deviceinfo.me, and takes a plain device screenshot.

Two things this deliberately avoids, based on real failures seen in CI:

1. Appium's WebView/browser automation mode ("browserName": "Chrome" +
   driver.get(url)) requires a Chromedriver binary that exactly matches
   the Chrome build baked into the emulator image. AOSP system images
   often ship a fixed, old Chrome version with no matching Chromedriver
   available, causing "No Chromedriver found that can automate Chrome
   'X.Y.Z'".

2. Launching by naming Chrome's exact component
   (appPackage=com.android.chrome, appActivity=com.google.android.apps.
   chrome.Main) is brittle — that activity alias doesn't exist on every
   Chrome build/emulator image, and when it fails to resolve, `am start`
   silently drops back to the home screen with no error.

Instead: start the Appium session without auto-launching any app
(autoLaunch=False), then fire a generic VIEW intent with just the target
URL and no component name — the same as running
`adb shell am start -a android.intent.action.VIEW -d <url>` — so Android
resolves the default browser (Chrome) itself. No Chromedriver, no
hardcoded activity name.

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
CHROME_PACKAGE = "com.android.chrome"

SESSION_CAPABILITIES = {
    "platformName": "Android",
    "automationName": "UiAutomator2",
    "deviceName": "Android Emulator",
    # Don't auto-launch any app on session start — we launch the URL
    # ourselves via a generic intent right after, letting Android pick
    # the default browser instead of us guessing its component name.
    "autoLaunch": False,
    "noReset": True,
    "autoGrantPermissions": True,
    "newCommandTimeout": 180,
}

# Text that can appear on Chrome's first-run screens on a fresh AVD, or
# on a "choose a browser" dialog if more than one app can handle the URL.
DISMISS_BUTTON_TEXTS = ["Accept & continue", "No thanks", "Got it", "OK", "Chrome", "Just once"]


def try_dismiss_dialogs(driver):
    for text in DISMISS_BUTTON_TEXTS:
        try:
            el = driver.find_element(AppiumBy.XPATH, f'//*[@text="{text}"]')
            el.click()
            print(f"Dismissed dialog button: '{text}'")
            time.sleep(2)
        except NoSuchElementException:
            pass


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    options = UiAutomator2Options().load_capabilities(SESSION_CAPABILITIES)

    driver = None
    try:
        print("Connecting to Appium server (no app auto-launch)...")
        driver = webdriver.Remote(APPIUM_SERVER_URL, options=options)

        caps_path = os.path.join(OUTPUT_DIR, "appium_session_capabilities.json")
        with open(caps_path, "w") as f:
            json.dump(dict(driver.capabilities), f, indent=2, default=str)
        print(f"Saved session capabilities to {caps_path}")

        print(f"Firing VIEW intent for {TARGET_URL} (no component name)...")
        driver.execute_script(
            "mobile: startActivity",
            {
                "intentAction": "android.intent.action.VIEW",
                "optionalIntentArguments": f'-d "{TARGET_URL}"',
            },
        )

        time.sleep(6)
        try_dismiss_dialogs(driver)
        time.sleep(8)

        current_package = driver.current_package
        print(f"Foreground package: {current_package}")

        try:
            url_bar = driver.find_element(AppiumBy.ID, f"{CHROME_PACKAGE}:id/url_bar")
            print(f"Address bar shows: {url_bar.text}")
        except NoSuchElementException:
            print("Address bar element not found (non-fatal); continuing.")

        screenshot_path = os.path.join(OUTPUT_DIR, "deviceinfo_screenshot.png")
        driver.save_screenshot(screenshot_path)
        print(f"Saved screenshot to {screenshot_path}")

        if current_package != CHROME_PACKAGE:
            print(f"FAILED: expected foreground app '{CHROME_PACKAGE}', got '{current_package}'.")
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
