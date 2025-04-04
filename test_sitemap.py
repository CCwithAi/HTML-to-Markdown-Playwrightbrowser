import requests
import xml.etree.ElementTree as ET
import sys

def test_sitemap(sitemap_url):
    print(f"Testing sitemap: {sitemap_url}")
    
    try:
        response = requests.get(sitemap_url, timeout=10)
        print(f"Status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Failed to fetch sitemap: HTTP {response.status_code}")
            return False
            
        # Try to parse the XML
        try:
            root = ET.fromstring(response.content)
            # Namespace is important for parsing sitemaps
            namespace = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            urls = [url_el.text for url_el in root.findall('.//sm:loc', namespace)]
            
            print(f"Found {len(urls)} URLs in sitemap")
            if urls:
                print("First 3 URLs:")
                for url in urls[:3]:
                    print(f"  - {url}")
                return True
            else:
                print("No URLs found in sitemap")
                return False
                
        except ET.ParseError as e:
            print(f"Error parsing sitemap XML: {e}")
            print("First 200 characters of response:")
            print(response.text[:200])
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching sitemap: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    # Use command line arg if provided, otherwise use default
    sitemap_url = sys.argv[1] if len(sys.argv) > 1 else "https://docs.crawl4ai.com/sitemap.xml"
    test_sitemap(sitemap_url) 