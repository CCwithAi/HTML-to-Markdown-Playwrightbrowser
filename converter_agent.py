import os
import csv
import google.generativeai as genai
import logging
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
import time
import re
from typing import List, Tuple, Dict, Optional
import datetime
import glob
import json

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Use GEMINI_API_KEY from .env

if not GEMINI_API_KEY: # Check the correct variable
    logging.error("GEMINI_API_KEY not found in .env file. Please add it.") # Update error message
    exit(1)

# Configure the Google Generative AI client
try:
    genai.configure(api_key=GEMINI_API_KEY) # Use the loaded GEMINI_API_KEY
    # Using gemini-2.0-flash as it's generally faster and cheaper for bulk tasks
    model = genai.GenerativeModel('gemini-2.0-flash')
    logging.info("Google Generative AI client configured successfully.")
except Exception as e:
    logging.error(f"Failed to configure Google Generative AI client: {e}")
    exit(1)

# Define input and output directories relative to the script location
SCRIPT_DIR = Path(__file__).parent
CSV_DIR = SCRIPT_DIR / "scraped_pages"
MD_DIR = SCRIPT_DIR / "ai_markdown_pages"

# Create the output directory if it doesn't exist
MD_DIR.mkdir(exist_ok=True)
logging.info(f"Output directory '{MD_DIR}' ensured.")

# Define Pydantic model for reading CSV data
class PageData(BaseModel):
    url: str
    html_content: str

# Cache for documentation snippets to improve code conversion
DOCS_CACHE = {}

def load_documentation_snippets():
    """Load code examples from Crawl4AI documentation for reference."""
    logging.info("Loading documentation snippets for reference...")
    # Check if we have crawl4ai documentation in the markdown_pages directory
    doc_paths = []
    for path in Path("markdown_pages").glob("**/*crawl4ai*"):
        if path.is_dir():
            doc_paths.extend(path.glob("**/*.md"))
    
    code_snippets = {}
    for doc_file in doc_paths:
        try:
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract all code blocks
                code_blocks = re.findall(r'```([^\n]*)\n(.*?)\n```', content, re.DOTALL)
                if code_blocks:
                    code_snippets[str(doc_file)] = code_blocks
        except Exception as e:
            logging.warning(f"Error reading documentation file {doc_file}: {e}")
    
    logging.info(f"Loaded {sum(len(blocks) for blocks in code_snippets.values())} code snippets from {len(code_snippets)} documentation files")
    return code_snippets

# --- Code block formatting functions ---
def detect_code_language(code_text: str, language_hint: Optional[str] = None, url: str = None) -> str:
    """
    Detect programming language from code content with enhanced accuracy.
    
    Args:
        code_text: The code text to analyze
        language_hint: Optional hint about the language from markdown
        url: The source URL to provide context (like docs.crawl4ai.com indicates Python)
        
    Returns:
        Detected language identifier (python, javascript, etc.) or text
    """
    # If we have a hint and it's not an empty string, use it
    if language_hint and language_hint.strip() and language_hint.strip().lower() != 'text':
        return language_hint.strip().lower()
    
    # Context-based detection from URL
    if url and any(domain in url for domain in ['crawl4ai.com', 'pydantic.dev', 'github.io/langgraph']):
        # These domains primarily contain Python code
        if re.search(r'import|def\s+\w+|class\s+\w+|async\s+def|await|with\s+|try:|except:', code_text):
            return "python"
    
    # Enhanced pattern-based detection
    # Python
    if re.search(r'import\s+\w+|from\s+\w+\s+import|def\s+\w+\s*\(|class\s+\w+|async\s+def|@\w+|await\s+|with\s+|if\s+__name__\s*==\s*[\'"]__main__[\'"]', code_text, re.IGNORECASE):
        return "python"
    # JavaScript/TypeScript
    elif re.search(r'function\s+\w+\s*\(|\w+\s*=>\s*[\{\(]|const\s+\w+\s*=|let\s+\w+\s*=|var\s+\w+\s*=|import\s+.*from\s+[\'"]|export\s+|class\s+\w+\s*\{\s*constructor|new\s+\w+\(', code_text):
        # Check for TypeScript specific features
        if re.search(r':\s*\w+(\[\])?|interface\s+\w+|<\w+>|implements\s+|namespace\s+', code_text):
            return "typescript"
        return "javascript"
    # HTML
    elif re.search(r'<(!DOCTYPE|html|head|body|div|span|p|a|img|ul|ol|li|table|form|input)\b|<\/\w+>', code_text, re.IGNORECASE):
        return "html"
    # SQL
    elif re.search(r'SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+.+\s+SET|DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE', code_text, re.IGNORECASE):
        return "sql"
    # JSON
    elif re.search(r'^\s*\{\s*"\w+"\s*:\s*', code_text) and re.search(r'}\s*$', code_text):
        return "json"
    # Java/Kotlin
    elif re.search(r'public\s+(class|interface)|private\s+\w+|protected\s+\w+|@Override|import\s+java\.|System\.out\.print', code_text):
        return "java"
    # C++
    elif re.search(r'#include\s+<\w+(\.\w+)?>|std::|int\s+main\s*\(\s*(?:void|int\s+argc)|void\s+\w+\s*\(\s*\w+', code_text):
        return "cpp"
    # Go
    elif re.search(r'package\s+main|import\s+\(\s*"|func\s+\w+\s*\(|go\s+func|make\(\w+\)', code_text):
        return "go"
    # Rust
    elif re.search(r'fn\s+\w+|let\s+mut\s+|struct\s+\w+|impl\s+|use\s+\w+::|pub\s+fn', code_text):
        return "rust"
    # Bash/Shell
    elif re.search(r'#!/bin/(ba)?sh|export\s+\w+=|\$\(\w+\)|if\s+\[\s+|\[\s+.+\s+\]', code_text):
        return "bash"
    # YAML
    elif re.search(r'^\s*\w+:\s*\n\s+-\s+', code_text, re.MULTILINE):
        return "yaml"
    
    # Default/fallback
    return "text"

