import streamlit as st
import os
import re
import subprocess
import sys
import io
import time
import shutil
import datetime
import zipfile
from pathlib import Path
from typing import List, Optional, Dict

# Function to check if a module is installed
def is_module_installed(module_name):
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False

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
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout + "\n" + result.stderr
    except Exception as e:
        return False, str(e)

# Set page configuration
st.set_page_config(layout="wide", page_title="AI-Enhanced Sitemap Crawler")

# Title and description
st.title("AI-Enhanced Sitemap Crawler")
st.markdown("""
This tool combines web scraping with AI conversion to generate high-quality Markdown 
from any website's sitemap. It uses Crawl4AI for accurate HTML extraction and Google Gemini
for intelligent markdown generation with enhanced code formatting.
""")

# Verify required installations
required_packages = {
    "crawl4ai": is_module_installed("crawl4ai"),
    "pydantic": is_module_installed("pydantic"),
    "requests": is_module_installed("requests"),
    "beautifulsoup4": is_module_installed("bs4"),
    "google.generativeai": is_module_installed("google.generativeai"),
    "playwright": is_module_installed("playwright")
}

# Check for missing packages
missing_packages = [pkg for pkg, installed in required_packages.items() if not installed]
if missing_packages:
    st.error(f"❌ Missing required packages: {', '.join(missing_packages)}")
    st.info("To install required packages, run: pip install -r requirements.txt")
    st.stop()

# Check for Playwright browsers
playwright_browsers_installed = check_playwright_browsers()
if not playwright_browsers_installed and required_packages.get("playwright", False):
    st.warning("⚠️ Playwright browsers are not installed. Crawl4AI requires these browsers to function.")
    if st.button("Install Playwright Browsers"):
        with st.spinner("Installing Playwright browsers (this may take a minute)..."):
            success, output = install_playwright_browsers()
            if success:
                st.success("✅ Playwright browsers installed successfully!")
                playwright_browsers_installed = True
            else:
                st.error(f"❌ Failed to install Playwright browsers. Error: {output}")
                st.info("Please run this command manually in your terminal: `python -m playwright install chromium`")

# Check for environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        st.warning("⚠️ GEMINI_API_KEY not found in environment or .env file. AI conversion will not work.")
except ImportError:
    st.warning("python-dotenv not installed. Using environment variables only.")

# --- Main UI Section ---
st.markdown("## Sitemap URL")
sitemap_url = st.text_input(
    "Enter sitemap URL",
    value="https://docs.crawl4ai.com/sitemap.xml",
    help="Enter the full URL of a sitemap (e.g., https://example.com/sitemap.xml)"
)

# Basic validation
if sitemap_url:
    if not sitemap_url.lower().endswith(".xml"):
        st.warning("URL should typically end with sitemap.xml", icon="⚠️")
    elif not sitemap_url.startswith(("http://", "https://")):
        st.warning("Sitemap URL should start with http:// or https://", icon="⚠️")

# Generate domain name for output directories
domain = ""
safe_domain = ""
if sitemap_url and "://" in sitemap_url:
    domain = sitemap_url.split("://")[1].split("/")[0]
    safe_domain = re.sub(r'[^\w.]', '_', domain)
    
# Display output locations
if domain:
    html_dir = f"scraped_pages/{domain}_sitemap"
    markdown_dir = f"ai_markdown_pages/{domain}_sitemap"
    
    st.markdown("## Output Locations")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"HTML will be saved to: **{html_dir}**")
    with col2:
        st.info(f"Markdown will be saved to: **{markdown_dir}**")

# Run options
st.markdown("## Run Options")

# Disable the run button if Playwright browsers aren't installed
run_button = st.button(
    "▶️ Run Integrated Workflow",
    help="Scrape the sitemap and convert HTML to enhanced markdown",
    type="primary",
    use_container_width=True,
    disabled=not playwright_browsers_installed and required_packages.get("playwright", False)
)

# Current status section
st.markdown("## Status")
status_container = st.empty()

