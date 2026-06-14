import fitz  # PyMuPDF
import re
import io
from collections import Counter
from difflib import SequenceMatcher

# ================================================================
# TITLES & LEVELS DETECTION
# ================================================================

def detect_numbering_level(text):
    text = text.strip()
    patterns = [
        # --- Numeric hierarchy ---
        # (r"^\d+\.\d+\.\d+", 3),   # 1.1.1
        # (r"^\d+\.\d+", 2),        # 1.1
        # (r"^\d+[\.\)]", 1),       # 1. or 1)

        # --- Vietnamese ---
        (r"^(CHƯƠNG|Chương)\s+\d+", 1),
        (r"^(MỤC|Mục)\s+\d+", 2),
        (r"^(PHẦN|Phần)\s+[IVX\d]+", 1),
        (r"^(ĐIỀU|Điều)\s+\d+", 2),

        # --- English ---
        (r"^(CHAPTER)\s+\d+", 1),
        (r"^(SECTION)\s+\d+(\.\d+)?", 2),
        (r"^(PART)\s+[IVX\d]+", 1),
        (r"^(ARTICLE)\s+\d+", 2),

        # --- Roman numerals ---
        # (r"^[IVXLC]+\.", 1),

        # --- Alphabet ---
        # (r"^[A-Z]\.", 2),
        # (r"^[a-z]\)", 3),

        # --- Common EN headings ---
        (r"^(INTRODUCTION|CONCLUSION|SUMMARY|ABSTRACT|OVERVIEW)$", 1),
    ]

    for pattern, level in patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return level

    # --- Bonus: Title Case English ---
    if text.istitle() and len(text.split()) <= 6:
        return 3

    return 0

def _classify_title_level(size, body_size, is_bold, text, spacing_boost=0):
    score = 0

    # Font size
    if size > body_size:
        diff = size - body_size
        if diff > 6:
            score += 3
        elif diff > 3:
            score += 2
        else:
            score += 1

    # Bold
    if is_bold:
        score += 1

    # ALL CAPS
    if text.isupper() and len(text) > 5:
        score += 1

    # Numbering
    num_level = detect_numbering_level(text)
    if num_level > 0:
        score += 3

    # Spacing
    score += spacing_boost

    # --- Decision ---
    if score < 3:
        return 0

    if num_level > 0:
        return num_level

    if size > body_size:
        diff = size - body_size
        if diff > 6:
            return 1
        elif diff > 3:
            return 2
        else:
            return 3

    return 4

def classify_title_scanned(line, avg_h, page_width, page_height):
    text = line["text"]
    h = line["h"]
    x0, x1 = line["x0"], line["x1"]
    y0 = line["y0"]
    score = 0

    # --- 1. Numbering override ---
    num_level = detect_numbering_level(text)
    if num_level > 0:
        score += 3
        # return num_level


    # --- 2. Height (font giả lập) ---
    h_ratio = h / avg_h
    if h_ratio > 1.5:
        score += 3
    elif h_ratio > 1.2:
        score += 2
    elif h_ratio > 1.05:
        score += 1

    # --- 3. ALL CAPS ---
    if text.isupper() and len(text) > 5:
        score += 1

    # --- 4. Center alignment ---
    center_x = (x0 + x1) / 2
    if abs(center_x - page_width / 2) < page_width * 0.15:
        score += 1

    # --- 5. Top of page ---
    if y0 < page_height * 0.25:
        score += 1

    # --- 6. Title Case (English) ---
    if text.istitle() and len(text.split()) <= 6:
        score += 1

    # --- 7. Length penalty ---
    if len(text.split()) > 12:
        score -= 2

    # --- Decision ---
    if score < 3:
        return 0

    if h_ratio > 1.5:
        return 1
    elif h_ratio > 1.2:
        return 2
    else:
        return 3

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

    prev_y = None
    for i, line_info in enumerate(all_lines):
        text = line_info["text"]
        spacing_boost = 0
        layout_boost = 0
        current_y = line_info.get("y", None)
        if prev_y is not None and current_y is not None:
            if abs(current_y - prev_y) > 15: spacing_boost += 1
        if i < len(all_lines) - 1:
            next_y = all_lines[i+1].get("y", None)
            if current_y is not None and next_y is not None:
                if abs(next_y - current_y) > 15: spacing_boost += 1
        prev_y = current_y

        if len(text.split()) <= 8: layout_boost += 1
        if len(text.split()) <= 5 and text.isupper(): layout_boost += 2
        if 200 < line_info.get("x_center", 0) < 400: layout_boost += 1

        title_level = _classify_title_level(line_info["size"], body_size, line_info["is_bold"], text, spacing_boost + layout_boost)
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
                if sum(len(t) for t in buffer_text) >= max_chunk_size: _flush_buffer()

    _flush_buffer()
    doc.close()
    return all_chunks

def chunk_scanned_pdf(pdf_path, max_chunk_size=800, min_chunk_size=300, overlap_size=100, tesseract_cmd=None, dpi=300):
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

    for page_num in range(len(doc)):
        print(f"    📄 Processing OCR for page {page_num + 1}/{len(doc)}...")
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
        # Optimize: Convert pixmap directly to PIL image (Greyscale) without intermediate PNG encoding
        img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
        tsv = pytesseract.image_to_data(img, lang="vie+eng", config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT)
        
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
        page_width, page_height = page.rect.width, page.rect.height

        for k in sorted(lines.keys()):
            l = lines[k]
            text = " ".join(l["words"])
            h = sum(l["h"]) / len(l["h"])
            line_info = {"text": text, "h": h, "x0": l["x0"], "x1": l["x1"], "y0": l["y0"]}
            title_level = classify_title_scanned(line_info, avg_h, page_width, page_height)
            current_len = sum(len(t) for t in buffer_text)

            if title_level > 0 and len(text.strip()) > 3:
                if title_level <= 2 or current_len >= min_chunk_size: flush()
                current_titles[title_level] = text
                for lv in [lv for lv in current_titles if lv > title_level]: del current_titles[lv]
                current_breadcrumb = " > ".join([current_titles[lv] for lv in sorted(current_titles.keys())])
                prefix = "#" * min(title_level, 3)
                buffer_text.append(f"{prefix} {text}")
                buffer_bboxes.append({"p": page_num + 1, "b": [l["x0"], l["y0"], l["x1"], l["y0"] + h]})
                buffer_pages.add(page_num + 1)
            else:
                buffer_text.append(text)
                buffer_bboxes.append({"p": page_num + 1, "b": [l["x0"], l["y0"], l["x1"], l["y0"] + h]})
                buffer_pages.add(page_num + 1)
                if sum(len(t) for t in buffer_text) >= max_chunk_size: flush()

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

def chunk_pdf_auto(pdf_path, max_chunk_size=800, min_chunk_size=300, overlap_size=100, tesseract_cmd=None, dpi=100):
    print(f"\n{'='*60}\n  Auto-chunking: {pdf_path}\n{'='*60}")
    if is_scanned_pdf(pdf_path):
        chunks = chunk_scanned_pdf(pdf_path, max_chunk_size, min_chunk_size, overlap_size=overlap_size, tesseract_cmd=tesseract_cmd, dpi=dpi)
    else:
        chunks = chunk_digital_pdf(pdf_path, max_chunk_size, min_chunk_size, overlap_size=overlap_size)
    return post_process_chunks(chunks, max_size=4000)