def process_code_block(code_text: str, language: str = "text", url: str = None) -> Tuple[str, str]:
    """
    Process a code block for better formatting in markdown with special handling for Crawl4AI code.
    
    Args:
        code_text: The code text to process
        language: The detected programming language
        url: The source URL for context
        
    Returns:
        Tuple of (formatted_code_text, language)
    """
    # Skip processing for very short code snippets
    if len(code_text) < 5:
        return code_text, language
    
    # Split into lines and remove empty lines at beginning and end
    lines = code_text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    
    if not lines:
        return code_text, language
        
    # Determine the minimum indent level (ignoring empty lines)
    non_empty_lines = [line for line in lines if line.strip()]
    if not non_empty_lines:
        return code_text, language
        
    min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
    
    # Process based on language
    if language == "python":
        # Format Python code
        formatted_lines = []
        for line in lines:
            # Preserve empty lines
            if not line.strip():
                formatted_lines.append("")
                continue
                
            # Preserve relative indentation but remove common leading whitespace
            indent = len(line) - len(line.lstrip())
            relative_indent = " " * (indent - min_indent) if indent > min_indent else ""
            content = line.lstrip()
            
            # Fix common Python spacing issues
            content = re.sub(r'import(\w+)', r'import \1', content)
            content = re.sub(r'from(\w+)', r'from \1', content)
            content = re.sub(r'def(\w+)', r'def \1', content)
            content = re.sub(r'class(\w+)', r'class \1', content)
            content = re.sub(r'if(\w+)', r'if \1', content)
            content = re.sub(r'elif(\w+)', r'elif \1', content)
            content = re.sub(r'for(\w+)', r'for \1', content)
            content = re.sub(r'while(\w+)', r'while \1', content)
            content = re.sub(r'with(\w+)', r'with \1', content)
            content = re.sub(r'return(\w+)', r'return \1', content)
            content = re.sub(r'except(\w+)', r'except \1', content)
            content = re.sub(r'as(\w+)', r'as \1', content)
            content = re.sub(r'in(\w+)', r'in \1', content)
            content = re.sub(r'await(\w+)', r'await \1', content)
            content = re.sub(r'async(\w+)', r'async \1', content)
            
            # Crawl4AI specific patterns
            if 'crawl4ai' in url.lower() if url else False:
                # Preserve CrawlerRunConfig
                content = re.sub(r'(CrawlerRunConfig)\s*\(', r'\1(', content)
                # Preserve AsyncWebCrawler pattern
                content = re.sub(r'(AsyncWebCrawler)\s*\(', r'\1(', content)
                # Preserve DefaultMarkdownGenerator pattern
                content = re.sub(r'(DefaultMarkdownGenerator)\s*\(', r'\1(', content)
            
            # Fix method chaining spacing
            content = re.sub(r'\.(\w+)\(', r'.\1(', content)
            
            # Fix operator spacing
            content = re.sub(r'([^=!<>])=([^=])', r'\1 = \2', content)
            content = re.sub(r'([^+])\+([^+=])', r'\1 + \2', content)
            content = re.sub(r'([^-])-([^-=])', r'\1 - \2', content)
            content = re.sub(r'([^*])\*([^*=])', r'\1 * \2', content)
            content = re.sub(r'([^/])/([^/=])', r'\1 / \2', content)
            
            formatted_lines.append(f"{relative_indent}{content}")
            
        # Fix imports for Crawl4AI specific code
        formatted_code = "\n".join(formatted_lines)
        if 'crawl4ai' in url.lower() if url else False:
            # Ensure proper imports for Crawl4AI (add if missing)
            if 'AsyncWebCrawler' in formatted_code and 'from crawl4ai import AsyncWebCrawler' not in formatted_code:
                pattern = re.compile(r'^(import|from)', re.MULTILINE)
                match = pattern.search(formatted_code)
                if match:
                    insert_point = match.start()
                    formatted_code = formatted_code[:insert_point] + "from crawl4ai import AsyncWebCrawler, CrawlerRunConfig\n" + formatted_code[insert_point:]
            
        return formatted_code, "python"
    
    elif language in ["javascript", "typescript", "jsx", "tsx"]:
        # Format JavaScript/TypeScript code
        formatted_lines = []
        for line in lines:
            if not line.strip():
                formatted_lines.append("")
                continue
                
            indent = len(line) - len(line.lstrip())
            relative_indent = " " * (indent - min_indent) if indent > min_indent else ""
            content = line.lstrip()
            
            # Fix common JS spacing issues
            content = re.sub(r'function(\w+)', r'function \1', content)
            content = re.sub(r'const(\w+)', r'const \1', content)
            content = re.sub(r'let(\w+)', r'let \1', content)
            content = re.sub(r'var(\w+)', r'var \1', content)
            content = re.sub(r'if(\w+)', r'if \1', content)
            content = re.sub(r'else(\w+)', r'else \1', content)
            content = re.sub(r'for(\w+)', r'for \1', content)
            content = re.sub(r'while(\w+)', r'while \1', content)
            content = re.sub(r'switch(\w+)', r'switch \1', content)
            content = re.sub(r'return(\w+)', r'return \1', content)
            
            # Fix operator spacing
            content = re.sub(r'([^=!<>])=([^=])', r'\1 = \2', content)
            content = re.sub(r'([^+])\+([^+=])', r'\1 + \2', content)
            content = re.sub(r'([^-])-([^-=])', r'\1 - \2', content)
            
            formatted_lines.append(f"{relative_indent}{content}")
            
        return "\n".join(formatted_lines), language
    
    elif language in ["json", "yaml"]:
        # For structured data formats, try to ensure valid formatting
        try:
            if language == "json":
                parsed = json.loads(code_text)
                return json.dumps(parsed, indent=2), language
            # YAML handling would go here if needed
        except:
            pass
        # If parsing fails, just return original with indentation preserved
        formatted_lines = []
        for line in lines:
            if not line.strip():
                formatted_lines.append("")
                continue
                
            indent = len(line) - len(line.lstrip())
            relative_indent = " " * (indent - min_indent) if indent > min_indent else ""
            content = line.lstrip()
            
            formatted_lines.append(f"{relative_indent}{content}")
            
        return "\n".join(formatted_lines), language
    
    else:
        # For other languages, just preserve indentation structure
        formatted_lines = []
        for line in lines:
            if not line.strip():
                formatted_lines.append("")
                continue
                
            indent = len(line) - len(line.lstrip())
            relative_indent = " " * (indent - min_indent) if indent > min_indent else ""
            content = line.lstrip()
            
            formatted_lines.append(f"{relative_indent}{content}")
            
        return "\n".join(formatted_lines), language

