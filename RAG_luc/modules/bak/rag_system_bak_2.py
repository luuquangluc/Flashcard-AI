"""
Trích xuất tiêu đề từ PDF: Digital PDF vs Scanned PDF
=====================================================

2 cách tiếp cận hoàn toàn khác nhau vì bản chất dữ liệu khác nhau:

- Digital PDF: Có text layer → dùng font metadata (size, bold, flags) để nhận diện tiêu đề
- Scanned PDF: Chỉ có ảnh → phải OCR trước, rồi dùng heuristic hoặc AI để nhận diện

Yêu cầu cài đặt:
    pip install PyMuPDF pytesseract Pillow
    # Với Scanned PDF, cần cài Tesseract OCR:
    # Windows: https://github.com/UB-Mannheim/tesseract/wiki
    # Cài thêm dữ liệu tiếng Việt: tesseract --list-langs → tải vie.traineddata
"""

import fitz  # PyMuPDF
import re
import time
import sys
import json
import os
import chromadb
from collections import Counter
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file up one directory
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

try:
    from langsmith import traceable, wrap_openai
except ImportError:
    def traceable(name=None, run_type=None, **kwargs):
        def decorator(func):
            return func
        return decorator
    def wrap_openai(client):
        return client

# Đảm bảo terminal Windows hỗ trợ tiếng Việt
if sys.platform == "win32":
    import io
    sys.stdin = io.TextIOWrapper(sys.stdin.detach(), encoding='utf-8', errors='replace')
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')


# ================================================================
# CÁCH 1: DIGITAL PDF - Trích xuất tiêu đề bằng Font Metadata
# ================================================================
def extract_titles_digital(pdf_path):
    """
    Trích xuất tiêu đề từ Digital PDF dựa trên thuộc tính font.

    Nguyên lý:
        - Tiêu đề thường có font-size LỚN HƠN body text
        - Tiêu đề thường là BOLD (flag bit 2^4 = 16)
        - Tiêu đề thường là ALL CAPS hoặc bắt đầu bằng số/chữ in hoa

    Cách hoạt động:
        1. Duyệt từng page → lấy từng LINE (gồm nhiều span)
        2. Nhóm các span cùng dòng lại, lấy font-size chính (dominant)
        3. Thu thập tất cả font-size → tìm body_size (size phổ biến nhất)
        4. Các line có size > body_size hoặc có flag bold → là tiêu đề
    """
    doc = fitz.open(pdf_path)

    all_lines = []        # Lưu text đã nhóm theo dòng
    font_sizes = []       # Thu thập tất cả font-size (từ mọi span)

    # --- Bước 1: Thu thập dữ liệu, NHÓM THEO DÒNG ---
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if block["type"] != 0:  # Bỏ qua block ảnh (type=1)
                continue

            for line in block["lines"]:
                line_text_parts = []
                line_sizes = []
                line_flags = []
                line_fonts = []

                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue

                    font_size = round(span["size"], 1)
                    line_text_parts.append(span["text"])  # Giữ nguyên spacing
                    line_sizes.append(font_size)
                    line_flags.append(span["flags"])
                    line_fonts.append(span["font"])
                    font_sizes.append(font_size)

                if not line_text_parts:
                    continue

                # Ghép tất cả span thành 1 dòng hoàn chỉnh
                full_text = " ".join(line_text_parts).strip()
                # Dùng font-size phổ biến nhất trong dòng này (dominant size)
                dominant_size = Counter(line_sizes).most_common(1)[0][0]
                # Dòng được coi là bold nếu đa số span là bold
                bold_count = sum(1 for f in line_flags if f & 2**4)
                is_bold = bold_count > len(line_flags) / 2

                all_lines.append({
                    "text": full_text,
                    "size": dominant_size,
                    "is_bold": is_bold,
                    "font": line_fonts[0] if line_fonts else "",
                    "page": page_num + 1,
                })

    # --- Bước 2: Xác định body font-size (size xuất hiện nhiều nhất) ---
    if not font_sizes:
        return []

    size_counter = Counter(font_sizes)
    body_size = size_counter.most_common(1)[0][0]
    print(f"  Body font-size pho bien nhat: {body_size}")
    print(f"  Phan bo font-size: {size_counter.most_common(10)}")

    # --- Bước 3: Lọc tiêu đề ---
    titles = []
    for line_info in all_lines:
        is_title = False
        level = 0  # Cấp tiêu đề (1 = lớn nhất)

        # Tiêu chí 1: Font-size lớn hơn body
        if line_info["size"] > body_size:
            is_title = True
            size_diff = line_info["size"] - body_size
            if size_diff > 6:
                level = 1  # Tiêu đề cấp 1 (rất lớn)
            elif size_diff > 3:
                level = 2  # Tiêu đề cấp 2
            else:
                level = 3  # Tiêu đề cấp 3

        # Tiêu chí 2: Bold + cùng size body → có thể là tiêu đề phụ
        elif line_info["is_bold"] and line_info["size"] >= body_size:
            is_title = True
            level = 4  # Tiêu đề phụ (bold nhưng cùng size)

        # Tiêu chí 3: ALL CAPS + đủ dài → tiêu đề
        elif line_info["text"].isupper() and len(line_info["text"]) > 5:
            is_title = True
            level = 3

        # Bỏ qua các dòng quá ngắn (nhiễu)
        if is_title and len(line_info["text"].strip()) > 2:
            titles.append({
                "text": line_info["text"],
                "level": level,
                "page": line_info["page"],
                "font_size": line_info["size"],
                "is_bold": line_info["is_bold"],
                "font": line_info["font"],
            })

    doc.close()
    return titles