# Run the integrated workflow
if run_button and sitemap_url:
    # Create output placeholder and progress bar
    output_container = st.empty()
    progress_bar = st.progress(0)
    
    # Log file for this run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"run_log_{timestamp}.txt"
    
    status_container.info(f"Starting integrated workflow for {sitemap_url}...")
    
    try:
        # Setup command for the integrated workflow
        cmd = [
            sys.executable, 
            "integrated_workflow.py", 
            "--sitemap", 
            sitemap_url
        ]
        
        # Setup environment with UTF-8 encoding
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # Run as subprocess
        with st.spinner(f"Processing {sitemap_url}..."):
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
                bufsize=1,
                env=env
            )
            
            # For storing and displaying output
            log_output = []
            
            # Read and display output in real-time
            for line in io.TextIOWrapper(process.stdout, encoding='utf-8'):
                line = line.strip()
                log_output.append(line)
                
                # Update progress indicator based on log content
                if "Starting web scraping process" in line:
                    progress_bar.progress(0.1)
                    status_container.info("🔍 Scraping sitemap URLs...")
                elif "Fetched" in line and "URLs from sitemap" in line:
                    # Extract number of URLs
                    try:
                        num_urls = int(re.search(r"Fetched (\d+) URLs", line).group(1))
                        if num_urls > 0:
                            progress_bar.progress(0.2)
                            status_container.info(f"📋 Found {num_urls} URLs in sitemap")
                    except:
                        pass
                elif "Processing URL:" in line:
                    progress_bar.progress(0.3)
                    status_container.info("🌐 Processing web pages...")
                elif "Starting AI conversion process" in line:
                    progress_bar.progress(0.5)
                    status_container.info("🧠 Starting AI conversion of HTML to Markdown...")
                elif "Processing '" in line and ".csv'" in line:
                    # We're in the conversion phase
                    progress_bar.progress(0.7)
                    status_container.info("📝 Applying AI to format content and code blocks...")
                elif "Saved Markdown to" in line:
                    progress_bar.progress(0.8)
                    status_container.info("💾 Saving formatted Markdown files...")
                elif "Integrated workflow completed successfully" in line:
                    progress_bar.progress(1.0)
                    status_container.success("✅ Processing complete!")
                # Check for Playwright browser error
                elif "BrowserType.launch: Executable doesn't exist" in line or "playwright install" in line:
                    status_container.error("❌ Playwright browser error. Please install the required browsers.")
                    st.error("Playwright browsers are required but not installed.")
                    
                    # Offer to install browsers
                    if st.button("Install Playwright Browsers Now"):
                        with st.spinner("Installing Playwright browsers..."):
                            success, output = install_playwright_browsers()
                            if success:
                                st.success("✅ Playwright browsers installed successfully! Please run the workflow again.")
                            else:
                                st.error(f"❌ Failed to install browsers: {output}")
                                st.info("Run this command manually: python -m playwright install chromium")
                
                # Show a scrollable log preview (last 20 lines)
                log_preview = "\n".join(log_output[-20:])
                output_container.code(log_preview, language="bash")
                
                # Force update UI
                time.sleep(0.01)
            
            # Wait for process to complete and get return code
            return_code = process.wait()
            
            # Save the full log
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(log_output))
            
            # Handle process completion
            if return_code != 0:
                status_container.error(f"❌ Process failed with exit code {return_code}")
                st.error("Check the log output above for details on the error.")
            else:
                status_container.success(f"✅ Processing completed successfully!")
                
                # Count generated files
                html_files = len(list(Path(html_dir).glob("*.csv"))) if Path(html_dir).exists() else 0
                md_files = len(list(Path(markdown_dir).glob("*.md"))) if Path(markdown_dir).exists() else 0
                
                st.success(f"Generated {html_files} HTML files and {md_files} Markdown files")
                
                # Offer download option for the markdown files
                if md_files > 0:
                    # Create a ZIP of the markdown files
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for file_path in Path(markdown_dir).glob("*.md"):
                            # Add file to zip with relative path
                            zip_file.write(
                                file_path, 
                                arcname=file_path.name
                            )
                    
                    zip_buffer.seek(0)
                    
                    # Offer download
                    st.download_button(
                        label="📥 Download All Markdown Files",
                        data=zip_buffer.getvalue(),
                        file_name=f"{domain}_markdown.zip",
                        mime="application/zip"
                    )
    
    except Exception as e:
        status_container.error(f"❌ Error: {str(e)}")
        import traceback
        st.code(traceback.format_exc(), language="python")

# --- How It Works Section ---
with st.expander("How It Works", expanded=False):
    st.markdown("""
    ### Two-Step Pipeline

    This tool uses a powerful two-step process:

    1. **Web Scraping with Crawl4AI**:
       - Extracts URLs from the sitemap
       - Fetches and cleans HTML content
       - Preserves document structure and code blocks
       - Saves raw HTML to CSV files

    2. **AI-Enhanced Markdown Conversion**:
       - Uses Google Gemini AI to convert HTML to markdown
       - Applies special formatting for code blocks
       - Detects programming languages automatically
       - Preserves indentation and spacing in code
       - Adds rich metadata in YAML frontmatter

    ### Unique Features

    - **Enhanced Code Block Detection**: Language-specific formatting that preserves syntax
    - **Documentation-Aware Processing**: Uses examples from existing documentation
    - **Metadata-Rich Output**: Comprehensive YAML frontmatter with source info, timestamps, and more
    """)

# --- System Information Section ---
with st.expander("System Information", expanded=False):
    st.markdown("### Environment")
    st.code(f"""
Python: {sys.version}
Platform: {sys.platform}
Working Directory: {os.getcwd()}
    """)
    
    st.markdown("### Required Packages")
    for pkg, installed in required_packages.items():
        if installed:
            st.success(f"✅ {pkg}")
        else:
            st.error(f"❌ {pkg}")
    
    # Check Playwright browsers
    if playwright_browsers_installed:
        st.success("✅ Playwright browsers installed")
    else:
        st.error("❌ Playwright browsers not installed")
        if st.button("Install Playwright Browsers", key="install_browsers_system"):
            with st.spinner("Installing Playwright browsers..."):
                success, output = install_playwright_browsers()
                if success:
                    st.success("✅ Browsers installed successfully!")
                    playwright_browsers_installed = True  # Update status
                else:
                    st.error(f"❌ Installation failed: {output}")
    
    # Check Gemini API key
    if gemini_key:
        st.success("✅ GEMINI_API_KEY found")
    else:
        st.error("❌ GEMINI_API_KEY not found")
        st.info("Create a .env file with GEMINI_API_KEY=your_key_here")

# Footer
st.divider()
st.caption("Built with Python, Streamlit, Crawl4AI and Google Gemini")