def post_process_markdown(markdown_content: str, url: str) -> str:
    """
    Process the markdown content to improve code block formatting and add metadata.
    
    Args:
        markdown_content: The markdown content to process
        url: The original URL source
        
    Returns:
        Processed markdown content with better formatting
    """
    # Count code blocks
    code_blocks_count = len(re.findall(r'```[^\n]*\n', markdown_content))
    
    # Process code blocks
    def replace_code_block(match):
        lang = match.group(1).strip().lower()
        code = match.group(2)
        
        # Process the code block
        formatted_code, detected_lang = process_code_block(code, lang if lang else "text", url)
        
        # Use detected language if original is empty or generic
        final_lang = detected_lang if not lang or lang == "text" else lang
        
        return f"```{final_lang}\n{formatted_code}\n```"
    
    # Find and replace code blocks with proper formatting
    processed_content = re.sub(r'```([^\n]*)\n(.*?)\n```', replace_code_block, markdown_content, flags=re.DOTALL)
    
    # Extract domain for metadata
    domain = url.split('/')[2] if '://' in url else url.split('/')[0]
    
    # Add frontmatter with metadata
    timestamp = datetime.datetime.now().isoformat()
    frontmatter = f"""---
url: {url}
source: gemini
date_processed: {timestamp}
domain: {domain}
content_type: documentation
contains_code: {code_blocks_count > 0}
"""
    
    if code_blocks_count > 0:
        frontmatter += f"code_blocks_count: {code_blocks_count}\n"
    
    frontmatter += f"formatter_version: 2.1\n---\n\n"
    
    # Add title and original URL reference at the top
    header = f"# {domain}\n\n> Original URL: [{url}]({url})\n\n"
    
    # Combine everything
    return frontmatter + header + processed_content