# ================================================================
# CÁCH 2: SCANNED PDF - Trích xuất tiêu đề bằng OCR + Heuristic
# ================================================================
def extract_titles_scanned(pdf_path, tesseract_cmd=None, lang="vie+eng", dpi=100):
    """
    Trích xuất tiêu đề từ Scanned PDF (PDF dạng ảnh, không có text layer).

    Nguyên lý:
        - Scanned PDF không có font metadata → phải OCR trước
        - Sau khi OCR, dùng Tesseract TSV output để lấy thông tin vị trí + kích thước chữ
        - Dòng có chiều cao chữ lớn hơn trung bình → có khả năng là tiêu đề

    Cách hoạt động:
        1. Render PDF page → ảnh (dùng PyMuPDF)
        2. Chạy OCR bằng Tesseract → lấy TSV data (bao gồm vị trí, kích thước, confidence)
        3. Nhóm các từ thành dòng (cùng line_num)
        4. Phân tích chiều cao trung bình → dòng cao hơn = tiêu đề
    """
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        print("❌ Cần cài đặt: pip install pytesseract Pillow")
        print("   Và cài Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki")
        return []

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    doc = fitz.open(pdf_path)
    all_titles = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # --- Bước 1: Render page thành ảnh ---
        # DPI thấp hơn = nhanh hơn, DPI cao hơn = OCR chính xác hơn
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # --- Bước 2: Chạy OCR và lấy dữ liệu TSV ---
        # TSV chứa: level, page_num, block_num, par_num, line_num, word_num,
        #           left, top, width, height, conf, text
        tsv_data = pytesseract.image_to_data(
            img, lang=lang, output_type=pytesseract.Output.DICT
        )

        # --- Bước 3: Nhóm từ thành dòng ---
        lines = {}  # key = (block_num, par_num, line_num)
        heights = []

        for i in range(len(tsv_data["text"])):
            text = tsv_data["text"][i].strip()
            conf = int(tsv_data["conf"][i])
            height = tsv_data["height"][i]

            if not text or conf < 30:  # Bỏ qua text có confidence thấp
                continue

            key = (
                tsv_data["block_num"][i],
                tsv_data["par_num"][i],
                tsv_data["line_num"][i],
            )

            if key not in lines:
                lines[key] = {"words": [], "heights": [], "top": tsv_data["top"][i]}

            lines[key]["words"].append(text)
            lines[key]["heights"].append(height)
            heights.append(height)

        if not heights:
            continue

        # --- Bước 4: Tính chiều cao trung bình để phân loại ---
        avg_height = sum(heights) / len(heights)

        for key, line_data in lines.items():
            line_text = " ".join(line_data["words"])
            line_avg_height = sum(line_data["heights"]) / len(line_data["heights"])

            is_title = False
            level = 0

            # Tiêu chí 1: Chiều cao chữ lớn hơn trung bình đáng kể
            height_ratio = line_avg_height / avg_height
            if height_ratio > 1.5:
                is_title = True
                level = 1
            elif height_ratio > 1.2:
                is_title = True
                level = 2

            # Tiêu chí 2: ALL CAPS + đủ dài
            if not is_title and line_text.isupper() and len(line_text) > 5:
                is_title = True
                level = 3

            # Tiêu chí 3: Bắt đầu bằng pattern tiêu đề (PHẦN, CHƯƠNG, Điều,...)
            title_patterns = [
                r"^(PHẦN\s+[IVXLCDM\d]+)",
                r"^(CHƯƠNG\s+[\d]+|Chương\s+[\d]+)",
                r"^(MỤC\s+[\d]+|Mục\s+[\d]+)",
                r"^(Điều\s+[\d]+)",
                r"^(PHẦN\s+\d+)",
            ]
            for pattern in title_patterns:
                if re.search(pattern, line_text):
                    is_title = True
                    level = min(level, 2) if level > 0 else 2
                    break

            if is_title and len(line_text) > 3:
                all_titles.append({
                    "text": line_text,
                    "level": level,
                    "page": page_num + 1,
                    "char_height": round(line_avg_height, 1),
                    "height_ratio": round(height_ratio, 2),
                })

    doc.close()
    return all_titles


