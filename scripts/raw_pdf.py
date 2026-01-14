import os
import re
import time
import requests
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

class NepalActsScraper:    
    def __init__(self, save_dir="nepal_acts_pdf"):
        self.save_dir = save_dir
        self.base_url = "https://lawcommission.gov.np/pages/alphabetical-index-of-acts/"
        self.root_url = "https://lawcommission.gov.np"
        self.downloaded_files = set()
        self.total_downloaded = 0
        
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        
        self.downloaded_files = set(os.listdir(self.save_dir))
    
    @staticmethod
    def clean_filename(text):
        clean = re.sub(r'[\\/*?:"<>|]', "", text)
        return clean.replace(" ", "_").strip()
    
    @staticmethod
    def extract_category_id(url):
        match = re.search(r"/category/(\d+)", url)
        return match.group(1) if match else None
    
    def download_pdf(self, url, filename):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                path = os.path.join(self.save_dir, filename)
                with open(path, "wb") as f:
                    f.write(response.content)
                print(f"Downloaded: {filename}")
                return True
            else:
                print(f"Failed: Status {response.status_code}")
                return False
        except Exception as e:
            print(f"Error downloading: {e}")
            return False
    
    def extract_categories_from_section(self, page, section_letters):
        print(f"\nExtracting sections: {', '.join(section_letters)}")
        
        all_rows = page.locator("table tr").all()
        category_map = {}
        current_section = None
        
        for row in all_rows:
            header_span = row.locator("td strong span")
            if header_span.count() > 0:
                section_letter = header_span.first.inner_text().strip()
                if section_letter in section_letters and len(section_letter) == 1:
                    current_section = section_letter
                    print(f"\nFound section: {current_section}")
                    continue
            
            if current_section:
                cells = row.locator("td").all()
                if len(cells) >= 1:
                    law_name = cells[0].inner_text().strip()
                    if law_name:
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
                        if category_id and category_id not in category_map:
                            category_map[category_id] = {
                                "url": category_link,
                                "name": law_name,
                                "section": current_section
                            }
                            print(f"{current_section} - {law_name}")
                        elif category_id:
                            print(f"Duplicate: {law_name}")
        
        print(f"\nTotal unique categories found: {len(category_map)}")
        return category_map
    
    def scrape_category(self, page, category_id, category_info):
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
                print(f"Error loading page: {e}")
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
                        time.sleep(1) 
            
            if not new_pdf_found:
                print(f"  No new PDFs on page {page_num}, moving to next category")
                break
            
            page_num += 1
        
        print(f"  Category complete: {category_pdf_count} PDFs downloaded")
        return category_pdf_count
    
    def scrape_sections(self, sections):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            print(f"{'='*70}")
            print(f"NEPAL ACTS PDF SCRAPER")
            print(f"{'='*70}")
            print(f"Target sections: {', '.join(sections)}")
            print(f"Save directory: {os.path.abspath(self.save_dir)}")
            print(f"{'='*70}\n")            
            print(f"Navigating to {self.base_url}...")
            page.goto(self.base_url, wait_until="networkidle", timeout=90000)
            time.sleep(2)            
            all_categories = self.extract_categories_from_section(page, sections)
            
            if len(all_categories) == 0:
                print("ERROR: No categories found. Exiting.")
                browser.close()
                return
            
            for category_id, category_info in all_categories.items():
                self.scrape_category(page, category_id, category_info)
            
            browser.close()            
            print(f"\n{'='*70}")
            print(f"SCRAPING COMPLETE")
            print(f"{'='*70}")
            print(f"Sections scraped: {', '.join(sections)}")
            print(f"Total categories processed: {len(all_categories)}")
            print(f"Total PDFs downloaded: {self.total_downloaded}")
            print(f"All PDFs saved in: {os.path.abspath(self.save_dir)}")
            print(f"{'='*70}\n")


def main():
    scraper = NepalActsScraper(save_dir="nepal_acts_pdf")    
    sections_to_scrape = ['अ', 'आ']
    scraper.scrape_sections(sections_to_scrape)


if __name__ == "__main__":
    main()