def build_crawl4ai_context():
    """Create context about Crawl4AI for the AI model based on available documentation."""
    context = []
    
    # Look for documentation in the markdown folders
    for md_dir in Path(".").glob("markdown_pages*"):
        if md_dir.is_dir():
            crawl4ai_docs = list(md_dir.glob("**/crawl4ai*.md"))
            
            # Take the most relevant docs (first 3)
            for doc_path in crawl4ai_docs[:3]:
                try:
                    with open(doc_path, "r", encoding="utf-8") as f:
                        doc_content = f.read()
                        # Extract title and first paragraph
                        title_match = re.search(r'# (.*?)\n', doc_content)
                        title = title_match.group(1) if title_match else "Crawl4AI Documentation"
                        
                        # Extract a few code examples
                        code_examples = re.findall(r'```python\n(.*?)\n```', doc_content, re.DOTALL)
                        
                        if code_examples:
                            context.append(f"Example from {title}:\n```python\n{code_examples[0]}\n```")
                except Exception as e:
                    logging.warning(f"Could not read {doc_path}: {e}")
    
    if not context:
        # If no docs found, provide a basic example
        context.append("""
Example Crawl4AI usage:
```python
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, DefaultMarkdownGenerator

async def main():
    async with AsyncWebCrawler() as crawler:
        config = CrawlerRunConfig(
            markdown_generator=DefaultMarkdownGenerator()
        )
        result = await crawler.arun(url="https://example.com", config=config)
        if result.success:
            print(result.markdown.fit_markdown)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```
""")
    
    return "\n\n".join(context)

# --- Helper Function for Conversion ---
def convert_html_to_markdown(html_content: str, url: str) -> str:
    """Uses Google Gemini to convert HTML content to Markdown with enhanced code awareness."""
    # Get context about Crawl4AI if relevant
    crawl4ai_context = ""
    if "crawl4ai" in url:
        crawl4ai_context = build_crawl4ai_context()
        
    prompt = f"""Please convert the following HTML content from the URL '{url}' into well-formatted Markdown.
Focus on preserving the main textual content, headings, lists, code blocks, and tables.
Ignore navigational elements unless they contain significant text.
Ensure the Markdown is clean and readable.

IMPORTANT - For code blocks, carefully follow these specific rules:
1. Always use triple backticks with accurate language identifiers (```python, ```javascript, etc.)
2. Preserve EXACT indentation and spacing in code blocks - this is critical for correct execution
3. Keep all imports and class/function definitions intact
4. Pay special attention to Python code, preserving docstrings and comments
5. For Python code, ensure proper spacing after keywords (def, class, import, etc.)
6. NEVER modify the logic or functionality of code

{crawl4ai_context}

HTML Content:
```html
{html_content[:30000]}
```

Markdown Output:""" # Increased token limit for better context

    try:
        # Add safety settings to reduce chances of blocking due to sensitive content in HTML
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        response = model.generate_content(prompt, safety_settings=safety_settings)

        # Check if the response has text content
        if response.parts:
             markdown_content = response.text
             logging.info(f"Successfully converted content from {url}")
             
             # Post-process the markdown to improve code formatting
             enhanced_markdown = post_process_markdown(markdown_content, url)
             return enhanced_markdown
        else:
            # Log the reason if the response was blocked or empty
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
            logging.warning(f"Conversion failed for {url}. Reason: {block_reason}. Response: {response}")
            return f"# Conversion Failed\n\nReason: {block_reason}\nURL: {url}"

    except Exception as e:
        logging.error(f"Error during Gemini API call for {url}: {e}")
        # Implement basic exponential backoff
        time.sleep(2) # Wait 2 seconds before potential retry or next step
        # In a production scenario, you might retry here
        return f"# Conversion Error\n\nAn error occurred during conversion: {e}\nURL: {url}"


