#!/usr/bin/env python3
"""
Server compatibility helper utilities for running scrapers on headless servers.
Provides Xvfb display management and browser setup utilities.
"""

import os
import subprocess
import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class XvfbDisplay:
    """
    Context manager for Xvfb virtual display.

    Usage:
        with XvfbDisplay() as display:
            # Run Selenium code here
            driver = webdriver.Firefox()
    """

    def __init__(self, width=1920, height=1080, colordepth=24):
        self.width = width
        self.height = height
        self.colordepth = colordepth
        self.proc = None
        self.display = None

    def __enter__(self):
        """Start Xvfb virtual display."""
        # Find available display number
        display_num = self._find_available_display()
        self.display = f":{display_num}"

        cmd = [
            "Xvfb",
            self.display,
            "-screen", "0", f"{self.width}x{self.height}x{self.colordepth}",
            "-ac",  # Disable access control
            "+extension", "GLX",  # Enable OpenGL extension
            "+render",  # Enable render extension
            "-noreset"
        ]

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Set DISPLAY environment variable
            os.environ["DISPLAY"] = self.display

            logger.info(f"Started Xvfb on display {self.display}")

            # Give Xvfb time to start
            import time
            time.sleep(1)

            return self

        except FileNotFoundError:
            logger.error("Xvfb not found. Install with: sudo apt-get install xvfb")
            raise
        except Exception as e:
            logger.error(f"Failed to start Xvfb: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop Xvfb virtual display."""
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            logger.info(f"Stopped Xvfb on display {self.display}")

        # Clean up DISPLAY variable
        if "DISPLAY" in os.environ:
            del os.environ["DISPLAY"]

    @staticmethod
    def _find_available_display(start=99):
        """Find an available display number."""
        for i in range(start, start + 100):
            lock_file = f"/tmp/.X{i}-lock"
            if not os.path.exists(lock_file):
                return i
        raise RuntimeError("No available display found")


def is_xvfb_available() -> bool:
    """Check if Xvfb is installed on the system."""
    try:
        result = subprocess.run(
            ["which", "Xvfb"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def is_firefox_available() -> bool:
    """Check if Firefox is installed on the system."""
    try:
        result = subprocess.run(
            ["which", "firefox"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def is_geckodriver_available() -> bool:
    """Check if geckodriver is installed on the system."""
    try:
        result = subprocess.run(
            ["which", "geckodriver"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def check_server_requirements() -> dict:
    """
    Check all server requirements for running scrapers.

    Returns:
        Dictionary with requirement check results
    """
    results = {
        "xvfb": is_xvfb_available(),
        "firefox": is_firefox_available(),
        "geckodriver": is_geckodriver_available(),
    }

    results["all_requirements_met"] = all(results.values())

    return results


def print_server_status():
    """Print server requirements status to console."""
    results = check_server_requirements()

    print("\n" + "="*60)
    print("SERVER REQUIREMENTS CHECK")
    print("="*60)

    status_symbol = lambda x: "✓" if x else "✗"

    print(f"{status_symbol(results['firefox'])} Firefox: {'Installed' if results['firefox'] else 'NOT FOUND'}")
    print(f"{status_symbol(results['geckodriver'])} geckodriver: {'Installed' if results['geckodriver'] else 'NOT FOUND'}")
    print(f"{status_symbol(results['xvfb'])} Xvfb: {'Installed' if results['xvfb'] else 'NOT FOUND (recommended)'}")

    print("="*60)

    if not results['firefox']:
        print("\nInstall Firefox:")
        print("  Ubuntu/Debian: sudo apt-get install firefox")
        print("  or Firefox ESR: sudo apt-get install firefox-esr")

    if not results['geckodriver']:
        print("\nInstall geckodriver:")
        print("  1. Download from: https://github.com/mozilla/geckodriver/releases")
        print("  2. Extract and move to /usr/local/bin/")
        print("  3. Make executable: chmod +x /usr/local/bin/geckodriver")

    if not results['xvfb']:
        print("\nInstall Xvfb (recommended for stability):")
        print("  Ubuntu/Debian: sudo apt-get install xvfb")

    print()

    return results['all_requirements_met']


@contextmanager
def get_virtual_display(auto_detect: bool = True):
    """
    Context manager that provides virtual display if needed.

    Args:
        auto_detect: If True, automatically use Xvfb if available

    Usage:
        with get_virtual_display() as display:
            driver = webdriver.Firefox()
    """
    use_xvfb = auto_detect and is_xvfb_available()

    if use_xvfb:
        with XvfbDisplay() as display:
            yield display
    else:
        # No virtual display - yield None
        yield None


if __name__ == "__main__":
    # Check and print server status
    all_ok = print_server_status()

    if all_ok:
        print("✓ All requirements met!")

        # Test Xvfb if available
        if is_xvfb_available():
            print("\nTesting Xvfb...")
            try:
                with XvfbDisplay() as display:
                    print(f"✓ Xvfb test successful (DISPLAY={display.display})")
            except Exception as e:
                print(f"✗ Xvfb test failed: {e}")
    else:
        print("✗ Some requirements are missing. Please install them before running scrapers.")
        exit(1)
