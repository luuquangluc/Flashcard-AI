import os
import json
import warnings
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas.metrics import faithfulness, answer_relevancy
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

try:
    from modules.RAG.rag_system import RAGSystem
except ImportError:
    from rag_system import RAGSystem

# Khởi tạo mô hình giám khảo (Evaluator)
llm_eval = ChatOpenAI(model="gpt-4o-mini", temperature=0)
emb_eval = OpenAIEmbeddings(model="text-embedding-3-small")

def calculate_custom_relevancy(question, answer, context, llm, embeddings):
    """Tính Answer Relevancy có sử dụng thêm Context để sinh câu hỏi"""
    prompt = f"""Dựa vào Ngữ cảnh (Context) và Câu trả lời (Answer) sau đây, hãy tạo ra 3 câu hỏi giả định ngắn gọn mà câu trả lời này đang cố gắng trả lời.
    Ngữ cảnh: {context}
    Câu trả lời: {answer}
    Trả về danh sách 3 câu hỏi, mỗi câu trên 1 dòng. Không thêm thứ tự hay ký tự đặc biệt."""
    
    try:
        response = llm.invoke(prompt)
        generated_questions = response.content.strip().split('\n')
        generated_questions = [q.strip() for q in generated_questions if q.strip()][:3]
        
        if not generated_questions:
            return 0.0
            
        # Tính vector embedding
        q_emb = embeddings.embed_query(question)
        gen_embs = embeddings.embed_documents(generated_questions)
        
        # Tính Cosine Similarity
        import numpy as np
        from numpy.linalg import norm
        
        def cosine_similarity(a, b):
            return np.dot(a, b) / (norm(a) * norm(b))
            
        similarities = [cosine_similarity(q_emb, gen_emb) for gen_emb in gen_embs]
        return float(np.mean(similarities))
    except Exception as e:
        print(f"  ⚠️ Lỗi tính custom relevancy: {e}")
        return 0.0

