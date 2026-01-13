import os
import re
import time
import requests
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

class NepalActsScraper:
    """Scraper for Nepal Law Commission acts organized by Nepali alphabet sections"""
    
    def __init__(self, save_dir="nepal_acts_pdf"):
        self.save_dir = save_dir
        self.base_url = "https://lawcommission.gov.np/pages/alphabetical-index-of-acts/"
        self.root_url = "https://lawcommission.gov.np"
        self.downloaded_files = set()
        self.total_downloaded = 0
        
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        
        # Load already downloaded files
        self.downloaded_files = set(os.listdir(self.save_dir))
    
    @staticmethod
    def clean_filename(text):
        """Clean text to create valid filename"""
        clean = re.sub(r'[\\/*?:"<>|]', "", text)
        return clean.replace(" ", "_").strip()
    
    @staticmethod
    def extract_category_id(url):
        """Extract category ID from URL"""
        match = re.search(r"/category/(\d+)", url)
        return match.group(1) if match else None
    
    def download_pdf(self, url, filename):
        """Download a PDF file using requests"""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                path = os.path.join(self.save_dir, filename)
                with open(path, "wb") as f:
                    f.write(response.content)
                print(f"  ✓ Downloaded: {filename}")
                return True
            else:
                print(f"  ✗ Failed: Status {response.status_code}")
                return False
        except Exception as e:
            print(f"  ✗ Error downloading: {e}")
            return False
    
    def extract_categories_from_section(self, page, section_letter):
        """Extract unique categories from a specific alphabet section"""
        print(f"\nLooking for '{section_letter}' section...")
        
        # Find the section heading
        section = page.locator(f"td strong span:has-text('{section_letter}')").first
        if section.count() == 0:
            section = page.locator(f"td:has(strong):has-text('{section_letter}')").first
        
        if section.count() == 0:
            print(f"ERROR: Could not find '{section_letter}' section")
            return {}
        
        print(f"Found '{section_letter}' section!")
        
        # Get the row and following rows
        section_row = section.locator("xpath=ancestor::tr[1]")
        following_rows = section_row.locator("xpath=following-sibling::tr")
        
        category_map = {}
        
        # Process each row
        for i in range(following_rows.count()):
            row = following_rows.nth(i)
            
            # Check if we've hit another section
            if row.locator("td strong span").count() > 0:
                next_section = row.locator("td strong span").first.inner_text().strip()
                if next_section != section_letter and len(next_section) == 1:
                    print(f"Reached next section: {next_section}, stopping...")
                    break
            
            cells = row.locator("td").all()
            if len(cells) < 2:
                continue
            
            # Extract law name
            law_name = cells[0].inner_text().strip()
            if not law_name:
                continue
            
            # Extract category link
            category_link = None
            category_id = None
            
            for cell in cells[1:]:
                links = cell.locator("a.in-cell-link[href*='/category/']").all()
                if links:
                    href = links[0].get_attribute("href")
                    if href:
                        category_link = href if href.startswith('http') else urljoin(self.root_url, href)
                        category_id = self.extract_category_id(category_link)
                        break
            
            # Store unique categories only
            if category_id and category_id not in category_map:
                category_map[category_id] = {
                    'url': category_link,
                    'name': law_name,
                    'section': section_letter
                }
                print(f"  ✓ Unique category {category_id}: {law_name}")
            elif category_id:
                print(f"  → Duplicate category {category_id}: {law_name}")
        
        print(f"Total unique categories in '{section_letter}': {len(category_map)}")
        return category_map
    
    def scrape_category(self, page, category_id, category_info):
        """Scrape all PDFs from a category with pagination"""
        category_url = category_info['url']
        law_name = category_info['name']
        section = category_info['section']
        
        print(f"\n{'='*70}")
        print(f"Section: {section} | Category {category_id}: {law_name}")
        print(f"{'='*70}")
        
        page_num = 1
        category_pdf_count = 0
        
        while True:
            paged_url = f"{category_url.rstrip('/')}/?page={page_num}"
            print(f"\n  Page {page_num}: {paged_url}")
            
            try:
                page.goto(paged_url, wait_until="networkidle", timeout=60000)
                time.sleep(2)
            except Exception as e:
                print(f"  ✗ Error loading page: {e}")
                break
            
            rows = page.locator("table tr").all()
            if not rows:
                print(f"  No rows found on page {page_num}")
                break
            
            new_pdf_found = False
            
            for row in rows:
                pdf_links = row.locator("a[href$='.pdf'], a:has(i.fa-file-pdf)").all()
                if not pdf_links:
                    continue
                
                cells = row.locator("td").all()
                if len(cells) < 2:
                    continue
                
                title = cells[1].inner_text().strip()
                if not title:
                    continue
                
                filename = f"{self.clean_filename(title)}.pdf"
                
                if filename in self.downloaded_files:
                    print(f"    ✓ Already exists: {filename}")
                    continue
                
                pdf_url = pdf_links[0].get_attribute("href")
                if pdf_url:
                    pdf_url = pdf_url if pdf_url.startswith("http") else urljoin(self.root_url, pdf_url)
                    print(f"    Downloading: {title}")
                    
                    if self.download_pdf(pdf_url, filename):
                        self.downloaded_files.add(filename)
                        self.total_downloaded += 1
                        category_pdf_count += 1
                        new_pdf_found = True
                        time.sleep(1)  # Rate limiting
            
            if not new_pdf_found:
                print(f"  No new PDFs on page {page_num}, moving to next category")
                break
            
            page_num += 1
        
        print(f"  Category complete: {category_pdf_count} PDFs downloaded")
        return category_pdf_count
    
    def scrape_sections(self, sections):
        """Main scraping method for multiple sections"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            print(f"{'='*70}")
            print(f"NEPAL ACTS PDF SCRAPER")
            print(f"{'='*70}")
            print(f"Target sections: {', '.join(sections)}")
            print(f"Save directory: {os.path.abspath(self.save_dir)}")
            print(f"{'='*70}\n")
            
            # Navigate to main page
            print(f"Navigating to {self.base_url}...")
            page.goto(self.base_url, wait_until="networkidle", timeout=90000)
            time.sleep(2)
            
            all_categories = {}
            
            # Extract categories from each section
            for section in sections:
                categories = self.extract_categories_from_section(page, section)
                all_categories.update(categories)
            
            print(f"\n{'='*70}")
            print(f"EXTRACTION SUMMARY")
            print(f"{'='*70}")
            print(f"Total unique categories found: {len(all_categories)}")
            print(f"Ready to scrape PDFs...")
            print(f"{'='*70}\n")
            
            if len(all_categories) == 0:
                print("ERROR: No categories found. Exiting.")
                browser.close()
                return
            
            # Scrape each category
            for category_id, category_info in all_categories.items():
                self.scrape_category(page, category_id, category_info)
            
            browser.close()
            
            # Final summary
            print(f"\n{'='*70}")
            print(f"SCRAPING COMPLETE")
            print(f"{'='*70}")
            print(f"Sections scraped: {', '.join(sections)}")
            print(f"Total categories processed: {len(all_categories)}")
            print(f"Total PDFs downloaded: {self.total_downloaded}")
            print(f"All PDFs saved in: {os.path.abspath(self.save_dir)}")
            print(f"{'='*70}\n")


def main():
    """Main entry point"""
    scraper = NepalActsScraper(save_dir="nepal_acts_pdf")
    
    # Define which sections to scrape
    # You can easily add more sections: ['अ', 'आ', 'इ', 'ई', 'उ', ...]
    sections_to_scrape = ['अ', 'आ']
    
    scraper.scrape_sections(sections_to_scrape)


if __name__ == "__main__":
    main()