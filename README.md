# AI-Enhanced Sitemap Crawler for Documentation

This tool crawls sitemaps, extracts content from each URL, and converts the HTML to high-quality Markdown using a combination of Crawl4AI's scraping capabilities and Google Gemini AI's conversion intelligence.

## Features

- **Powerful Web Scraping**: Uses Crawl4AI to handle complex web page structures
- **AI-Enhanced Markdown Conversion**: Leverages Google Gemini AI to intelligently convert HTML to clean Markdown
- **Advanced Code Formatting**: Special processing for code blocks with language detection and proper formatting
- **Metadata-Rich Output**: YAML frontmatter with detailed metadata for better knowledge management
- **Structured Content**: Organizes content into hierarchical chunks for better consumption by LLMs
- **Integrated Workflow**: Run the entire process with a single command or step-by-step

## Setup

1. Install required dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your Google Gemini API key:

```
GEMINI_API_KEY=your_api_key_here
```

3. Optional: Configure environment variables for specific sitemaps:

```
SITEMAP_URL=https://example.com/sitemap.xml
```

## Usage

### Integrated Workflow (Recommended)

Run the complete scraping and conversion pipeline with a single command:

```bash
python integrated_workflow.py --sitemap https://docs.crawl4ai.com/sitemap.xml
```

This will:
1. Scrape all URLs in the sitemap using Crawl4AI
2. Save HTML content to CSV files in `scraped_pages/`
3. Convert HTML to enhanced markdown using Google Gemini AI
4. Save markdown files to `ai_markdown_pages/`

### Step-by-Step Approach

If you prefer more control, you can run each step separately:

1. **Scrape only**:
```bash
python agent.py
# Or with a specific sitemap:
python integrated_workflow.py --sitemap https://example.com/sitemap.xml --skip-convert
```

2. **Convert only**:
```bash
python converter_agent.py
# Or with a specific input directory:
python converter_agent.py --input scraped_pages/example.com_sitemap
# Or skip scraping in the integrated workflow:
python integrated_workflow.py --sitemap https://example.com/sitemap.xml --skip-scrape
```

### Streamlit App

The project also includes a Streamlit app for easy use:

```bash
streamlit run streamlit_app.py
```

## Output

The workflow produces two sets of output:

1. **HTML Content**: Raw HTML saved to CSV files in `scraped_pages/{domain}_sitemap/`
2. **Markdown Content**: AI-enhanced markdown saved to `ai_markdown_pages/{domain}_sitemap/`

Each markdown file includes:
- YAML frontmatter with metadata (URL, domain, date, code block counts, etc.)
- Original URL reference for attribution
- Clean, well-formatted content
- Code blocks with proper language tags and formatting

## How It Works

This tool combines two powerful approaches:

1. **Crawl4AI Scraping**: Uses AsyncWebCrawler to extract HTML content from web pages, handling JavaScript, CSS, and complex page structures.

2. **Google Gemini AI Conversion**: Processes the HTML content with advanced AI to generate high-quality markdown, with special emphasis on:
   - Preserving code structure and syntax
   - Detecting programming languages
   - Formatting code blocks properly
   - Maintaining document structure
   - Cleaning up unnecessary elements

## Code Block Enhancement

Special attention is given to code blocks:

- **Language Detection**: Intelligently detects programming languages from code patterns
- **Formatting Preservation**: Maintains indentation, spacing, and structure
- **Syntax Correction**: Fixes common spacing issues without altering functionality
- **Context-Aware Processing**: Uses documentation snippets as references 