# ================================================================
# CÁCH 3: TỰ ĐỘNG PHÁT HIỆN loại PDF rồi chọn phương pháp phù hợp
# ================================================================
def is_scanned_pdf(pdf_path, sample_pages=3):
    """
    Kiểm tra PDF là digital hay scanned.
    
    Logic: Nếu các trang đầu có rất ít text nhưng có nhiều ảnh → scanned.
    """
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
    
    # Nếu trung bình mỗi trang có < 50 ký tự text → likely scanned
    avg_text = total_text_len / pages_to_check
    print(f"📋 Trung bình {avg_text:.0f} ký tự/trang, {total_images} ảnh trong {pages_to_check} trang đầu")
    
    return avg_text < 50


def extract_titles_auto(pdf_path, tesseract_cmd=None, dpi=100):
    """
    Tự động chọn phương pháp phù hợp để trích xuất tiêu đề.
    """
    print(f"\n{'='*60}")
    print(f"  Phan tich: {pdf_path}")
    print(f"{'='*60}")
    
    if is_scanned_pdf(pdf_path):
        print("  Phat hien: SCANNED PDF -> Su dung OCR")
        return extract_titles_scanned(pdf_path, tesseract_cmd=tesseract_cmd, dpi=dpi)
    else:
        print("  Phat hien: DIGITAL PDF -> Su dung Font Metadata")
        return extract_titles_digital(pdf_path)


# ================================================================
# HELPER: Phân loại title level từ font size
# ================================================================
def _classify_title_level(size, body_size, is_bold, text):
    """
    Trả về title_level (0 = body text, 1-4 = cấp tiêu đề).
    Dùng chung cho cả chunk_digital_pdf và extract_titles_digital.
    """
    if size > body_size:
        size_diff = size - body_size
        if size_diff > 6:
            return 1
        elif size_diff > 3:
            return 2
        else:
            return 3
    elif is_bold and size >= body_size:
        return 4
    elif text.isupper() and len(text) > 5:
        return 3
    return 0


def _fix_vietnamese_spacing(text):
    # No-op: return text as-is to avoid breaking Vietnamese words
    # The PDF text quality depends on the source document
    return text




