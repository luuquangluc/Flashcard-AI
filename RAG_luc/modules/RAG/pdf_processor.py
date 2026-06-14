import fitz  # PyMuPDF
import os
import json
import re
import gc
import tempfile
import uuid
from PIL import Image
from typing import List, Dict, Any, Tuple
from collections import Counter
from difflib import SequenceMatcher

# ================================================================
# TITLES & LEVELS DETECTION
# ================================================================

def _classify_title_level(size, body_size, is_bold, text):
    if size > body_size:
        size_diff = size - body_size
        if size_diff > 6: return 1
        elif size_diff > 3: return 2
        else: return 3
    elif is_bold and size >= body_size:
        return 4
    elif text.isupper() and len(text) > 5:
        return 3
    return 0

# ================================================================
# PDF TYPE DETECTION & EXTRACTION
# ================================================================

def is_scanned_pdf(pdf_path, sample_pages=3):
    doc = fitz.open(pdf_path)
    pages_to_check = min(sample_pages, len(doc))
    
    total_text_len = 0
    total_images = 0
    
    for i in range(pages_to_check):
        page = doc[i]
        text = page.get_text().strip()
        images = page.get_images()
        
        total_text_len += len(text)
        total_images += len(images)
    
    doc.close()
    
    avg_text = total_text_len / pages_to_check
    return avg_text < 50

def extract_titles_digital(pdf_path):
    doc = fitz.open(pdf_path)
    all_lines = []
    font_sizes = []

    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] != 0: continue
            for line in block["lines"]:
                line_text_parts = []
                line_sizes = []
                line_flags = []
                line_fonts = []

                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text: continue
                    font_size = round(span["size"], 1)
                    line_text_parts.append(span["text"])
                    line_sizes.append(font_size)
                    line_flags.append(span["flags"])
                    line_fonts.append(span["font"])
                    font_sizes.append(font_size)

                if not line_text_parts: continue
                full_text = " ".join(line_text_parts).strip()
                dominant_size = Counter(line_sizes).most_common(1)[0][0]
                bold_count = sum(1 for f in line_flags if f & 2**4)
                is_bold = bold_count > len(line_flags) / 2

                all_lines.append({
                    "text": full_text,
                    "size": dominant_size,
                    "is_bold": is_bold,
                    "font": line_fonts[0] if line_fonts else "",
                    "page": page_num + 1,
                })

    if not font_sizes: return []
    body_size = Counter(font_sizes).most_common(1)[0][0]

    titles = []
    for line_info in all_lines:
        level = _classify_title_level(line_info["size"], body_size, line_info["is_bold"], line_info["text"])
        if level > 0 and len(line_info["text"].strip()) > 2:
            titles.append({
                "text": line_info["text"],
                "level": level,
                "page": line_info["page"],
            })

    doc.close()
    return titles

def extract_titles_scanned(pdf_path, tesseract_cmd=None, lang="vie+eng", dpi=100):
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return []

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    doc = fitz.open(pdf_path)
    all_titles = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
        # Optimize: Convert pixmap directly to PIL image (Greyscale) without intermediate PNG encoding
        img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
        custom_config = r'--oem 3 --psm 6'
        tsv_data = pytesseract.image_to_data(img, lang=lang, config=custom_config, output_type=pytesseract.Output.DICT)
        
        lines = {}
        heights = []
        for i in range(len(tsv_data["text"])):
            text = tsv_data["text"][i].strip()
            if not text or int(tsv_data["conf"][i]) < 30: continue
            key = (tsv_data["block_num"][i], tsv_data["par_num"][i], tsv_data["line_num"][i])
            if key not in lines:
                lines[key] = {"words": [], "heights": [], "top": tsv_data["top"][i]}
            lines[key]["words"].append(text)
            lines[key]["heights"].append(tsv_data["height"][i])
            heights.append(tsv_data["height"][i])
        
        if not heights: continue
        avg_h = sum(heights) / len(heights)

        for key, line_data in lines.items():
            l_text = " ".join(line_data["words"])
            l_h = sum(line_data["heights"]) / len(line_data["heights"])
            
            # Simple level logic for now, or use classify_title_scanned if we have layout info
            level = 0
            h_ratio = l_h / avg_h
            if h_ratio > 1.5: level = 1
            elif h_ratio > 1.2: level = 2
            elif l_text.isupper() and len(l_text) > 5: level = 3
            
            if level > 0 and len(l_text) > 3:
                all_titles.append({"text": l_text, "level": level, "page": page_num + 1})

    doc.close()
    return all_titles

