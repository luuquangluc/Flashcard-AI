import os
import base64
import json
import pytesseract
from PIL import Image
from openai import OpenAI
import io
import logging

from config.settings import API_PRICES, COST_FILE

logger = logging.getLogger(__name__)

class VisionProcessor:
    def __init__(self, api_key=None, tesseract_cmd=None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        self.cost_file = COST_FILE

    def log_cost(self, model, prompt_tokens, completion_tokens, feature_name="Vision"):
        """Tính toán và lưu chi phí API vào file JSON."""
        prices = {
            "gpt-4o-mini": {"in": 0.15 / 1_000_000, "out": 0.60 / 1_000_000},
            "gpt-4o": {"in": 5.00 / 1_000_000, "out": 15.00 / 1_000_000}
        }
        p = prices.get(model.lower(), {"in": 0, "out": 0})
        cost = (prompt_tokens * p["in"]) + (completion_tokens * p["out"])
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        new_entry = {
            "timestamp": timestamp,
            "feature": feature_name,
            "model": model,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "cost_usd": round(cost, 8)
        }
        
        try:
            logs = []
            if os.path.exists(self.cost_file):
                with open(self.cost_file, "r", encoding="utf-8") as f:
                    try:
                        logs = json.load(f)
                    except:
                        logs = []
            
            logs.append(new_entry)
            
            with open(self.cost_file, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error logging cost to JSON: {e}")
        return cost

    def encode_image_to_base64(self, image_path):
        """Converts an image file to a base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def get_structured_text_vision(self, image_path):
        """Uses GPT-4o-mini Vision to extract structured text from a slide image."""
        if not os.path.exists(image_path):
            logger.error(f"Image path does not exist: {image_path}")
            return None
            
        base64_image = self.encode_image_to_base64(image_path)
        
        system_prompt = """Bạn là một chuyên gia phân tích tài liệu (Document Understanding).
Nhiệm vụ của bạn là chuyển đổi ảnh slide này thành văn bản có cấu trúc (Markdown).

YÊU CẦU CỰC KỲ QUAN TRỌNG:
1. PHÂN TÁCH RẠCH RÒI: Hãy phân tách đâu là nội dung chính (Main Content) và đâu là ghi chú lề/chú thích nhỏ (Marginal Notes/Key Insights).
2. GIỮ NGUYÊN LOGIC: Nếu có sơ đồ (mũi tên), hãy mô tả lại bằng Markdown (ví dụ: A -> B).
3. KHÔNG BỎ SÓT: Tuyệt đối không bỏ sót các đoạn text nhỏ ở góc hoặc bên lề (ví dụ: rào cản, lợi ích).
4. CHUẨN HÓA THUẬT NGỮ: Nếu thấy text có vẻ bị lỗi OCR như "Al" hãy hiểu là "AI", "All Readiness" là "AI Readiness".
5. TRẢ VỀ JSON: Kết quả TRẢ VỀ PHẢI LÀ ĐỊNH DẠNG JSON với cấu trúc sau:
{
  "title": "Tiêu đề slide",
  "main_content": "Nội dung chính dạng Markdown",
  "key_notes": "Các ghi chú lề quan trọng",
  "full_markdown": "Toàn bộ nội dung kết hợp"
}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Hãy phân tích slide này theo yêu cầu."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "low"
                                }
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=1500
            )
            content = response.choices[0].message.content
            # Log cost
            self.log_cost("gpt-4o-mini", response.usage.prompt_tokens, response.usage.completion_tokens, "Vision Understanding")
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error in Vision API: {e}")
            return None

    def get_bboxes_tesseract(self, image_path, dpi=300):
        """Uses Tesseract to get word-level bounding boxes for highlighting."""
        if not os.path.exists(image_path):
            logger.error(f"Image path for Tesseract does not exist: {image_path}")
            return []
        try:
            # Scale factor: pixel coords (dpi) → PDF points (72 DPI)
            scale = 72.0 / dpi
            # PSM 6: Assume a single uniform block of text.
            with Image.open(image_path) as img:
                data = pytesseract.image_to_data(img, lang='vie+eng', config='--oem 3 --psm 6', output_type=pytesseract.Output.DICT)
                bboxes = []
                n_boxes = len(data['level'])
                for i in range(n_boxes):
                    text = data['text'][i].strip()
                    conf = int(data['conf'][i])
                    if text and conf > 30:
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        bboxes.append({
                            "text": text,
                            "b": [x * scale, y * scale, (x + w) * scale, (y + h) * scale]
                        })
                return bboxes
        except Exception as e:
            logger.error(f"Error in Tesseract Bboxes: {e}")
            return []

    def process_slide_hybrid(self, image_path, dpi=300):
        """Hybrid approach: GPT Vision for text, Tesseract for coordinates."""
        structured_data = self.get_structured_text_vision(image_path)
        bboxes = self.get_bboxes_tesseract(image_path, dpi=dpi)
        
        final_markdown = ""
        if structured_data:
            final_markdown = structured_data.get("full_markdown", "")
            # Fallback if full_markdown is missing but others exist
            if not final_markdown:
                final_markdown = f"# {structured_data.get('title', '')}\n\n{structured_data.get('main_content', '')}\n\n### NOTES:\n{structured_data.get('key_notes', '')}"
        
        return {
            "text": final_markdown,
            "bboxes": bboxes,
            "metadata": structured_data
        }
