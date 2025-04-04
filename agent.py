import os
import asyncio
import logging
import csv
from typing import List, Optional, Dict, Tuple
from pathlib import Path
import re
import datetime

# Ensure proper encoding for console output on Windows
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
import xml.etree.ElementTree as ET
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the output directories
HTML_DIR = "scraped_pages"
MD_DIR = "markdown_pages"

# Create the output directories if they don't exist
os.makedirs(HTML_DIR, exist_ok=True)
os.makedirs(MD_DIR, exist_ok=True)

def fetch_sitemap_urls(sitemap_url: str) -> List[str]:
    """Fetch and parse sitemap, return list of page URLs using requests."""
    urls = []
    try:
        response = requests.get(sitemap_url, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        root = ET.fromstring(response.content)
        # Namespace is important for parsing sitemaps
        namespace = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [url_el.text for url_el in root.findall('.//sm:loc', namespace)]
        logging.info(f"Fetched {len(urls)} URLs from sitemap: {sitemap_url}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching sitemap {sitemap_url}: {e}")
    except ET.ParseError as e:
        logging.error(f"Error parsing sitemap XML {sitemap_url}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching sitemap {sitemap_url}: {e}")
    return urls

async def scrape_page(url: str, output_dir: str, crawler: AsyncWebCrawler):
    """Scrape a single page and save its HTML content to a CSV file."""
    logging.info(f"Processing URL: {url}")
    
    try:
        # Configure the crawler to get clean HTML
        config = CrawlerRunConfig(
            # No markdown generation specified - we'll get raw HTML only
        )
        
        # Crawl the page
        result = await crawler.arun(url=url, config=config)
        
        if not result.success:
            logging.error(f"Failed to crawl {url}: {result.error_message}")
            return

        # Get the HTML content
        html_content = result.html
        
        # Create a safe filename from URL
        safe_filename = url.replace('https://', '').replace('http://', '')\
                           .replace('/', '_').replace(':', '_')\
                           .replace('?', '_').replace('&', '_')\
                           .replace('.', '_')
        
        if not safe_filename:
            safe_filename = f"page_{hash(url)}"  # Fallback for weird URLs
        
        # Save HTML content to CSV for later processing by converter_agent
        csv_file_path = os.path.join(output_dir, f"{safe_filename}.csv")
        
        # Save the HTML with URL to CSV for the converter agent
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['url', 'html_content']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            writer.writerow({
                'url': url,
                'html_content': html_content
            })
        
        logging.info(f"Saved HTML content from {url} to {csv_file_path} for AI conversion")

    except Exception as e:
        logging.error(f"Error processing {url}: {str(e)}")

async def crawl_sitemap(sitemap_url: str, output_dir: str):
    """Crawl all URLs in a sitemap and save HTML content to CSV files."""
    urls = fetch_sitemap_urls(sitemap_url)

    if not urls:
        logging.error(f"No URLs found in sitemap: {sitemap_url}")
        return

    # Create a domain-specific output directory
    domain = sitemap_url.replace('https://', '').replace('http://', '').split('/')[0]
    domain_output_dir = os.path.join(output_dir, f"{domain}_sitemap")
    os.makedirs(domain_output_dir, exist_ok=True)
    
    logging.info(f"Will save HTML content to: {domain_output_dir}")
    
    # Use a single crawler instance for all tasks
    async with AsyncWebCrawler() as crawler:
        # Process URLs in batches to avoid overwhelming the system
        batch_size = 5  # Adjust based on system capabilities
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i+batch_size]
            tasks = [scrape_page(url, domain_output_dir, crawler) for url in batch]
            await asyncio.gather(*tasks)

    logging.info(f"Completed processing {len(urls)} URLs from {sitemap_url}")
    return domain_output_dir

async def main(sitemap_url: str = None):
    """Main entry point for the crawler."""
    # Use provided parameters or defaults
    if not sitemap_url:
        sitemap_url = "https://docs.crawl4ai.com/sitemap.xml"  # Default example
    
    # Crawl the sitemap and save HTML content
    output_dir = await crawl_sitemap(sitemap_url, HTML_DIR)
    
    if output_dir:
        logging.info(f"Scraping completed. HTML content saved to {output_dir}.")
        logging.info(f"Run converter_agent.py next to convert HTML to enhanced markdown.")

if __name__ == "__main__":
    # Can be run from command line:
    # python agent.py
    # Or with specific parameters using environment variables
    import os
    sitemap_url = os.getenv("SITEMAP_URL")
    
    asyncio.run(main(sitemap_url))