def extract_titles_auto(pdf_path, tesseract_cmd=None, dpi=100):
    if is_scanned_pdf(pdf_path):
        return extract_titles_scanned(pdf_path, tesseract_cmd=tesseract_cmd, dpi=dpi)
    else:
        return extract_titles_digital(pdf_path)

# ================================================================
# CHUNKING STRATEGIES
# ================================================================

def chunk_digital_pdf(pdf_path, max_chunk_size=800, min_chunk_size=300, overlap_size=100):
    print(f"  [Digital] Đang phân tích và gộp chunk: {pdf_path}")
    doc = fitz.open(pdf_path)
    
    all_lines = []
    font_sizes = []
    
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] != 0: continue
            for line in block["lines"]:
                line_text_parts = []
                line_sizes = []
                line_flags = []
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text: continue
                    line_text_parts.append(span["text"])
                    line_sizes.append(round(span["size"], 1))
                    line_flags.append(span["flags"])
                    font_sizes.append(round(span["size"], 1))

                if not line_text_parts: continue
                full_text = " ".join(line_text_parts).strip()
                dominant_size = Counter(line_sizes).most_common(1)[0][0]
                bold_count = sum(1 for f in line_flags if f & 2**4)
                is_bold = bold_count > len(line_flags) / 2
                
                # Use the full line bbox instead of just the first span for better coverage
                bbox = line.get("bbox", (0,0,0,0))
                x0, y0, x1, y1 = bbox

                all_lines.append({
                    "text": full_text, "size": dominant_size, "is_bold": is_bold,
                    "page": page_num + 1, "y": y0, "x0": x0, "x1": x1, "x_center": (x0 + x1) / 2,
                    "bbox": [x0, y0, x1, y1]
                })
    
    if not all_lines:
        doc.close()
        return []
        
    # CRITICAL: Sort lines by page then Y coordinate to ensure consecutive physical lines are chunked together.
    # This avoids "holes" caused by non-sequential internal PDF block order.
    all_lines = sorted(all_lines, key=lambda x: (x["page"], x["y"], x["x0"]))
    
    body_size = Counter(font_sizes).most_common(1)[0][0]
    
    all_chunks = []
    current_titles = {}
    buffer_text = []
    buffer_bboxes = []
    buffer_pages = set()
    current_breadcrumb = "Noi dung chung"
    
    def _flush_buffer():
        nonlocal buffer_text, buffer_bboxes, buffer_pages
        if buffer_text:
            raw_text = "\n".join(buffer_text).strip()
            if len(raw_text) > 20:
                all_chunks.append({
                    "raw_text": raw_text,
                    "enriched_text": f"CAU TRUC: {current_breadcrumb}\nNOI DUNG:\n{raw_text}",
                    "breadcrumb": current_breadcrumb,
                    "page": min(buffer_pages) if buffer_pages else 0,
                    "page_list": sorted(list(buffer_pages)) if buffer_pages else [],
                    "bboxes": list(buffer_bboxes),
                    "chunk_index": len(all_chunks)
                })
            
            # Implement overlap
            overlap_accum = []
            overlap_bboxes = []
            overlap_len = 0
            for line, bbox in zip(reversed(buffer_text), reversed(buffer_bboxes)):
                overlap_accum.insert(0, line)
                overlap_bboxes.insert(0, bbox)
                overlap_len += len(line)
                if overlap_len >= overlap_size:
                    break
            buffer_text = overlap_accum
            buffer_bboxes = overlap_bboxes
            buffer_pages = set() # Reset for next chunk

    for i, line_info in enumerate(all_lines):
        text = line_info["text"]

        title_level = _classify_title_level(line_info["size"], body_size, line_info["is_bold"], text)
        current_len = sum(len(t) for t in buffer_text)
        
        if title_level > 0 and len(text.strip()) > 2:
            if title_level <= 2 or current_len >= min_chunk_size:
                _flush_buffer()
            current_titles[title_level] = text
            for lv in [lv for lv in current_titles if lv > title_level]: del current_titles[lv]
            current_breadcrumb = " > ".join([current_titles[lv] for lv in sorted(current_titles.keys())])
            prefix = "#" * title_level if title_level <= 3 else "###"
            buffer_text.append(f"{prefix} {text}")
            buffer_bboxes.append({"p": line_info["page"], "b": line_info["bbox"]})
            buffer_pages.add(line_info["page"])
        else:
            if text.strip():
                buffer_text.append(text)
                buffer_bboxes.append({"p": line_info["page"], "b": line_info["bbox"]})
                buffer_pages.add(line_info["page"])
                current_total = sum(len(t) for t in buffer_text)
                # Smart flush: Nếu đã đạt ngưỡng, ưu tiên cắt tại dấu câu kết thúc
                if current_total >= max_chunk_size:
                    is_sentence_end = text.strip().endswith(('.', '!', '?', ':', ';', '"', '”'))
                    if is_sentence_end or current_total >= max_chunk_size * 1.5:
                        _flush_buffer()

    _flush_buffer()
    doc.close()
    return all_chunks

