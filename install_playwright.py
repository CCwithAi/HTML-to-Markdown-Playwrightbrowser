#!/usr/bin/env python3
"""
Simple script to install Playwright browsers required for Crawl4AI.
Run this if you encounter errors related to missing Playwright browsers.
"""

import sys
import subprocess
import os

def install_playwright_browsers():
    """Install Playwright browsers (primarily Chromium)."""
    print("Installing Playwright browsers (may take a minute)...")
    try:
        # First check if playwright is installed
        try:
            import playwright
            print("Playwright package is installed.")
        except ImportError:
            print("Playwright package is not installed. Installing...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "playwright"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"Failed to install Playwright: {result.stderr}")
                return False
            print("Playwright package installed successfully.")
            
        # Now install the browsers
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Playwright browsers installed successfully!")
            return True
        else:
            print(f"❌ Failed to install browsers: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error during installation: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Playwright Browser Installer")
    print("=" * 60)
    print("This script will install the Chromium browser required for Crawl4AI.")
    print("=" * 60)
    
    if install_playwright_browsers():
        print("\nInstallation completed successfully!")
        print("You can now run the integrated workflow or Streamlit app.")
    else:
        print("\nInstallation failed.")
        print("Please try running this command manually:")
        print("python -m playwright install chromium")
    
    print("\nPress Enter to exit...", end="")
    input() 