def chunk_digital_pdf(pdf_path, max_chunk_size=700, min_chunk_size=400):
    """
    Chunk Digital PDF với chiến lược:
    1. Gom nhiều section nhỏ thành 1 chunk nếu mỗi section quá ít chữ (tốt cho slide).
    2. Bao gồm cả Tiêu đề vào trong nội dung chunk để tăng ngữ cảnh.
    3. Tự động flush khi gặp tiêu đề lớn (Level 1, 2) hoặc đạt max_chunk_size.
    """
    print(f"  [Digital] Đang phân tích và gộp chunk: {pdf_path}")
    doc = fitz.open(pdf_path)
    
    # ---- Bước 1: Thu thập tất cả dòng và font size ----
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
                all_lines.append({"text": full_text, "size": dominant_size, "is_bold": is_bold, "page": page_num + 1})
    
    if not font_sizes:
        doc.close()
        return []
    
    body_size = Counter(font_sizes).most_common(1)[0][0]
    
    # ---- Bước 2: Gom chunk (Greedy Strategy) ----
    all_chunks = []
    current_titles = {}  # key=level, val=text
    
    buffer_text = []      # Buffer chứa text cho chunk hiện tại
    buffer_pages = set()
    current_breadcrumb = "Noi dung chung"
    
    def _flush_buffer():
        nonlocal buffer_text, buffer_pages
        if buffer_text:
            raw_text = "\n".join(buffer_text).strip()
            if len(raw_text) > 20: # Bỏ qua chunk quá ngắn/nhiễu
                all_chunks.append({
                    "raw_text": raw_text,
                    "enriched_text": f"CAU TRUC: {current_breadcrumb}\nNOI DUNG:\n{raw_text}",
                    "breadcrumb": current_breadcrumb,
                    "page": min(buffer_pages) if buffer_pages else 0
                })
            buffer_text = []
            buffer_pages = set()

    for line_info in all_lines:
        text = line_info["text"]
        title_level = _classify_title_level(line_info["size"], body_size, line_info["is_bold"], text)
        
        # Tính toán độ dài hiện tại trong buffer
        current_len = sum(len(t) for t in buffer_text)
        
        if title_level > 0 and len(text.strip()) > 2:
            # Nếu gặp tiêu đề lớn (Lv1, Lv2) HOẶC buffer đã đủ lớn thì flush
            if title_level <= 2 or current_len >= min_chunk_size:
                _flush_buffer()
            
            # Cập nhật cấu trúc tiêu đề
            current_titles[title_level] = text
            for lv in [lv for lv in current_titles if lv > title_level]:
                del current_titles[lv]
            
            sorted_levels = sorted(current_titles.keys())
            current_breadcrumb = " > ".join([current_titles[lv] for lv in sorted_levels])
            
            # Thêm tiêu đề vào nội dung chunk (để AI biết đang đọc đến mục nào)
            prefix = "#" * title_level if title_level <= 3 else "###"
            buffer_text.append(f"{prefix} {text}")
            buffer_pages.add(line_info["page"])
        else:
            # Body text: gom vào buffer
            if text.strip():
                buffer_text.append(text)
                buffer_pages.add(line_info["page"])
                
                # Nếu vượt quá max size thì flush ngay
                if sum(len(t) for t in buffer_text) >= max_chunk_size:
                    _flush_buffer()

    _flush_buffer()
    
    doc.close()
    print(f"  Tạo được {len(all_chunks)} chunks (Greedy merge strategy)")
    return all_chunks





# ================================================================
# CHUNKING 2: SCANNED PDF - Chunk theo cấu trúc OCR + Height
# ================================================================
def chunk_scanned_pdf(pdf_path, max_chunk_size=700, min_chunk_size=400, tesseract_cmd=None, lang="vie+eng", dpi=100):
    """
    Chunk Scanned PDF với logic gom mục nhỏ tương tự Digital.
    """
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        print("  Cần cài đặt: pip install pytesseract Pillow")
        return []
    
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    print(f"  [Scanned] Đang OCR và gộp chunk: {pdf_path}")
    doc = fitz.open(pdf_path)
    
    all_chunks = []
    current_titles = {}
    buffer_text = []
    buffer_pages = set()
    current_breadcrumb = "Noi dung chung"

    def _flush_buffer():
        nonlocal buffer_text, buffer_pages
        if buffer_text:
            raw_text = "\n".join(buffer_text).strip()
            if len(raw_text) > 20:
                all_chunks.append({
                    "raw_text": raw_text,
                    "enriched_text": f"CAU TRUC: {current_breadcrumb}\nNOI DUNG:\n{raw_text}",
                    "breadcrumb": current_breadcrumb,
                    "page": min(buffer_pages) if buffer_pages else 0
                })
            buffer_text = []
            buffer_pages = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        tsv_data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
        
        lines_data = {}
        h_list = []
        for i in range(len(tsv_data["text"])):
            text = tsv_data["text"][i].strip()
            if not text or int(tsv_data["conf"][i]) < 30: continue
            k = (tsv_data["block_num"][i], tsv_data["par_num"][i], tsv_data["line_num"][i])
            if k not in lines_data: lines_data[k] = {"words": [], "h": []}
            lines_data[k]["words"].append(text)
            lines_data[k]["h"].append(tsv_data["height"][i])
            h_list.append(tsv_data["height"][i])
        
        if not h_list: continue
        avg_h = sum(h_list) / len(h_list)
        
        for k in sorted(lines_data.keys()):
            l_text = " ".join(lines_data[k]["words"])
            l_h = sum(lines_data[k]["h"]) / len(lines_data[k]["h"])
            h_ratio = l_h / avg_h
            
            title_level = 0
            if h_ratio > 1.5: title_level = 1
            elif h_ratio > 1.2: title_level = 2
            elif l_text.isupper() and len(l_text) > 5: title_level = 3
            
            title_patterns = [r"^(PHẦN\s+[IVX\d]+)", r"^(CHƯƠNG\s+[\d]+|Chương\s+[\d]+)", r"^(MỤC\s+[\d]+|Mục\s+[\d]+)", r"^(Điều\s+[\d]+)"]
            for p in title_patterns:
                if re.search(p, l_text):
                    title_level = max(title_level, 2) if title_level > 0 else 2
                    break
            
            current_len = sum(len(t) for t in buffer_text)
            
            if title_level > 0 and len(l_text.strip()) > 3:
                if title_level <= 2 or current_len >= min_chunk_size:
                    _flush_buffer()
                
                current_titles[title_level] = l_text
                for lv in [lv for lv in current_titles if lv > title_level]: del current_titles[lv]
                sorted_lv = sorted(current_titles.keys())
                current_breadcrumb = " > ".join([current_titles[lv] for lv in sorted_lv])
                
                prefix = "#" * title_level if title_level <= 3 else "###"
                buffer_text.append(f"{prefix} {l_text}")
                buffer_pages.add(page_num + 1)
            else:
                buffer_text.append(l_text)
                buffer_pages.add(page_num + 1)
                if sum(len(t) for t in buffer_text) >= max_chunk_size:
                    _flush_buffer()
                
    _flush_buffer()
    doc.close()
    print(f"  Tạo được {len(all_chunks)} chunks (Scanned, greedy strategy)")
    return all_chunks




