import os
import pytesseract
from pdf2image import convert_from_path
import pymupdf  
from tqdm import tqdm 

INPUT_DIR = "C:\\Users\\poudy\\Downloads\\license_RAG\\data\\nepal_acts_pdf"
OUTPUT_DIR = "C:\\Users\\poudy\\Downloads\\license_RAG\\data\\ocr_texts"
DPI = 300                  

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def is_pdf_digital(doc):
    for page_num in range(min(3, len(doc))):
        if len(doc[page_num].get_text().strip()) > 50:
            return True
    return False

def extract_digital(pdf_path):
    text_content = []
    doc = pymupdf.open(pdf_path)
    for i, page in enumerate(doc):
        page_text = page.get_text("text")
        text_content.append(f"--- PAGE {i+1} ---\n{page_text}")
    doc.close()
    return "\n".join(text_content)

def extract_scanned(pdf_path):
    text_content = []
    images = convert_from_path(pdf_path, dpi=DPI)
    for i, image in enumerate(images):
        page_text = pytesseract.image_to_string(image, lang='nep')
        text_content.append(f"--- PAGE {i+1} ---\n{page_text}")
    return "\n".join(text_content)

def process_all_acts():
    files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith('.pdf')])    
    print(f"Starting ingestion of {len(files)} files...")
    
    for filename in tqdm(files):
        pdf_path = os.path.join(INPUT_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, filename.replace(".pdf", ".txt"))
        
        try:
            doc = pymupdf.open(pdf_path)
            if is_pdf_digital(doc):
                content = extract_digital(pdf_path)
            else:
                content = extract_scanned(pdf_path)
            doc.close()
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    process_all_acts()