def chunk_scanned_pdf(pdf_path, max_chunk_size=800, min_chunk_size=300, overlap_size=100, tesseract_cmd=None, dpi=300, vision_processor=None):
    import pytesseract
    from PIL import Image
    print(f"  [Scanned+] OCR + layout detection: {pdf_path}")
    doc = fitz.open(pdf_path)
    all_chunks = []
    current_titles = {}
    buffer_text = []
    buffer_bboxes = []
    buffer_pages = set()
    current_breadcrumb = "Noi dung chung"

    def flush():
        nonlocal buffer_text, buffer_bboxes, buffer_pages
        if buffer_text:
            raw = "\n".join(buffer_text).strip()
            if len(raw) > 20:
                all_chunks.append({
                    "raw_text": raw,
                    "enriched_text": f"CAU TRUC: {current_breadcrumb}\nNOI DUNG:\n{raw}",
                    "breadcrumb": current_breadcrumb,
                    "page": min(buffer_pages) if buffer_pages else 0,
                    "page_list": sorted(list(buffer_pages)) if buffer_pages else [],
                    "chunk_index": len(all_chunks),
                    "bboxes": list(buffer_bboxes)
                })
            
            # Implement overlap
            overlap_accum = []
            overlap_bboxes = []
            overlap_len = 0
            for line, bbox in zip(reversed(buffer_text), reversed(buffer_bboxes)):
                overlap_accum.insert(0, line)
                overlap_bboxes.insert(0, bbox)
                overlap_len += len(line)
                if overlap_len >= overlap_size:
                    break
            buffer_text = overlap_accum
            buffer_bboxes = overlap_bboxes
            buffer_pages = set()

    from concurrent.futures import ThreadPoolExecutor
    import threading
    
    all_chunks = []
    local_temp_dir = os.path.join(os.getcwd(), "temp_ocr")
    os.makedirs(local_temp_dir, exist_ok=True)
    
    def process_single_page(page_num):
        # Open a local document handle for thread-safety
        try:
            with fitz.open(pdf_path) as local_doc:
                page = local_doc[page_num]
                # Generate pixmap
                pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
                temp_img_path = os.path.join(local_temp_dir, f"ocr_tmp_{uuid.uuid4().hex}.png")
                pix.save(temp_img_path)
        except Exception as e:
            print(f"    ❌ Lỗi khi đọc trang {page_num+1}: {e}")
            return None
        
        try:
            # --- STEP 1: LOCAL OCR (Free & Always Done) ---
            tsv = pytesseract.image_to_data(temp_img_path, lang="vie+eng", config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT)
            
            # Count words with decent confidence
            words = [tsv["text"][i] for i in range(len(tsv["text"])) if tsv["text"][i].strip() and int(tsv["conf"][i]) > 30]
            word_count = len(words)
            
            # --- STEP 2: SELECTIVE VISION DECISION ---
            # Heuristic: If word count < 150, it's likely a Slide or Diagram -> Needs Vision
            # If word count >= 150, it's a dense text page -> Tesseract is enough
            should_use_vision = vision_processor and word_count < 150
            
            if should_use_vision:
                print(f"    🌟 [Selective Vision] Page {page_num + 1} is complex ({word_count} words). Calling AI...")
                vision_res = vision_processor.process_slide_hybrid(temp_img_path, dpi=dpi)
                if vision_res and vision_res.get("text"):
                    current_breadcrumb = vision_res.get("metadata", {}).get("title", "Noi dung slide")
                    return {
                        "type": "vision",
                        "page": page_num + 1,
                        "text": vision_res["text"],
                        "breadcrumb": current_breadcrumb,
                        "bboxes": [{"p": page_num + 1, "b": b["b"]} for b in vision_res["bboxes"]]
                    }

            # --- STEP 3: FALLBACK TO TRADITIONAL OCR ---
            return {
                "type": "ocr",
                "page": page_num + 1,
                "tsv": tsv
            }
        finally:
            if os.path.exists(temp_img_path):
                try: os.remove(temp_img_path)
                except: pass
            del pix

    print(f"    🚀 Đang xử lý song song {len(doc)} trang...")
    results = []
    # Giảm xuống 4 workers để cân bằng tốc độ và RAM
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_single_page, range(len(doc))))

    # --- RECONSTRUCT CHUNKS IN ORDER ---
    buffer_text = []
    buffer_bboxes = []
    buffer_pages = set()
    current_titles = {}
    current_breadcrumb = "Noi dung slide"

    def flush():
        nonlocal buffer_text, buffer_bboxes, buffer_pages, current_breadcrumb
        if not buffer_text: return
        
        full_text = " ".join(buffer_text)
        all_chunks.append({
            "raw_text": full_text,
            "enriched_text": f"CAU TRUC: {current_breadcrumb}\nNOI DUNG:\n{full_text}",
            "breadcrumb": current_breadcrumb,
            "page": sorted(list(buffer_pages))[0] if buffer_pages else 0,
            "page_list": sorted(list(buffer_pages)),
            "chunk_index": len(all_chunks),
            "bboxes": buffer_bboxes[:]
        })
        buffer_text = []
        buffer_bboxes = []
        buffer_pages = set()

    for res in results:
        if not res: continue
        page_num = res["page"] - 1
        
        if res["type"] == "vision":
            flush() # Flush any pending OCR text before vision page
            all_chunks.append({
                "raw_text": res["text"],
                "enriched_text": f"CAU TRUC: {res['breadcrumb']}\nNOI DUNG:\n{res['text']}",
                "breadcrumb": res["breadcrumb"],
                "page": page_num + 1,
                "page_list": [page_num + 1],
                "chunk_index": len(all_chunks),
                "bboxes": res["bboxes"]
            })
            # Update breadcrumb for next pages from vision title
            current_breadcrumb = res["breadcrumb"]
            continue

        # Process OCR fallback results
        tsv = res["tsv"]
        lines = {}
        heights = []
        for i in range(len(tsv["text"])):
            txt = tsv["text"][i].strip()
            if not txt or int(tsv["conf"][i]) < 30: continue
            key = (tsv["block_num"][i], tsv["par_num"][i], tsv["line_num"][i])
            if key not in lines:
                lines[key] = {"words": [], "h": [], "x0": tsv["left"][i], "x1": tsv["left"][i] + tsv["width"][i], "y0": tsv["top"][i]}
            lines[key]["words"].append(txt)
            lines[key]["h"].append(tsv["height"][i])
            lines[key]["x0"] = min(lines[key]["x0"], tsv["left"][i])
            lines[key]["x1"] = max(lines[key]["x1"], tsv["left"][i] + tsv["width"][i])
            heights.append(tsv["height"][i])

        if not heights: continue
        avg_h = sum(heights) / len(heights)
        
        # Scale factor: Tesseract pixel coords (dpi) → PDF points (72 DPI)
        scale = 72.0 / dpi
        
        for k in sorted(lines.keys()):
            l = lines[k]
            text = " ".join(l["words"])
            h = sum(l["h"]) / len(l["h"])
            
            h_ratio = h / avg_h
            title_level = 0
            if h_ratio > 1.5: title_level = 1
            elif h_ratio > 1.2: title_level = 2
            elif text.isupper() and len(text) > 5: title_level = 3
            
            title_patterns = [
                r"^(PHẦN\s+[IVX\d]+)", r"^(CHƯƠNG\s+[\d]+|Chương\s+[\d]+)", r"^(MỤC\s+[\d]+|Mục\s+[\d]+)", r"^(Điều\s+[\d]+)",
                r"^(PART\s+[IVX\d]+|Part\s+[IVX\d]+)", r"^(CHAPTER\s+[\d]+|Chapter\s+[\d]+)", r"^(SECTION\s+[\d]+|Section\s+[\d]+)", r"^(ARTICLE\s+[\d]+|Article\s+[\d]+)"
            ]
            for p in title_patterns:
                if re.search(p, text):
                    title_level = max(title_level, 2) if title_level > 0 else 2
                    break
            
            current_len = sum(len(t) for t in buffer_text)

            if title_level > 0 and len(text.strip()) > 3:
                if title_level <= 2 or current_len >= min_chunk_size: flush()
                current_titles[title_level] = text
                for lv in [lv for lv in current_titles if lv > title_level]: del current_titles[lv]
                current_breadcrumb = " > ".join([current_titles[lv] for lv in sorted(current_titles.keys())])
                prefix = "#" * min(title_level, 3)
                buffer_text.append(f"{prefix} {text}")
                buffer_bboxes.append({"p": page_num + 1, "b": [l["x0"] * scale, l["y0"] * scale, l["x1"] * scale, (l["y0"] + h) * scale]})
                buffer_pages.add(page_num + 1)
            else:
                buffer_text.append(text)
                buffer_bboxes.append({"p": page_num + 1, "b": [l["x0"] * scale, l["y0"] * scale, l["x1"] * scale, (l["y0"] + h) * scale]})
                buffer_pages.add(page_num + 1)
                current_total = sum(len(t) for t in buffer_text)
                if current_total >= max_chunk_size:
                    is_sentence_end = text.strip().endswith(('.', '!', '?', ':', ';', '"', '”'))
                    if is_sentence_end or current_total >= max_chunk_size * 1.5:
                        flush()

    flush()
    doc.close()
    print(f"  ✅ Created {len(all_chunks)} chunks (improved scanned)")
    return all_chunks

