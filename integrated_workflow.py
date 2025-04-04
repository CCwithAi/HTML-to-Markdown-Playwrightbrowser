#!/usr/bin/env python3
"""
Integrated workflow script for scraping web content and converting to high-quality markdown.
This combines Crawl4AI's powerful scraping with Gemini AI's conversion capabilities.
"""

import os
import argparse
import asyncio
import logging
import sys
import subprocess
from pathlib import Path
import time
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("integrated_workflow.log", mode="a")
    ]
)

# Function to check if Playwright browsers are installed
def check_playwright_browsers():
    try:
        # Check if the Playwright browser directory exists
        user_home = os.path.expanduser("~")
        playwright_dir = os.path.join(user_home, "AppData", "Local", "ms-playwright")
        
        if not os.path.exists(playwright_dir):
            return False
            
        # Check if there's at least one browser directory with an executable
        chromium_dirs = list(Path(playwright_dir).glob("chromium-*"))
        if not chromium_dirs:
            return False
            
        # Check for the chrome executable in the latest chromium directory
        latest_chromium = sorted(chromium_dirs)[-1] if chromium_dirs else None
        if latest_chromium:
            chrome_exe = latest_chromium / "chrome-win" / "chrome.exe"
            return chrome_exe.exists()
            
        return False
    except Exception:
        return False

# Function to install Playwright browsers
def install_playwright_browsers():
    try:
        logging.info("Installing Playwright browsers...")
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logging.info("Playwright browsers installed successfully")
            return True
        else:
            logging.error(f"Failed to install Playwright browsers: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Error installing Playwright browsers: {e}")
        return False

# Import our custom modules
import agent  # The scraper
import converter_agent  # The AI converter

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Integrated workflow for scraping web content and converting to high-quality markdown."
    )
    parser.add_argument(
        "--sitemap",
        type=str,
        help="URL of the sitemap to scrape (e.g., https://docs.crawl4ai.com/sitemap.xml)",
        required=True
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip the scraping step and only run the conversion on existing CSV files"
    )
    parser.add_argument(
        "--skip-convert",
        action="store_true",
        help="Skip the conversion step and only run the scraping to generate CSV files"
    )
    parser.add_argument(
        "--install-playwright",
        action="store_true",
        help="Install Playwright browsers if missing"
    )
    return parser.parse_args()

async def run_scraper(sitemap_url: str) -> Optional[str]:
    """Run the scraper to extract HTML content from the sitemap URLs."""
    logging.info(f"Starting web scraping process for sitemap: {sitemap_url}")
    
    # Check for Playwright browsers before running
    if not check_playwright_browsers():
        logging.warning("Playwright browsers not installed. These are required for web scraping.")
        try:
            # Try to install playwright browsers
            if install_playwright_browsers():
                logging.info("Successfully installed Playwright browsers")
            else:
                logging.error("Failed to install Playwright browsers. Please install manually using: python -m playwright install chromium")
                return None
        except Exception as e:
            logging.error(f"Error during Playwright browser installation: {e}")
            return None
    
    try:
        # Use the agent.py module to run the scraper
        output_dir = await agent.main(sitemap_url)
        return output_dir
    except Exception as e:
        logging.error(f"Error during scraping process: {e}")
        return None

def run_converter(input_dir: Optional[str] = None):
    """Run the converter to transform HTML content to enhanced markdown."""
    logging.info(f"Starting AI conversion process for directory: {input_dir or 'all directories'}")
    try:
        # Use the converter_agent.py module to convert HTML to markdown
        converter_agent.process_csv_files(input_dir)
    except Exception as e:
        logging.error(f"Error during conversion process: {e}")

async def main():
    """Main workflow function that orchestrates the scraping and conversion process."""
    args = parse_args()
    sitemap_url = args.sitemap
    
    # Check if we should install Playwright browsers
    if args.install_playwright and not check_playwright_browsers():
        install_playwright_browsers()
    
    output_dir = None
    
    # Step 1: Scrape content if not skipped
    if not args.skip_scrape:
        output_dir = await run_scraper(sitemap_url)
        if not output_dir:
            logging.error("Scraping process failed or produced no output. Exiting.")
            if not args.skip_convert:
                # Check if we should proceed with conversion anyway
                proceed = input("Scraping failed. Do you still want to proceed with conversion? (y/n): ")
                if proceed.lower() != 'y':
                    return
    
    # Add a small delay between steps
    time.sleep(1)
    
    # Step 2: Convert content if not skipped
    if not args.skip_convert:
        run_converter(output_dir)
    
    logging.info("Integrated workflow completed successfully!")
    
    # Provide a summary
    if not args.skip_scrape and not args.skip_convert:
        domain = sitemap_url.replace('https://', '').replace('http://', '').split('/')[0]
        markdown_dir = os.path.join("ai_markdown_pages", f"{domain}_sitemap")
        logging.info(f"HTML content saved to: {output_dir}")
        logging.info(f"Markdown content saved to: {markdown_dir}")
    elif not args.skip_scrape:
        logging.info(f"HTML content saved to: {output_dir}")
    elif not args.skip_convert:
        logging.info("Markdown conversion completed on existing CSV files")

if __name__ == "__main__":
    asyncio.run(main()) 