from difflib import SequenceMatcher

def merge_chunk_list(chunks):
    if not chunks: return None
    if len(chunks) == 1:
        return chunks[0]
        
    raw_text = "\n\n".join(c["raw_text"] for c in chunks)
    enriched_text = f"CAU TRUC: {chunks[0]['breadcrumb']}\nNOI DUNG:\n{raw_text}"
    
    return {
        "raw_text": raw_text,
        "enriched_text": enriched_text,
        "breadcrumb": chunks[0]["breadcrumb"],
        "page": chunks[0]["page"]
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
    if buffer_list:
        merged.append(merge_chunk_list(buffer_list))
    return merged

def hierarchical_merge(chunks, level_index, max_size):
    if not chunks: return []
    total_len = sum(len(c["raw_text"]) for c in chunks)
    
    # Base Case: All chunks fit perfectly under the size limit
    if total_len <= max_size:
        return [merge_chunk_list(chunks)]
        
    # Safety Valve: Prevent infinite loop or overly deep hierarchies
    if level_index > 5:
        return greedy_merge(chunks, max_size)

    # Group identical/similar sibling chunks at the current level
    groups = []
    for c in chunks:
        parts = c["breadcrumb"].split(" > ") if c["breadcrumb"] else []
        part = parts[level_index] if level_index < len(parts) else ""
        
        if not groups:
            groups.append([c])
        else:
            prev_chunk = groups[-1][0]
            prev_parts = prev_chunk["breadcrumb"].split(" > ") if prev_chunk["breadcrumb"] else []
            prev_part = prev_parts[level_index] if level_index < len(prev_parts) else ""
            
            if part and prev_part:
                # Similarity requirement >= 0.6 as requested
                if SequenceMatcher(None, part.lower(), prev_part.lower()).ratio() > 0.6:
                    groups[-1].append(c)
                else:
                    groups.append([c])
            elif part == prev_part: # Both are empty string
                groups[-1].append(c)
            else:
                groups.append([c])

    # If all chunks are stuck inside exactly ONE group, we couldn't split them.
    # Therefore, we drill down to the NEXT child level (e.g. from L1 -> L2).
    if len(groups) == 1:
        return hierarchical_merge(chunks, level_index + 1, max_size)
    
    # Process each correctly clustered group independently.
    result = []
    for sg in groups:
        result.extend(hierarchical_merge(sg, level_index + 1, max_size))
        
    return result

def post_process_chunks(chunks, max_size=4000):
    if not chunks:
        return []
    print("  [Post-Process] Đang áp dụng thuật toán Hierarchical Clustering cho các chunk...")
    merged = hierarchical_merge(chunks, 0, max_size)
    print(f"  [Post-Process] Đã gộp từ {len(chunks)} -> {len(merged)} chunks tối ưu nhất.")
    return merged

# ================================================================
# CHUNKING 3: TỰ ĐỘNG - Phát hiện loại PDF rồi chunk phù hợp
# ================================================================
def chunk_pdf_auto(pdf_path, max_chunk_size=700, min_chunk_size=400, tesseract_cmd=None, dpi=100):
    """
    Tự động phát hiện loại PDF (digital/scanned) rồi chunk với chiến lược gộp mục nhỏ.
    
    Returns:
        list[dict] với keys: raw_text, enriched_text, breadcrumb, page
    """
    print(f"\n{'='*60}")
    print(f"  Auto-chunking: {pdf_path}")
    print(f"{'='*60}")
    
    if is_scanned_pdf(pdf_path):
        print("  -> SCANNED PDF -> OCR + Greedy chunking")
        chunks = chunk_scanned_pdf(pdf_path, max_chunk_size, min_chunk_size, tesseract_cmd=tesseract_cmd, dpi=dpi)
    else:
        print("  -> DIGITAL PDF -> Font-metadata Greedy chunking")
        chunks = chunk_digital_pdf(pdf_path, max_chunk_size, min_chunk_size)
        
    return post_process_chunks(chunks, max_size=4000)


# ================================================================
# RAG SYSTEM CLASS
# ================================================================

class RAGSystem:
    def __init__(self, model_name="gpt-4o-mini", answer_model_name="gpt-4o-mini", embedding_model_name="text-embedding-3-small"):
        self.model_name = model_name
        self.answer_model_name = answer_model_name
        self.embedding_model_name = embedding_model_name
        
        # Check API key explicitly
        has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
        self.use_openai_embeddings = has_openai_key
        
        try:
            self.client = wrap_openai(OpenAI())
        except Exception:
            self.client = wrap_openai(OpenAI(api_key="dummy-key"))
            
        if self.use_openai_embeddings:
            print(f"  🔄 Đang cấu hình sử dụng OpenAI Embedding ({self.embedding_model_name})...")
            self.embedding_model = None
        else:
            self.embedding_model_name = "paraphrase-multilingual-MiniLM-L12-v2"
            print(f"  🔄 Không có OPENAI_API_KEY, đang tải mô hình Embedding cục bộ ({self.embedding_model_name})...")
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
        
        self.chroma_client = chromadb.EphemeralClient()
        self.col_titles = self.chroma_client.get_or_create_collection(name="section_titles")
        self.col_content = self.chroma_client.get_or_create_collection(name="section_content")
        
        self.bm25 = None
        self.chunks = []

    def embed_text(self, text):
        if self.use_openai_embeddings:
            try:
                response = self.client.embeddings.create(
                    model=self.embedding_model_name,
                    input=[text]
                )
                return response.data[0].embedding
            except Exception as e:
                print(f"  ⚠️ Lỗi gọi OpenAI Embedding, chuyển sang chạy cục bộ: {e}")
                self.use_openai_embeddings = False
                from sentence_transformers import SentenceTransformer
                if getattr(self, "embedding_model", None) is None:
                    self.embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
                return self.embedding_model.encode(text, normalize_embeddings=True).tolist()
        else:
            from sentence_transformers import SentenceTransformer
            if getattr(self, "embedding_model", None) is None:
                self.embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            return self.embedding_model.encode(text, normalize_embeddings=True).tolist()

    @traceable(name="Process PDF")
    def process_pdf(self, pdf_path, tesseract_cmd=None, dpi=100):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Không tìm thấy file: {pdf_path}")
            
        self.chunks = chunk_pdf_auto(pdf_path, tesseract_cmd=tesseract_cmd, dpi=dpi)
        
        if not self.chunks:
            print("  ⚠️ Không tạo được chunk nào.")
            return False

        # Indexing
        print(f"  🚀 Đang index {len(self.chunks)} chunks vào Dual Collections...")
        for i, item in enumerate(self.chunks):
            self.col_content.add(
                documents=[item["enriched_text"]],
                metadatas=[{"breadcrumb": item["breadcrumb"], "page": item["page"], "raw": item["raw_text"]}],
                embeddings=[self.embed_text(item["enriched_text"])],
                ids=[f"content_{i}"]
            )
            
            self.col_titles.add(
                documents=[item["breadcrumb"]],
                metadatas=[{"breadcrumb": item["breadcrumb"]}],
                embeddings=[self.embed_text(item["breadcrumb"])],
                ids=[f"title_{i}"]
            )

        # Initialize BM25
        try:
            from rank_bm25 import BM25Okapi
            print("\n  🔄 Đang khởi tạo BM25 cho Hybrid Search...")
            tokenized_corpus = [doc["raw_text"].lower().split(" ") for doc in self.chunks]
            self.bm25 = BM25Okapi(tokenized_corpus)
        except ImportError:
            print("\n  ⚠️ rank_bm25 chưa được cài đặt, bỏ qua Hybrid Search.")
            
        return True

    @traceable(name="Detect Intent", run_type="llm")
    def detect_intent(self, query):
        prompt = f"""Phân loại câu hỏi của người dùng vào 1 trong 2 loại:
1. 'STRUCTURE': Hỏi về cấu trúc, mục lục, hoặc nội dung tổng quát của một Chương/Mục/Phần.
2. 'DETAIL': Hỏi về chi tiết, định nghĩa, thông tin cụ thể bên trong văn bản.

Câu hỏi: '{query}'

Trả về DUY NHẤT một từ: STRUCTURE hoặc DETAIL."""
        
        try:
            res = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            label = res.choices[0].message.content.strip().upper()
            return "STRUCTURE" if "STRUCTURE" in label else "DETAIL"
        except Exception as e:
            print(f"  ❌ Lỗi detect_intent: {e}")
            return "DETAIL"

    def reciprocal_rank_fusion(self, dense_ranks, sparse_ranks, k=60):
        scores = {}
        for rank, item_id in enumerate(dense_ranks):
            scores[item_id] = scores.get(item_id, 0) + 1.0 / (rank + k)
        for rank, item_id in enumerate(sparse_ranks):
            scores[item_id] = scores.get(item_id, 0) + 1.0 / (rank + k)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    @traceable(name="Retrieve Context")
    def retrieve_context(self, query, intent="DETAIL", top_n=3):
        context = ""
        if intent == "STRUCTURE":
            print("  🔍 Đang tìm kiếm theo Cấu trúc (Titles)...")
            res_t = self.col_titles.query(query_embeddings=[self.embed_text(query)], n_results=1)
            
            if res_t["metadatas"][0]:
                best_breadcrumb = res_t["metadatas"][0][0]["breadcrumb"]
                print(f"  🎯 Khớp tiêu đề: {best_breadcrumb}")
                
                all_c = self.col_content.get()
                matched_raws = []
                for meta in all_c["metadatas"]:
                    if meta["breadcrumb"] == best_breadcrumb or meta["breadcrumb"].startswith(best_breadcrumb + " >"):
                        matched_raws.append(meta["raw"])
                        
                if matched_raws:
                    context = "\n\n".join(matched_raws)
            else:
                intent = "DETAIL" # Fallback

        if intent == "DETAIL":
            print("  🔍 Đang tìm kiếm theo Chi tiết (Content)...")
            if self.bm25 is not None:
                tokenized_query = query.lower().split(" ")
                bm25_scores = self.bm25.get_scores(tokenized_query)
                sparse_top_idx = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_n*2]
                sparse_ranks = [f"content_{i}" for i in sparse_top_idx]
                
                res_dense = self.col_content.query(query_embeddings=[self.embed_text(query)], n_results=top_n*2)
                dense_ranks = res_dense["ids"][0]
                
                fused = self.reciprocal_rank_fusion(dense_ranks, sparse_ranks)
                best_ids = [x[0] for x in fused[:top_n]]
                
                res_c = self.col_content.get(ids=best_ids)
                id_to_meta = {id_: meta for id_, meta in zip(res_c["ids"], res_c["metadatas"])}
                
                parts = []
                for chunk_id in best_ids:
                    if chunk_id in id_to_meta:
                        meta = id_to_meta[chunk_id]
                        parts.append(f"[{meta['breadcrumb']} - Trang {meta['page']}]:\n{meta['raw']}")
                context = "\n\n".join(parts)
            else:
                res_c = self.col_content.query(query_embeddings=[self.embed_text(query)], n_results=top_n)
                parts = []
                for i in range(len(res_c["documents"][0])):
                    meta = res_c["metadatas"][0][i]
                    parts.append(f"[{meta['breadcrumb']} - Trang {meta['page']}]:\n{meta['raw']}")
                context = "\n\n".join(parts)
        
        return context

    @traceable(name="Generate Flashcards", run_type="llm")
    def generate_flashcards(self, context, num_flashcard=3):
        if not context.strip():
            return "Không có ngữ cảnh để tạo câu hỏi."

        paragraphs = context.split("\n\n")
        parts = []
        cur_part = []
        cur_len = 0
        for p in paragraphs:
            if cur_len + len(p) > 2000 and cur_part:
                parts.append("\n\n".join(cur_part))
                cur_part = []
                cur_len = 0
            cur_part.append(p)
            cur_len += len(p)
        if cur_part: parts.append("\n\n".join(cur_part))

        num_parts = len(parts)
        if num_parts == 0: return "Ngữ cảnh trống."

        allocations = [num_flashcard // num_parts + (1 if i < num_flashcard % num_parts else 0) for i in range(num_parts)]
        all_questions = []

        for idx, (part_text, sub_num) in enumerate(zip(parts, allocations)):
            if sub_num <= 0: continue
            
            system_prompt = f"""<identity>
Bạn là một trợ lý giáo dục AI chuyên về tạo câu hỏi
</identity>

<objective>
Dựa hoàn toàn vào ngữ cảnh được cung cấp trong thẻ <context>, hãy tạo tối đa {sub_num} câu hỏi Flashcard chất lượng cao.
Các câu hỏi phải trải dài qua 3 cấp độ tư duy: Nhận biết, Thông hiểu và Vận dụng.
</objective>

<definitions>
<Nhận biết>
Nhắc lại hoặc nhận diện các thông tin, dữ liệu, định nghĩa, quy tắc đã học mà không cần giải thích thêm.
</Nhận biết>
<Thông hiểu>
Khả năng hiểu ý nghĩa tài liệu, có thể tóm tắt, diễn giải hoặc giải thích dữ liệu theo cách hiểu cá nhân.
</Thông hiểu>
<Vận dụng>
Sử dụng kiến thức đã học để giải quyết một vấn đề trong tình huống mới hoặc cụ thể.
</Vận dụng>
</definitions>

<constraints>
1. CHỈ sử dụng thông tin từ <context>. KHÔNG tự ý thêm kiến thức bên ngoài.
2. Ngôn ngữ: Tiếng Việt.
3. Phong cách: Câu hỏi ngắn gọn, trọng tâm, phù hợp làm Flashcard.
4. Số lượng: Tối đa {sub_num} câu hỏi.
5. Luôn trả về JSON tương tự mẫu, ngẫu nhiên với 3 cấp độ tư duy.
</constraints>

<output_format>
Trả về kết quả DUY NHẤT ở định dạng JSON theo mẫu:
{{
  "questions": [
    {{"level": "Nhận biết", "question": "..."}},
  ]
}}
</output_format>"""
            
            user_prompt = f"""<context>
{part_text}
</context>
<task>Hãy tạo tối đa {sub_num} câu hỏi dựa trên ngữ cảnh trên.</task>"""

            try:
                print(f"    ⏳ Đang gọi LLM (Phần {idx + 1}/{num_parts})...")
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                parsed = json.loads(response.choices[0].message.content)
                if "questions" in parsed:
                    all_questions.extend(parsed["questions"])
            except Exception as e:
                print(f"    ❌ Lỗi LLM: {e}")

        return json.dumps({"questions": all_questions}, ensure_ascii=False, indent=2)

    @traceable(name="RAG Query")
    def query(self, query):
        intent = self.detect_intent(query)
        print(f"  🧠 Intent detected: {intent}")
        
        context = self.retrieve_context(query, intent=intent)
        if not context:
            return "Không tìm thấy ngữ cảnh phù hợp.", ""
            
        print(f"\n📄 NGỮ CẢNH ({intent}):\n" + "-"*30 + f"\n{context[:500]}..." + "\n" + "-"*30)
        
        print("\n🧠 Đang tạo Flashcards...")
        flashcards = self.generate_flashcards(context)
        return flashcards, context


# ================================================================
# Main: Sandbox / Test
# ================================================================
if __name__ == "__main__":
    pdf_path = os.path.join(os.path.dirname(__file__), "De_cuong_duong_loi.pdf")
    
    rag = RAGSystem()
    if rag.process_pdf(pdf_path):
        print("\n" + "="*50)
        print("📑 CẤU TRÚC ĐÃ TRÍCH XUẤT:")
        seen_bc = set()
        for chunk in rag.chunks:
            bc = chunk.get("breadcrumb", "Không có tiêu đề")
            if bc not in seen_bc:
                print(f"  - {bc}")
                seen_bc.add(bc)
        print("="*50)

        while True:
            try:
                print("\n" + "-"*50)
                user_query = input("Nhap cau hoi (hoac 'exit' de thoat): ").strip()
                if not user_query or user_query.lower() in ['exit', 'quit', 'q']: break
                
                result, context = rag.query(user_query)
                print("\n✨ KẾT QUẢ FLASHCARDS:")
                print(result)
            except EOFError: break
            except Exception as e:
                print(f"❌ Lỗi: {e}")