# ================================================================
# POST-PROCESSING (MERGING)
# ================================================================

def merge_chunk_list(chunks):
    if not chunks: return None
    if len(chunks) == 1: return chunks[0]
    
    # Calculate page range
    all_pages = []
    for c in chunks:
        p = c.get("page")
        if isinstance(p, int): all_pages.append(p)
        elif isinstance(p, str) and "-" in p:
            parts = p.split("-")
            all_pages.extend([int(parts[0]), int(parts[1])])
        elif isinstance(p, str):
            try: all_pages.append(int(p))
            except: pass
            
    min_p = min(all_pages) if all_pages else 0
    max_p = max(all_pages) if all_pages else 0
    page_str = str(min_p) if min_p == max_p else f"{min_p}-{max_p}"
    
    raw_text = "\n\n".join(c["raw_text"] for c in chunks)
    breadcrumb = chunks[0]["breadcrumb"]
    enriched_text = f"CAU TRUC: {breadcrumb} (Trang {page_str})\nNOI DUNG:\n{raw_text}"
    
    merged_bboxes = []
    for c in chunks:
        merged_bboxes.extend(c.get("bboxes", []))
        
    return {
        "raw_text": raw_text, 
        "enriched_text": enriched_text, 
        "breadcrumb": breadcrumb, 
        "page": page_str,
        "page_list": sorted(list(set(all_pages))),
        "chunk_index": chunks[0].get("chunk_index", 0),
        "bboxes": merged_bboxes,
        "original_chunks": chunks
    }