# --- Main Processing Logic ---
def process_csv_files(input_dir=None):
    """
    Reads CSV files with HTML content, converts to Markdown using AI, and saves results.
    
    Args:
        input_dir: Optional specific directory to process, or process all directories under CSV_DIR
    """
    if input_dir:
        directories = [Path(input_dir)]
    else:
        # Check for any domain-specific directories
        directories = [d for d in CSV_DIR.glob('*') if d.is_dir()]
        if not directories:
            directories = [CSV_DIR]  # If no subdirectories, use the main directory
    
    for directory in directories:
        if not directory.is_dir():
            logging.error(f"Input directory '{directory}' not found.")
            continue
            
        logging.info(f"Processing files in '{directory}'...")
        csv_files = list(directory.glob("*.csv"))
        if not csv_files:
            logging.warning(f"No CSV files found in '{directory}'.")
            continue

        logging.info(f"Found {len(csv_files)} CSV files to process in {directory}.")
        
        # Create a corresponding output directory
        output_dir = MD_DIR / directory.name
        output_dir.mkdir(exist_ok=True)

        for csv_filepath in csv_files:
            logging.info(f"Processing '{csv_filepath.name}'...")
            md_filename = csv_filepath.stem + ".md"
            md_filepath = output_dir / md_filename

            # Skip if Markdown file already exists
            if md_filepath.exists():
                logging.info(f"Markdown file '{md_filepath.name}' already exists. Skipping.")
                continue

            try:
                with open(csv_filepath, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    # Assuming only one row per CSV based on the previous script's logic
                    row = next(reader, None)
                    if not row:
                        logging.warning(f"CSV file '{csv_filepath.name}' is empty or has no header. Skipping.")
                        continue

                    try:
                        page_data = PageData(**row)
                    except ValidationError as e:
                        logging.warning(f"Data validation error in '{csv_filepath.name}': {e}. Skipping.")
                        continue

                    # Convert HTML to Markdown using Gemini with enhanced code formatting
                    markdown_content = convert_html_to_markdown(page_data.html_content, page_data.url)

                    # Save the Markdown content
                    try:
                        with open(md_filepath, 'w', encoding='utf-8') as mdfile:
                            mdfile.write(markdown_content)
                        logging.info(f"Saved Markdown to '{md_filepath.name}'")
                    except IOError as e:
                        logging.error(f"Error writing Markdown file '{md_filepath.name}': {e}")

            except FileNotFoundError:
                logging.error(f"CSV file '{csv_filepath.name}' not found.")
            except Exception as e:
                logging.error(f"An unexpected error occurred processing '{csv_filepath.name}': {e}")

            # Add a small delay between API calls to avoid hitting rate limits
            time.sleep(1.5) # Adjust as needed based on API limits (Gemini Flash allows 60 QPM typically)

        logging.info(f"Finished processing all CSV files in '{directory}'.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert HTML content to Markdown using Google Gemini AI")
    parser.add_argument("--input", help="Specific input directory to process (optional)")
    args = parser.parse_args()
    
    # Attempt to load documentation snippets for reference
    try:
        DOCS_CACHE = load_documentation_snippets()
    except Exception as e:
        logging.warning(f"Could not load documentation snippets: {e}")
    
    # Process CSV files in the specified directory or all directories
    process_csv_files(args.input)