def main():
    print("="*60)
    print("🚀 BẮT ĐẦU ĐÁNH GIÁ RAG BẰNG RAGAS (BATCH 50 CARDS)")
    print("="*60)

    rag = RAGSystem()
    
    # 1. Nạp dữ liệu (Xử lý PDF thật)
    print("\n⏳ Đang nạp dữ liệu từ file PDF thật...")
    pdf_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'Thu_gui_nguoi_thi_si_tre_tuoi.pdf')
    
    if os.path.exists(pdf_path):
        rag.process_pdf(pdf_path)
    else:
        print(f"⚠️ Không tìm thấy file {pdf_path}!")
        return

    print("\n⏳ Đang sinh 50 Flashcards từ RAG...")
    
    # 2. Sinh 50 thẻ 1 lần duy nhất
    result_json, context = rag.query("", num_flashcard=50)
    
    rag_results = []
    try:
        data = json.loads(result_json)
        flashcards = data.get("flashcards", [])
        print(f"  ✅ Đã sinh thành công {len(flashcards)} thẻ.")
        
        highlight_matches = 0
        total_cards = len(flashcards)
        
        mismatched_logs = []
        for card in flashcards:
            rag_results.append({
                "question": card.get("question", ""),
                "answer": card.get("answer", ""),
                "contexts": [card.get("context", "")] # Chỉ dùng duy nhất chunk tìm được ở Bước 4
            })
            
            # Tính toán độ chuẩn xác của Highlight (Dùng id_cau_hoi và id_cau_tra_loi)
            id_q = card.get("id_cau_hoi")
            id_a = card.get("id_cau_tra_loi")
            llm_id = card.get("llm_chunk_id")
            
            if id_q == id_a:
                highlight_matches += 1
            else:
                # Thu thập các thẻ bị lệch
                q_text = card.get("question", "")
                ans_text = card.get("answer", "")
                ans_context = card.get("context", "")
                mismatched_logs.append(
                    f"❌ LỆCH HIGHLIGHT:\n"
                    f"❓ Câu hỏi: {q_text}\n"
                    f"🅰️ Câu trả lời: {ans_text}\n"
                    f"👉 Phân tích: Q_chunk={id_q} | Ans_chunk={id_a} | AI_khai_bao={llm_id}\n"
                    f"📄 Nội dung Chunk dùng bôi đậm (Ans_chunk):\n{ans_context}\n"
                    f"{'='*50}\n\n"
                )
                
        # Ghi ra file nếu có lệch
        if mismatched_logs:
            with open("mismatched_highlights.txt", "w", encoding="utf-8") as f:
                f.write(f"📊 TỔNG HỢP CÁC THẺ BỊ LỆCH HIGHLIGHT ({len(mismatched_logs)}/{total_cards})\n")
                f.write("="*60 + "\n\n")
                f.write("".join(mismatched_logs))
            print(f"\n⚠️ Đã phát hiện {len(mismatched_logs)} thẻ bị lệch highlight. Chi tiết đã được ghi vào file: mismatched_highlights.txt")
        else:
            print("\n🎉 Tuyệt vời! 100% thẻ đều trùng khớp highlight!")
                
        highlight_accuracy = highlight_matches / total_cards if total_cards > 0 else 0
    except Exception as e:
        print(f"❌ Lỗi parse JSON: {e}")
        return

    if not rag_results:
        print("⚠️ Không có thẻ nào được sinh ra.")
        return

    # 3. Đóng gói thành EvaluationDataset cho RAGAS
    samples = [
        SingleTurnSample(
            user_input=r["question"],
            response=r["answer"],
            retrieved_contexts=r["contexts"],
        )
        for r in rag_results
    ]
    dataset = EvaluationDataset(samples=samples)

    # 4. Chấm điểm bằng RAGAS (Chỉ tính Faithfulness để giảm chi phí)
    print("\n📐 Đang chấm điểm với RAGAS cho 50 thẻ (Chỉ tính Faithfulness để giảm chi phí)...")
    result = evaluate(
        dataset,
        metrics=[faithfulness],
        llm=llm_eval,
        embeddings=emb_eval
    )

    import numpy as np
    scores = {}
    # Chỉ lấy điểm faithfulness
    raw = result["faithfulness"]
    scores["faithfulness"] = float(np.mean([v for v in raw if v is not None]))
        
    # Lưu danh sách các thẻ bị lỗi Faithfulness (nói điêu/ảo giác)
    faithfulness_scores = result["faithfulness"]
    with open("low_faithfulness.txt", "w", encoding="utf-8") as f:
        f.write("📊 CÁC THẺ CÓ ĐIỂM FAITHFULNESS THẤP (< 0.8)\n")
        f.write("="*60 + "\n\n")
        for i, r in enumerate(rag_results):
            score = faithfulness_scores[i]
            if score is not None and score < 0.8:
                f.write(f"❌ Thẻ {i+1} - Điểm Faithfulness: {score:.4f}\n")
                f.write(f"❓ Câu hỏi: {r['question']}\n")
                f.write(f"🅰️ Câu trả lời: {r['answer']}\n")
                f.write(f"📄 Ngữ cảnh (Context):\n")
                for ctx in r["contexts"]:
                    f.write(f"  - {ctx}\n")
                f.write("="*50 + "\n\n")
    print("  ⚠️ Đã lưu danh sách thẻ bị lỗi Faithfulness vào file: low_faithfulness.txt")
        
    # Đã bỏ qua khâu tính Custom Answer Relevancy để giảm chi phí theo yêu cầu
    pass
        
    # Thêm điểm đo lường Highlight mới
    scores["highlight_accuracy"] = highlight_accuracy

    # 5. In báo cáo
    print("\n" + "="*60)
    print("📊 KẾT QUẢ ĐÁNH GIÁ (RAGAS SCORES CHO 50 THẺ)")
    print("="*60)
    for k, v in scores.items():
        star = ""
        if k == "faithfulness" and v >= 0.8:
            star = " ⭐ (ĐẠT MỤC TIÊU)"
        elif k == "highlight_accuracy" and v >= 0.8:
            star = " ⭐ (HIGHLIGHT CHUẨN)"
        print(f"  {k:20s}: {v:.4f}{star}")

    print("\n✅ Đã hoàn tất Evaluation!")

if __name__ == "__main__":
    main()