def greedy_merge(chunks, max_size):
    merged = []
    buffer_list = []
    b_len = 0
    for c in chunks:
        if b_len + len(c["raw_text"]) > max_size and buffer_list:
            merged.append(merge_chunk_list(buffer_list))
            buffer_list = []
            b_len = 0
        buffer_list.append(c)
        b_len += len(c["raw_text"])
    if buffer_list: merged.append(merge_chunk_list(buffer_list))
    return merged

def hierarchical_merge(chunks, level_index, max_size):
    if not chunks: return []
    total_len = sum(len(c["raw_text"]) for c in chunks)
    if total_len <= max_size: return [merge_chunk_list(chunks)]
    if level_index > 5: return greedy_merge(chunks, max_size)

    groups = []
    for c in chunks:
        parts = c["breadcrumb"].split(" > ") if c["breadcrumb"] else []
        part = parts[level_index] if level_index < len(parts) else ""
        
        if not groups:
            groups.append([c])
        else:
            prev_group = groups[-1]
            prev_chunk = prev_group[-1] # So sánh với chunk cuối cùng của nhóm trước đó
            
            # Lấy số trang để kiểm tra khoảng cách (lấy trang kết thúc của chunk trước)
            p_prev = prev_chunk.get("page")
            if isinstance(p_prev, str) and "-" in p_prev: p_prev = int(p_prev.split("-")[-1])
            p_curr = c.get("page")
            if isinstance(p_curr, str) and "-" in p_curr: p_curr = int(p_curr.split("-")[0])
            
            # Điều kiện gộp: Khớp breadcrumb VÀ khoảng cách trang <= 1
            is_same_page = (abs(int(p_curr) - int(p_prev)) <= 1) if (p_curr is not None and p_prev is not None) else True
            
            match = False
            if part and prev_chunk["breadcrumb"]:
                prev_parts = prev_chunk["breadcrumb"].split(" > ")
                prev_part = prev_parts[level_index] if level_index < len(prev_parts) else ""
                if prev_part and SequenceMatcher(None, part.lower(), prev_part.lower()).ratio() > 0.6:
                    match = True
            elif part == (prev_chunk["breadcrumb"].split(" > ")[level_index] if level_index < len(prev_chunk["breadcrumb"].split(" > ")) else ""):
                match = True
            
            if match and is_same_page:
                groups[-1].append(c)
            else:
                groups.append([c])

    if len(groups) == 1: return hierarchical_merge(chunks, level_index + 1, max_size)
    result = []
    for sg in groups: result.extend(hierarchical_merge(sg, level_index + 1, max_size))
    return result

def post_process_chunks(chunks, max_size=4000):
    if not chunks: return []
    print("  [Post-Process] Đang áp dụng thuật toán Hierarchical Clustering cho các chunk...")
    merged = hierarchical_merge(chunks, 0, max_size)
    print(f"  [Post-Process] Đã gộp từ {len(chunks)} -> {len(merged)} chunks tối ưu nhất.")
    return merged

def chunk_pdf_auto(pdf_path, max_chunk_size=800, min_chunk_size=300, overlap_size=100, tesseract_cmd=None, dpi=100, vision_processor=None):
    print(f"\n{'='*60}\n  Auto-chunking: {pdf_path}\n{'='*60}")
    if is_scanned_pdf(pdf_path):
        chunks = chunk_scanned_pdf(pdf_path, max_chunk_size, min_chunk_size, overlap_size=overlap_size, tesseract_cmd=tesseract_cmd, dpi=dpi, vision_processor=vision_processor)
    else:
        # Digital PDFs usually don't need Vision API unless they are image-heavy slides
        # But we can enable it if forced. For now, standard digital chunking.
        chunks = chunk_digital_pdf(pdf_path, max_chunk_size, min_chunk_size, overlap_size=overlap_size)
    return post_process_chunks(chunks, max_size=600)
