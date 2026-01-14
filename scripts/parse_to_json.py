import os
import re
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import hashlib

INPUT_DIR = r"C:\Users\poudy\Downloads\license_RAG\data\ocr_texts"
OUTPUT_DIR = r"C:\Users\poudy\Downloads\license_RAG\data\parsed_json"

@dataclass
class LegalChunk:
    content: str
    content_with_context: str
    metadata: Dict
    chunk_id: str
    
    def to_dict(self):
        return asdict(self)

class NepaliLegalParser:
    def __init__(self):
        self.part_pattern = re.compile(r"भाग\s*[–\-]?\s*([\d१२३४५६७८९०]+)\s*(.*)")
        self.chapter_pattern = re.compile(r"परिच्छेद\s*[–\-]?\s*([\d१२३४५६७८९०]+)\s*(.*)")
        self.section_pattern = re.compile(r"^([\d१२३४५६७८९०]+)\.\s*(.*)")
        self.sub_section_pattern = re.compile(r"^\(([\d१२३४५६७८९०]+)\)\s*(.*)")
        self.clause_pattern = re.compile(r"^\(([कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह]+)\)\s*(.*)")
        
        self.ref_patterns = [
            re.compile(r"दफा\s*([\d१२३४५६७८९०]+)"),
            re.compile(r"उपदफा\s*\(([\d१२३४५६७८९०]+)\)"),
            re.compile(r"परिच्छेद\s*([\d१२३४५६७८९०]+)"),
        ]
        
        self.definition_markers = ["परिभाषा", "परिभाषाहरू", "शब्दार्थ"]
        self.schedule_markers = ["अनुसूची", "तफसिल"]
        
    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        
        text = re.sub(r'[□▪▫●○◆◇■]', '', text)
        text = re.sub(r'www\.lawcommission\.gov\.np', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'नेपाल राजपत्र.*?भाग', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s*([।,])\s*', r'\1 ', text)
        
        return text.strip()
    
    def get_act_metadata(self, file_path: str, text: str) -> Dict:
        base_name = os.path.basename(file_path)
        
        try:
            from urllib.parse import unquote
            decoded_name = unquote(base_name, encoding='utf-8')
            act_name = os.path.splitext(decoded_name)[0].replace('_', ' ').strip()
        except:
            act_name = os.path.splitext(base_name)[0].replace('_', ' ').strip()
        
        date_pattern = re.compile(r"२०[\d०१२३४५६७८९]+")
        dates = date_pattern.findall(text[:500])
        
        preamble = ""
        if "प्रस्तावना" in text[:1000]:
            preamble_match = re.search(r"प्रस्तावना[:\s]+(.*?)(?=भाग|परिच्छेद|१\.)", 
                                      text[:2000], re.DOTALL)
            if preamble_match:
                preamble = self.clean_text(preamble_match.group(1))
        
        return {
            "act_name": act_name,
            "act_identifier": self.generate_act_id(act_name),
            "enactment_date": dates[0] if dates else None,
            "preamble": preamble[:500] if preamble else None,
            "source_filename": base_name
        }
    
    def generate_act_id(self, act_name: str) -> str:
        return hashlib.md5(act_name.encode('utf-8')).hexdigest()[:8]
    
    def generate_chunk_id(self, act_id: str, dapha: str, sub: str = None, 
                          khanda: str = None) -> str:
        parts = [act_id, dapha]
        if sub:
            parts.append(sub)
        if khanda:
            parts.append(khanda)
        return "_".join(parts)
    
    def extract_cross_references(self, text: str) -> List[str]:
        references = []
        for pattern in self.ref_patterns:
            matches = pattern.findall(text)
            references.extend(matches)
        return list(set(references))
    
    def is_definition_section(self, text: str) -> bool:
        return any(marker in text for marker in self.definition_markers)
    
    def is_schedule_section(self, text: str) -> bool:
        return any(marker in text for marker in self.schedule_markers)
    
    def create_contextual_content(self, section_title: str, section_no: str,
                                  subsection_content: str = None,
                                  subsection_no: str = None,
                                  clause_content: str = None,
                                  clause_label: str = None) -> Tuple[str, str]:
        
        if clause_content:
            minimal = f"({clause_label}) {clause_content}"
        elif subsection_content:
            minimal = f"({subsection_no}) {subsection_content}"
        else:
            minimal = f"{section_no}. {section_title}"
        
        contextual = f"दफा {section_no}: {section_title}\n"
        if subsection_content:
            contextual += f"({subsection_no}) {subsection_content}\n"
        if clause_content:
            contextual += f"({clause_label}) {clause_content}"
        
        return minimal.strip(), contextual.strip()
    
    def parse_act(self, file_path: str) -> Tuple[List[LegalChunk], Dict]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    raw_text = f.read()
            except:
                with open(file_path, 'r', encoding='latin-1') as f:
                    raw_text = f.read()
        
        act_metadata = self.get_act_metadata(file_path, raw_text)
        act_id = act_metadata["act_identifier"]
        
        chunks = []
        definitions = []
        cross_references = defaultdict(list)
        
        current_part = "Main"
        current_chapter = "General"
        current_section_no = None
        current_section_title = None
        current_section_full_text = []
        current_subsection_no = None
        current_subsection_text = None
        
        anchor_found = False
        parse_stats = {
            "sections": 0,
            "subsections": 0,
            "clauses": 0,
            "definitions": 0
        }
        
        if "--- PAGE" in raw_text:
            pages = re.split(r"--- PAGE (\d+) ---", raw_text)
        else:
            pages = ['', '1', raw_text]
        
        for i in range(1, len(pages), 2):
            page_no = int(pages[i])
            lines = pages[i+1].split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if not anchor_found:
                    if ("प्रस्तावना" in line or 
                        "परिभाषा" in line or
                        re.match(r"^१\.", line) or
                        self.section_pattern.match(line)):
                        anchor_found = True
                    else:
                        continue
                
                p_m = self.part_pattern.match(line)
                if p_m:
                    current_part = f"भाग {p_m.group(1)}: {self.clean_text(p_m.group(2))}"
                    continue
                
                c_m = self.chapter_pattern.match(line)
                if c_m:
                    current_chapter = f"परिच्छेद {c_m.group(1)}: {self.clean_text(c_m.group(2))}"
                    continue
                
                s_m = self.section_pattern.match(line)
                if s_m:
                    current_section_no = s_m.group(1)
                    current_section_title = self.clean_text(s_m.group(2))
                    current_section_full_text = [current_section_title]
                    current_subsection_no = None
                    current_subsection_text = None
                    
                    minimal, contextual = self.create_contextual_content(
                        current_section_title, current_section_no
                    )
                    
                    chunk_id = self.generate_chunk_id(act_id, current_section_no)
                    refs = self.extract_cross_references(current_section_title)
                    is_def = self.is_definition_section(current_section_title)
                    
                    chunk = LegalChunk(
                        content=minimal,
                        content_with_context=contextual,
                        metadata={
                            "act_name": act_metadata["act_name"],
                            "act_identifier": act_id,
                            "part": current_part,
                            "chapter": current_chapter,
                            "dapha_no": current_section_no,
                            "citation": f"{act_metadata['act_name']}, दफा {current_section_no}",
                            "page_no": page_no,
                            "type": "section",
                            "is_definition": is_def,
                            "cross_references": refs,
                            "hierarchy_level": 1
                        },
                        chunk_id=chunk_id
                    )
                    
                    chunks.append(chunk)
                    parse_stats["sections"] += 1
                    
                    if is_def:
                        definitions.append(chunk_id)
                    
                    if refs:
                        cross_references[chunk_id] = refs
                    
                    continue
                
                sub_m = self.sub_section_pattern.match(line)
                if sub_m and current_section_no:
                    current_subsection_no = sub_m.group(1)
                    current_subsection_text = self.clean_text(sub_m.group(2))
                    current_section_full_text.append(f"({current_subsection_no}) {current_subsection_text}")
                    
                    minimal, contextual = self.create_contextual_content(
                        current_section_title, current_section_no,
                        current_subsection_text, current_subsection_no
                    )
                    
                    chunk_id = self.generate_chunk_id(act_id, current_section_no, 
                                                     current_subsection_no)
                    refs = self.extract_cross_references(current_subsection_text)
                    
                    chunk = LegalChunk(
                        content=minimal,
                        content_with_context=contextual,
                        metadata={
                            "act_name": act_metadata["act_name"],
                            "act_identifier": act_id,
                            "part": current_part,
                            "chapter": current_chapter,
                            "dapha_no": current_section_no,
                            "sub_section_no": current_subsection_no,
                            "citation": f"{act_metadata['act_name']}, दफा {current_section_no}({current_subsection_no})",
                            "page_no": page_no,
                            "type": "sub_section",
                            "parent_section_title": current_section_title,
                            "cross_references": refs,
                            "hierarchy_level": 2
                        },
                        chunk_id=chunk_id
                    )
                    
                    chunks.append(chunk)
                    parse_stats["subsections"] += 1
                    
                    if refs:
                        cross_references[chunk_id] = refs
                    
                    continue
                
                k_m = self.clause_pattern.match(line)
                if k_m and current_section_no:
                    khanda_label = k_m.group(1)
                    khanda_text = self.clean_text(k_m.group(2))
                    current_section_full_text.append(f"({khanda_label}) {khanda_text}")
                    
                    minimal, contextual = self.create_contextual_content(
                        current_section_title, current_section_no,
                        current_subsection_text, current_subsection_no,
                        khanda_text, khanda_label
                    )
                    
                    chunk_id = self.generate_chunk_id(act_id, current_section_no,
                                                     current_subsection_no, khanda_label)
                    refs = self.extract_cross_references(khanda_text)
                    
                    citation_parts = [f"{act_metadata['act_name']}, दफा {current_section_no}"]
                    if current_subsection_no:
                        citation_parts.append(f"({current_subsection_no})")
                    citation_parts.append(f"({khanda_label})")
                    
                    chunk = LegalChunk(
                        content=minimal,
                        content_with_context=contextual,
                        metadata={
                            "act_name": act_metadata["act_name"],
                            "act_identifier": act_id,
                            "part": current_part,
                            "chapter": current_chapter,
                            "dapha_no": current_section_no,
                            "sub_section_no": current_subsection_no,
                            "khanda_label": khanda_label,
                            "citation": "".join(citation_parts),
                            "page_no": page_no,
                            "type": "clause",
                            "parent_section_title": current_section_title,
                            "cross_references": refs,
                            "hierarchy_level": 3
                        },
                        chunk_id=chunk_id
                    )
                    
                    chunks.append(chunk)
                    parse_stats["clauses"] += 1
                    
                    if refs:
                        cross_references[chunk_id] = refs
                    
                    continue
                
                if chunks:
                    cleaned_line = self.clean_text(line)
                    chunks[-1].content += " " + cleaned_line
                    chunks[-1].content_with_context += " " + cleaned_line
                    current_section_full_text.append(cleaned_line)
        
        if chunks:
            comprehensive_chunks = self.create_comprehensive_chunks(chunks, act_metadata)
            chunks.extend(comprehensive_chunks)
        
        parse_stats["definitions"] = len(definitions)
        
        validation_issues = self.validate_parse_quality(chunks, parse_stats, raw_text)
        
        metadata = {
            **act_metadata,
            "total_chunks": len(chunks),
            "parse_statistics": parse_stats,
            "definition_sections": definitions,
            "cross_reference_map": dict(cross_references),
            "validation_issues": validation_issues
        }
        
        return chunks, metadata
    
    def create_comprehensive_chunks(self, chunks: List[LegalChunk], 
                                    act_metadata: Dict) -> List[LegalChunk]:
        comprehensive = []
        sections = defaultdict(list)
        
        for chunk in chunks:
            if chunk.metadata["type"] in ["section", "sub_section", "clause"]:
                sections[chunk.metadata["dapha_no"]].append(chunk)
        
        for dapha_no, section_chunks in sections.items():
            if len(section_chunks) > 1:
                full_content = "\n".join([c.content for c in section_chunks])
                chunk_id = f"{act_metadata['act_identifier']}_{dapha_no}_full"
                
                chunk = LegalChunk(
                    content=full_content,
                    content_with_context=full_content,
                    metadata={
                        "act_name": act_metadata["act_name"],
                        "act_identifier": act_metadata["act_identifier"],
                        "part": section_chunks[0].metadata["part"],
                        "chapter": section_chunks[0].metadata["chapter"],
                        "dapha_no": dapha_no,
                        "citation": f"{act_metadata['act_name']}, दफा {dapha_no} (पूर्ण)",
                        "page_no": section_chunks[0].metadata["page_no"],
                        "type": "section_comprehensive",
                        "sub_chunk_count": len(section_chunks),
                        "hierarchy_level": 0
                    },
                    chunk_id=chunk_id
                )
                comprehensive.append(chunk)
        
        return comprehensive
    
    def validate_parse_quality(self, chunks: List[LegalChunk], 
                                stats: Dict, raw_text: str) -> List[str]:
        issues = []
        
        if len(chunks) == 0:
            issues.append("CRITICAL: No chunks parsed - file may be empty or unreadable")
            return issues
        
        if len(chunks) < 5:
            issues.append(f"WARNING: Only {len(chunks)} chunks parsed - may indicate parsing issues")
        
        if stats["sections"] == 0:
            issues.append("CRITICAL: No sections found - parsing anchor may be incorrect")
        
        if stats["sections"] > 0 and stats["subsections"] == 0 and stats["clauses"] == 0:
            issues.append("INFO: No subsections or clauses found - may be a simple Act")
        
        if stats["sections"] > 0:
            ratio = (stats["subsections"] + stats["clauses"]) / stats["sections"]
            if ratio < 0.3:
                issues.append(f"WARNING: Low sub-structure ratio ({ratio:.2f}) - may have missed content")
        
        has_nepali = bool(re.search(r'[ऀ-ॿ]', raw_text))
        if not has_nepali:
            issues.append("CRITICAL: No Devanagari text detected - wrong encoding or corrupted file")
        
        return issues

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    parser = NepaliLegalParser()
    
    if not os.path.exists(INPUT_DIR):
        print(f"ERROR: Input directory not found: {INPUT_DIR}")
        return
    
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.txt')]
    
    if not files:
        print(f"ERROR: No .txt files found in {INPUT_DIR}")
        return
    
    all_chunks = []
    all_metadata = []
    parsing_report = []
    
    print(f"Found {len(files)} files to parse\n")
    
    for idx, filename in enumerate(files, 1):
        file_path = os.path.join(INPUT_DIR, filename)
        
        try:
            from urllib.parse import unquote
            display_name = unquote(filename, encoding='utf-8')
        except:
            display_name = filename
        
        print(f"\n[{idx}/{len(files)}] Parsing: {display_name[:60]}...")
        
        try:
            chunks, metadata = parser.parse_act(file_path)
            all_chunks.extend([chunk.to_dict() for chunk in chunks])
            all_metadata.append(metadata)            
            report = {
                "file": filename,
                "decoded_name": display_name,
                "status": "success",
                "chunks": len(chunks),
                "statistics": metadata["parse_statistics"],
                "issues": metadata["validation_issues"]
            }
            parsing_report.append(report)
            
            status = "done" if len(chunks) > 0 else "⚠"
            print(f"  {status} {len(chunks)} chunks | "
                  f"Sections: {metadata['parse_statistics']['sections']} | "
                  f"Subsections: {metadata['parse_statistics']['subsections']} | "
                  f"Clauses: {metadata['parse_statistics']['clauses']}")
            
            if metadata["validation_issues"]:
                for issue in metadata["validation_issues"][:2]:
                    print(f"    ⚠ {issue}")
            
        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
            parsing_report.append({
                "file": filename,
                "decoded_name": display_name,
                "status": "failed",
                "error": str(e)
            })
    
    chunks_file = os.path.join(OUTPUT_DIR, "vidhi_rag_enhanced.json")
    with open(chunks_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    
    metadata_file = os.path.join(OUTPUT_DIR, "acts_metadata.json")
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, ensure_ascii=False, indent=2)
    
    report_file = os.path.join(OUTPUT_DIR, "parsing_report.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(parsing_report, f, ensure_ascii=False, indent=2)
    
    print(f"PARSING COMPLETE")
    print(f"Total chunks indexed: {len(all_chunks)}")
    print(f"Acts processed: {len(all_metadata)}")
    print(f"Successful parses: {sum(1 for r in parsing_report if r['status'] == 'success')}")
    print(f"Failed parses: {sum(1 for r in parsing_report if r['status'] == 'failed')}")
    print(f"Files with warnings: {sum(1 for r in parsing_report if r.get('issues'))}")
    print(f"\nOutput files:")
    print(f"  - Chunks: {chunks_file}")
    print(f"  - Metadata: {metadata_file}")
    print(f"  - Report: {report_file}")

if __name__ == "__main__":
    main()
