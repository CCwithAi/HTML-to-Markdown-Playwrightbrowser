import argparse
import asyncio
import csv
import json
import logging
import os
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl
from crawl4ai import AsyncWebCrawler


# Load environment variables from .env file
load_dotenv()


# Define the Pydantic model for the scraped page data
class ScrapedPageData(BaseModel):
    url: HttpUrl
    content: str


async def scrape_sitemap_async(sitemap_url: str) -> list:
    """
    Instantiate AsyncWebCrawler, scrape the sitemap, and return a list of ScrapedPageData objects.
    """
    scraped_pages_data = []
    try:
        logging.info(f"Instantiating AsyncWebCrawler...")
        # Configure the crawler - adjust parameters as needed based on crawl4ai docs
        # Example: Setting a specific extraction strategy if needed
        # crawler_config = {"extractor": {"strategy": "html"}} # Example config
        async with AsyncWebCrawler(verbose=True) as crawler:
            logging.info(f"Starting sitemap scrape for {sitemap_url} using crawl4ai library...")
            # Assuming arun returns an object with scraped data.
            # The exact structure depends on crawl4ai version and configuration.
            # Common patterns: result.data, result.pages, or the result itself might be iterable.
            # We expect arun to return a CrawlResultContainer object.
            result = await crawler.arun(url=sitemap_url)

            # Check if the result has the 'results' attribute and it's a list
            if result and hasattr(result, 'results') and isinstance(result.results, list):
                logging.info(f"Scraping returned {len(result.results)} items. Processing...")
                for item in result.results: # Iterate over result.results
                    try:
                        # Extract URL and content using .get() for safety, assuming item is a dict
                        page_url = item.get("url")
                        # Prefer 'content', fallback to 'markdown', default to empty string
                        page_content = item.get("content", item.get("markdown", ""))

                        if page_url and page_content:
                            # Validate and create Pydantic model instance
                            scraped_pages_data.append(ScrapedPageData(url=str(page_url), content=str(page_content)))
                        else:
                            logging.warning(f"Skipping item due to missing URL or content: {item}")
                    except Exception as p_err:
                        logging.error(f"Pydantic validation or processing error for item {item}: {p_err}")
                logging.info(f"Successfully processed {len(scraped_pages_data)} pages.")
            elif result:
                 logging.warning(f"Scraping completed, but result.results is not a list or not found. Result type: {type(result)}. Attributes: {getattr(result, '__dict__', 'N/A')}")
            else:
                logging.warning("Scraping completed but the result object was empty or None.")

    except Exception as e:
        logging.error(f"Error during scraping or processing: {e}", exc_info=True)

    return scraped_pages_data


import re # Need re for sanitizing filenames

def sanitize_filename(url_str: str) -> str:
    """Sanitize a URL string to be used as a filename."""
    # Remove scheme (http, https)
    sanitized = re.sub(r'^https?://', '', url_str)
    # Replace common invalid characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', sanitized)
    # Replace multiple underscores with a single one
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores/periods
    sanitized = sanitized.strip('_.')
    # Limit length (optional, but good practice)
    return sanitized[:100] # Limit filename length

def save_output(data: list, output_dir: str, output_format: str):
    """
    Save the list of ScrapedPageData objects to files in the specified directory
    and format (csv, json, or markdown).
    """
    if not data:
        logging.warning("No data to save.")
        return

    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"Ensured output directory exists: '{output_dir}'")

        if output_format == "csv":
            output_file = os.path.join(output_dir, "scraped_data.csv")
            logging.info(f"Attempting to save {len(data)} records to CSV: '{output_file}'...")
            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ScrapedPageData.model_fields.keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for entry in data:
                    writer.writerow(entry.model_dump())
            logging.info(f"Successfully saved CSV output to '{output_file}'.")

        elif output_format == "json":
            output_file = os.path.join(output_dir, "scraped_data.json")
            logging.info(f"Attempting to save {len(data)} records to JSON: '{output_file}'...")
            with open(output_file, "w", encoding="utf-8") as jsonfile:
                json.dump([entry.model_dump() for entry in data], jsonfile, indent=2, ensure_ascii=False)
            logging.info(f"Successfully saved JSON output to '{output_file}'.")

        elif output_format == "markdown":
            logging.info(f"Attempting to save {len(data)} records as individual Markdown files in '{output_dir}'...")
            saved_count = 0
            for entry in data:
                # Create a filename from the URL
                filename_base = sanitize_filename(str(entry.url))
                output_file = os.path.join(output_dir, f"{filename_base}.md")
                try:
                    with open(output_file, "w", encoding="utf-8") as mdfile:
                        mdfile.write(f"# Content from: {entry.url}\n\n") # Add a header
                        mdfile.write(entry.content)
                    saved_count += 1
                except Exception as file_e:
                    logging.error(f"Error saving Markdown file '{output_file}' for URL {entry.url}: {file_e}")
            logging.info(f"Successfully saved {saved_count} Markdown files to '{output_dir}'.")

    except Exception as e:
        logging.error(f"Error during saving output to directory '{output_dir}': {e}", exc_info=True)


def parse_arguments():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Scrape a sitemap using crawl4ai and save results."
    )
    parser.add_argument(
        "--sitemap",
        type=str,
        default="https://docs.crawl4ai.com/sitemap.xml",
        help="URL of the sitemap to scrape.",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["csv", "json", "markdown"], # Add markdown option
        default="csv",
        help="Output format (csv, json, or markdown).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output_data", # Changed default name
        help="Directory to save the output files.", # Changed help text
    )
    return parser.parse_args()


async def main():
    # Set up basic logging configuration.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    args = parse_arguments()

    # Scrape the sitemap using the async function
    # Scrape the sitemap using the async function
    # This now returns a list of ScrapedPageData objects if successful
    scraped_data = await scrape_sitemap_async(args.sitemap)

    # Save the structured data to the output directory/files
    save_output(scraped_data, args.output, args.format)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())