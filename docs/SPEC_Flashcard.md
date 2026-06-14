# SPEC – Flashcard AI

**Phiên bản:** 1.0  
**Sản phẩm:** Flashcard AI  
**Loại sản phẩm AI:** AI Copilot / AI Augmentation  
**Mục tiêu:** Giúp người học biến tài liệu học tập thành bộ flashcard chất lượng, có thể kiểm chứng nguồn, chỉnh sửa và học lặp lại theo lịch.

---

## 0. Tóm tắt sản phẩm

**Flashcard AI** là nền tảng học tập thông minh cho phép học sinh, sinh viên, giáo viên và người tự học tải lên tài liệu như PDF, slide, ghi chú, sách giáo khoa, đề cương ôn thi hoặc văn bản thô. Hệ thống sử dụng AI để phân tích nội dung, nhận diện ý chính, tạo câu hỏi – câu trả lời dạng flashcard và hỗ trợ người dùng ôn tập hiệu quả hơn.

Thay vì người dùng phải đọc toàn bộ tài liệu, tự chọn ý chính, tự đặt câu hỏi và tự soạn câu trả lời, Flashcard AI đóng vai trò như một **trợ lý học tập**. AI tạo bản nháp flashcard ban đầu, còn người dùng có quyền kiểm tra nguồn, chỉnh sửa, chấp nhận, xóa hoặc yêu cầu tạo lại. Vì vậy, sản phẩm không thay thế hoàn toàn người học mà giúp người học tiết kiệm thời gian và tổ chức kiến thức tốt hơn.

### One-line pitch

> **Flashcard AI biến tài liệu học tập thành flashcard thông minh trong vài giây, giúp người học tiết kiệm thời gian, ghi nhớ tốt hơn và kiểm soát chất lượng nội dung bằng phản hồi của chính mình.**

---

## 1. Problem Statement

Người dùng thường mất nhiều thời gian khi tự tạo flashcard thủ công. Quy trình thông thường gồm: đọc tài liệu, xác định ý chính, nghĩ câu hỏi, viết câu trả lời, kiểm tra lại nội dung và sắp xếp thẻ để học. Với tài liệu dài như slide bài giảng, sách giáo khoa, đề cương ôn thi hoặc PDF chuyên ngành, quá trình này có thể kéo dài nhiều giờ.

Bên cạnh đó, người dùng dễ gặp hai vấn đề chính:

1. **Tạo flashcard không đều giữa các phần kiến thức.**  
   Người dùng có xu hướng tập trung quá nhiều vào một số phần mình thấy quan trọng hoặc dễ hiểu, dẫn đến việc tạo quá nhiều thẻ cho một phần, trong khi các phần khác bị bỏ sót.

2. **Khó chuyển kiến thức thành câu hỏi – đáp án chất lượng.**  
   Không phải người học nào cũng biết cách biến nội dung trong tài liệu thành flashcard ngắn gọn, đúng trọng tâm, dễ ôn tập và phù hợp với mục tiêu học.

Do đó, Flashcard AI được xây dựng để giải quyết bài toán: **làm thế nào giúp người dùng tạo flashcard nhanh hơn, đầy đủ hơn, chính xác hơn và vẫn giữ quyền kiểm soát chất lượng nội dung?**

---

## 2. Target Users

### 2.1. Người dùng chính

| Nhóm người dùng | Nhu cầu chính | Ví dụ tình huống sử dụng |
|---|---|---|
| Học sinh, sinh viên | Tạo flashcard từ tài liệu học tập, slide, đề cương ôn thi | Sinh viên tải slide môn Quản trị dữ liệu để tạo bộ câu hỏi ôn thi |
| Người tự học | Hệ thống hóa kiến thức từ sách, khóa học, bài viết | Người học tiếng Anh tạo flashcard từ danh sách từ vựng hoặc bài đọc |
| Người luyện thi | Ôn tập theo chủ đề, chương, dạng câu hỏi | Người luyện IELTS/TOEIC tạo flashcard từ tài liệu từ vựng hoặc ngữ pháp |
| Giáo viên, trợ giảng | Tạo bộ câu hỏi nhanh để hỗ trợ học sinh ôn tập | Giáo viên tải bài giảng PDF và tạo bộ flashcard cho lớp |
| Nhân viên cần học kiến thức nội bộ | Ghi nhớ quy trình, thuật ngữ, chính sách, tài liệu đào tạo | Nhân viên mới tạo flashcard từ tài liệu onboarding |

### 2.2. Người dùng ưu tiên trong MVP

Trong giai đoạn MVP, sản phẩm nên tập trung vào **học sinh, sinh viên và người tự học**, vì đây là nhóm có nhu cầu tạo flashcard thường xuyên, có tài liệu đầu vào rõ ràng và dễ đưa ra phản hồi trực tiếp về chất lượng flashcard.

---

## 3. Pain Points

| Pain Point | Mô tả chi tiết | Tác động |
|---|---|---|
| Tốn thời gian tạo flashcard thủ công | Người dùng phải đọc, chọn ý, đặt câu hỏi, viết câu trả lời và kiểm tra lại từng thẻ | Giảm động lực học, mất nhiều thời gian trước khi bắt đầu ôn tập |
| Khó xác định ý chính từ tài liệu dài | Tài liệu có nhiều chương, nhiều khái niệm, nhiều ví dụ và thông tin phụ | Flashcard dễ bị thiếu ý hoặc lan man |
| Mất cân bằng nội dung | Một số phần được tạo quá nhiều thẻ, phần khác bị bỏ sót | Bộ flashcard không bao phủ đầy đủ kiến thức |
| Chất lượng câu hỏi không ổn định | Câu hỏi có thể quá dài, quá dễ, quá khó hoặc không đúng trọng tâm | Hiệu quả ghi nhớ thấp |
| Khó kiểm chứng nội dung | Người dùng không biết flashcard được tạo từ phần nào trong tài liệu | Giảm niềm tin vào AI |
| Thiếu cơ chế học lại có hệ thống | Người dùng tạo thẻ xong nhưng không có lịch ôn tập phù hợp | Khả năng ghi nhớ dài hạn chưa cao |

---

## 4. Value Proposition

Flashcard AI mang lại giá trị cho người dùng thông qua 5 điểm chính:

1. **Tiết kiệm thời gian:** giảm đáng kể thời gian tạo flashcard so với thao tác thủ công.
2. **Bao phủ kiến thức tốt hơn:** AI có thể quét toàn bộ tài liệu, nhận diện các ý chính và đề xuất flashcard theo từng phần.
3. **Tăng chất lượng học tập:** flashcard được trình bày ngắn gọn, theo cặp câu hỏi – đáp án, phù hợp với việc ôn tập chủ động.
4. **Có thể kiểm chứng:** mỗi flashcard nên gắn với nguồn trích dẫn hoặc đoạn nội dung gốc để người dùng kiểm tra khi cần.
5. **Học hỏi từ phản hồi:** hệ thống ghi nhận hành động Accept, Edit, Regenerate, Delete, Like/Dislike để cải thiện chất lượng về sau.

---

## 5. AI Product Canvas

| Thành phần | Nội dung |
|---|---|
| **User** | Người thường xuyên học từ tài liệu dài, cần tạo flashcard để ghi nhớ và ôn tập. Nhóm chính trong MVP là học sinh, sinh viên và người tự học. |
| **Pain** | Tốn thời gian tạo flashcard thủ công, khó chọn ý chính, dễ bỏ sót nội dung, khó kiểm chứng độ chính xác của flashcard. |
| **AI Solution** | AI phân tích tài liệu, trích xuất ý chính, tạo câu hỏi – câu trả lời dạng flashcard, gắn nguồn trích dẫn và cho phép người dùng chỉnh sửa. |
| **Value** | Giảm thời gian tạo flashcard, tăng mức độ bao phủ kiến thức, hỗ trợ học tập chủ động và tăng hiệu quả ghi nhớ. |
| **Trust** | Có nút xem nguồn, hiển thị confidence khi cần, cho phép Edit/Regenerate/Delete, thu thập phản hồi và lưu lịch sử chỉnh sửa. |
| **Feasibility** | Có thể xây dựng bằng LLM kết hợp RAG, OCR, chunking tài liệu, vector database và giao diện web. MVP nên giới hạn loại file, dung lượng và số lượng flashcard mỗi lần tạo. |
| **Business Impact** | Tăng mức độ sử dụng sản phẩm, cải thiện retention, tạo lợi thế dữ liệu từ phản hồi người dùng và có thể mở rộng sang gói trả phí. |

---

## 6. Automation hay Augmentation?

**Lựa chọn:** Augmentation.

Flashcard AI không nên được thiết kế như một hệ thống tự động hoàn toàn, vì nội dung học tập có thể ảnh hưởng trực tiếp đến kết quả học của người dùng. Nếu AI tạo sai hoặc diễn giải thiếu chính xác, người dùng có thể học nhầm kiến thức.

Vì vậy, AI nên đóng vai trò **trợ lý tạo bản nháp flashcard**. Người dùng vẫn là người ra quyết định cuối cùng thông qua các hành động:

- **Accept / Save:** chấp nhận flashcard.
- **Edit:** chỉnh sửa câu hỏi hoặc câu trả lời.
- **Regenerate:** yêu cầu AI tạo lại.
- **Delete:** xóa thẻ không phù hợp.
- **View Source:** xem đoạn tài liệu gốc liên quan.
- **Like / Dislike:** đánh giá chất lượng.
- **Report Error:** báo lỗi nghiêm trọng.

### Lý do chọn Augmentation

- Giảm rủi ro người dùng học sai kiến thức.
- Tăng niềm tin vì người dùng có thể kiểm chứng nguồn.
- Tạo dữ liệu phản hồi chất lượng để cải thiện sản phẩm.
- Phù hợp với chiến lược recall-first: AI có thể tạo nhiều thẻ bao phủ kiến thức, sau đó người dùng chọn lọc và chỉnh sửa.

---

## 7. Core User Flow

### 7.1. Luồng tạo flashcard cơ bản

1. Người dùng đăng nhập vào Flashcard AI.
2. Người dùng chọn chức năng **Tạo thẻ**.
3. Người dùng tải lên tài liệu PDF/slide/văn bản hoặc chọn tài liệu từ thư viện.
4. Hệ thống kiểm tra định dạng, dung lượng và chất lượng tài liệu.
5. Hệ thống trích xuất văn bản từ tài liệu.
6. Tài liệu được chia thành các đoạn nhỏ theo chương, trang hoặc chủ đề.
7. AI nhận diện ý chính và tạo bộ flashcard.
8. Hệ thống hiển thị flashcard kèm nguồn tham chiếu.
9. Người dùng Accept, Edit, Regenerate, Delete hoặc View Source.
10. Người dùng lưu bộ flashcard vào thư viện.
11. Người dùng học bằng chế độ lật thẻ, quiz hoặc spaced repetition.

### 7.2. Luồng xử lý phản hồi

```text
User Action
→ Feedback Button
→ Correction Logs
→ Data Processing & Analysis
→ Admin Review nếu cần
→ Prompt Optimization / Retrieval Optimization
→ Model Evaluation
→ Deploy Improved Version
```

---

## 8. Feature Scope

### 8.1. In-scope cho MVP

| Tính năng | Mô tả | Ưu tiên |
|---|---|---|
| Upload PDF | Người dùng tải file PDF để tạo flashcard | Must-have |
| Nhập văn bản thủ công | Người dùng dán nội dung văn bản | Must-have |
| Tạo flashcard theo chủ đề | Người dùng nhập chủ đề hoặc phạm vi muốn tạo | Must-have |
| Tạo flashcard theo khoảng trang | Người dùng chọn trang bắt đầu và kết thúc | Should-have |
| Hiển thị source | Mỗi flashcard có nguồn trích dẫn từ tài liệu | Must-have |
| Edit flashcard | Người dùng chỉnh sửa câu hỏi/câu trả lời | Must-have |
| Regenerate flashcard | Tạo lại thẻ hoặc cả bộ thẻ | Must-have |
| Delete flashcard | Xóa thẻ không phù hợp | Must-have |
| Save deck | Lưu bộ flashcard vào thư viện | Must-have |
| Like/Dislike | Thu thập phản hồi nhanh | Should-have |
| Thống kê cơ bản | Số thẻ đã tạo, tỷ lệ chấp nhận, thời gian học | Should-have |

### 8.2. Out-of-scope cho MVP

| Tính năng | Lý do chưa ưu tiên |
|---|---|
| Fine-tune model riêng | Cần nhiều dữ liệu chất lượng, chưa phù hợp giai đoạn đầu |
| Tạo flashcard từ video dài | Cần xử lý audio/transcript phức tạp hơn |
| Học nhóm / chia sẻ lớp học | Có thể bổ sung sau khi core flow ổn định |
| Game hóa nâng cao | Nên triển khai sau khi chất lượng flashcard đạt ngưỡng |
| Cá nhân hóa sâu theo năng lực | Cần dữ liệu học tập dài hạn |

---

## 9. User Stories – 4 Paths

### Feature: Tạo flashcard từ tài liệu bằng AI

**Trigger:** Người dùng tải tài liệu lên hoặc nhập nội dung học tập, sau đó yêu cầu AI tạo flashcard.

| Path | Mô tả | Hành vi hệ thống | Hành động người dùng | Kết quả |
|---|---|---|---|---|
| **Happy Path – AI đúng và tự tin** | AI tạo flashcard chính xác, đầy đủ, bám sát tài liệu | Hiển thị bộ flashcard, confidence cao, có source | Người dùng Accept/Save và bắt đầu học | Bộ flashcard được lưu, feedback tích cực được ghi nhận |
| **Low-confidence Path – AI không chắc** | AI tạo được thẻ nhưng một số nội dung có độ tin cậy thấp | Gắn nhãn “Cần xem lại”, hiển thị source rõ hơn | Người dùng View Source, Edit hoặc Regenerate | Hệ thống ghi nhận thẻ cần cải thiện |
| **Failure Path – AI sai** | Flashcard sai, thiếu nguồn hoặc diễn giải không đúng | Cho phép Report Error, Regenerate, Delete | Người dùng báo lỗi hoặc xóa thẻ | Lỗi được lưu vào correction logs |
| **Correction Path – Người dùng chỉnh sửa** | Người dùng sửa câu hỏi/câu trả lời để phù hợp hơn | Lưu phiên bản trước và sau chỉnh sửa | Người dùng Save phiên bản đã chỉnh | Dữ liệu chỉnh sửa được dùng để cải thiện prompt/eval |

---

## 10. Learning Signals

### 10.1. Tín hiệu hệ thống cần thu thập

| Signal | Cách thu thập | Ý nghĩa | Red Flag |
|---|---|---|---|
| Acceptance Rate | Tỷ lệ thẻ được Accept/Save | Đo mức độ phù hợp của flashcard | Giảm dưới 65% trong 1 tuần |
| Edit Rate | Tỷ lệ thẻ bị chỉnh sửa | Đo mức độ cần can thiệp của người dùng | Trên 35% trong 1 tuần |
| Regeneration Rate | Tỷ lệ yêu cầu tạo lại | Đo mức độ không hài lòng với kết quả ban đầu | Trên 30% trong 1 tuần |
| Deletion Rate | Tỷ lệ thẻ bị xóa | Đo mức độ không hữu ích | Trên 20% trong 1 tuần |
| Like/Dislike Ratio | Phản hồi nhanh sau khi tạo | Đo cảm nhận người dùng | Like ratio dưới 60% |
| Source View Rate | Tỷ lệ người dùng mở nguồn | Đo nhu cầu kiểm chứng | Tăng đột biến có thể báo hiệu thiếu tin tưởng |
| Report Error Rate | Lỗi nghiêm trọng do người dùng báo cáo | Đo chất lượng và độ an toàn | Trên 10% trong 1 tuần |
| Time to Accept | Thời gian từ lúc xem đến lúc chấp nhận | Đo độ rõ ràng và tin cậy | Tăng mạnh theo thời gian |
| Latency | Thời gian tạo flashcard | Đo trải nghiệm kỹ thuật | Trên 8 giây với tài liệu ngắn |
| CSAT | Khảo sát hài lòng | Đo cảm nhận tổng thể | Dưới 4.0/5 |

### 10.2. User correction đi vào đâu?

Các chỉnh sửa của người dùng không nên dùng trực tiếp để fine-tune ngay lập tức. Thay vào đó, nên đi qua pipeline kiểm soát chất lượng:

```text
User Edit / Report Error
→ Correction Logs
→ Deduplication & Cleaning
→ Labeling / Admin Review
→ Evaluation Dataset Update
→ Prompt & Retrieval Improvement
→ Optional Fine-tuning khi đủ dữ liệu
```

### 10.3. Dữ liệu nào có giá trị cao nhất?

1. **Edit before/after:** cho biết AI sai ở đâu và người dùng mong muốn câu trả lời như thế nào.
2. **Source-linked feedback:** phản hồi gắn với đoạn nguồn giúp cải thiện retrieval và giảm hallucination.
3. **Regenerate reason:** lý do tạo lại giúp phân loại lỗi: thiếu ý, sai ý, câu hỏi quá dài, quá dễ, quá khó.
4. **Acceptance signal:** xác định mẫu flashcard được người dùng tin tưởng.
5. **Behavioral learning data:** cho biết thẻ nào giúp người dùng ghi nhớ tốt hơn.

---

## 11. Data Types

| Loại dữ liệu | Có dùng không? | Ví dụ | Vai trò |
|---|---:|---|---|
| User-specific Data | Có, nhưng hạn chế trong MVP | Bộ thẻ đã lưu, lịch sử học, thẻ đã chỉnh sửa | Cá nhân hóa trải nghiệm và lưu tiến độ |
| Domain-specific Data | Có | PDF, slide, ghi chú, sách, đề cương | Nguồn chính để tạo flashcard |
| Real-time Data | Có | Nội dung vừa upload, flashcard vừa tạo | Phản hồi tức thời cho người dùng |
| Human-judgment Data | Có | Accept, Edit, Delete, Like/Dislike, Report Error | Cải thiện chất lượng AI |
| Behavioral Data | Có | Thời gian học, số lần ôn, độ khó tự đánh giá | Tối ưu lịch học và trải nghiệm |
| Synthetic Data | Có, trong kiểm thử | Bộ tài liệu và flashcard mẫu | Test hệ thống trước khi triển khai |

### 11.1. Marginal Value của dữ liệu

Dữ liệu có giá trị tăng dần theo thời gian nếu được thu thập đúng cách. Đặc biệt, dữ liệu chỉnh sửa của người dùng và dữ liệu nguồn gắn với flashcard có thể tạo ra lợi thế cạnh tranh vì phản ánh trực tiếp cách người học muốn chuyển đổi tài liệu thành kiến thức có thể ôn tập.

Tuy nhiên, cần tránh thu thập dữ liệu quá mức. MVP chỉ nên thu các dữ liệu cần thiết cho việc cải thiện chất lượng flashcard, vận hành sản phẩm và cá nhân hóa cơ bản.

---

## 12. AI Architecture đề xuất

### 12.1. Kiến trúc tổng quát

```text
Upload Document
→ File Validation
→ Text Extraction / OCR
→ Chunking
→ Embedding & Indexing
→ Retrieval
→ Flashcard Generation
→ Source Attribution
→ User Review
→ Feedback Logging
→ Evaluation & Improvement
```

### 12.2. Thành phần kỹ thuật

| Thành phần | Công nghệ đề xuất | Ghi chú |
|---|---|---|
| Frontend | React / Next.js | Phù hợp xây dựng web app hiện đại |
| Backend | FastAPI / Node.js | Xử lý upload, gọi model, quản lý user |
| Database | PostgreSQL | Lưu user, deck, flashcard, feedback |
| Object Storage | S3-compatible storage | Lưu file upload nếu cần |
| Vector Database | FAISS / Chroma / Qdrant | Lưu embedding phục vụ retrieval |
| OCR | PaddleOCR / Tesseract / dịch vụ cloud OCR | Dùng cho file scan hoặc ảnh |
| LLM | GPT / Gemini / Claude / Llama | Có thể thay đổi theo chi phí và chất lượng |
| Queue | Celery / Redis Queue / BullMQ | Xử lý tài liệu dài bất đồng bộ |
| Monitoring | Prometheus / Grafana / Sentry | Theo dõi lỗi, latency, cost |

### 12.3. Lý do nên dùng RAG

RAG giúp AI tạo flashcard dựa trên đoạn nội dung cụ thể từ tài liệu, thay vì chỉ dựa vào kiến thức tổng quát của mô hình. Điều này giúp:

- Giảm hallucination.
- Gắn flashcard với nguồn rõ ràng.
- Cho phép người dùng kiểm chứng câu trả lời.
- Tối ưu theo từng tài liệu cụ thể.

---

## 13. Quality Strategy

### 13.1. Optimize Precision hay Recall?

**Ưu tiên:** Recall-first, nhưng có kiểm soát precision.

Flashcard AI nên ưu tiên recall vì mục tiêu chính là giúp người dùng bao phủ đầy đủ kiến thức quan trọng trong tài liệu. Nếu AI bỏ sót nhiều ý, người dùng vẫn phải tự đọc lại tài liệu và tạo thêm flashcard thủ công, làm giảm giá trị sản phẩm.

Tuy nhiên, recall cao không có nghĩa là chấp nhận nội dung sai. Vì sản phẩm theo hướng augmentation, AI có thể tạo nhiều flashcard hơn, nhưng cần:

- Gắn source rõ ràng.
- Cho phép chỉnh sửa/xóa nhanh.
- Đánh dấu nội dung low-confidence.
- Theo dõi precision và hallucination rate.

### 13.2. Điều gì xảy ra nếu chọn sai chiến lược?

Nếu chỉ tối ưu precision và bỏ qua recall, AI sẽ tạo ít flashcard, chỉ chọn các ý chắc chắn nhất. Điều này làm bộ flashcard có vẻ chính xác nhưng thiếu nhiều nội dung quan trọng.

Nếu chỉ tối ưu recall mà bỏ qua precision, AI có thể tạo quá nhiều thẻ, trong đó có thẻ sai hoặc không hữu ích. Điều này làm người dùng mất niềm tin và phải tốn thời gian lọc lại.

Vì vậy, chiến lược phù hợp là: **Recall-first + Human Review + Source Attribution**.

---

## 14. Evaluation Metrics & Thresholds

| Metric | Định nghĩa | Target | Red Flag |
|---|---|---:|---:|
| Recall | Tỷ lệ ý chính trong tài liệu được chuyển thành flashcard | ≥ 85% | < 70% trong 1 tuần |
| Precision | Tỷ lệ flashcard đúng và bám sát nguồn | ≥ 80% | < 65% trong 1 tuần |
| Acceptance Rate | Tỷ lệ thẻ được chấp nhận không chỉnh sửa | ≥ 80% | < 65% trong 1 tuần |
| Edit Rate | Tỷ lệ thẻ bị chỉnh sửa | ≤ 20% | > 35% trong 1 tuần |
| Regeneration Rate | Tỷ lệ thẻ được yêu cầu tạo lại | ≤ 15% | > 30% trong 1 tuần |
| Deletion Rate | Tỷ lệ thẻ bị xóa | ≤ 10% | > 20% trong 1 tuần |
| Report Error Rate | Tỷ lệ thẻ bị báo lỗi | ≤ 5% | > 10% trong 1 tuần |
| Hallucination Rate | Tỷ lệ thẻ có thông tin không nằm trong nguồn | ≤ 5% | > 10% |
| Source Coverage | Tỷ lệ thẻ có nguồn trích dẫn hợp lệ | ≥ 95% | < 85% |
| Avg Latency | Thời gian tạo flashcard trung bình | ≤ 5 giây với tài liệu ngắn | > 8 giây |
| Cost per Generation | Chi phí trung bình mỗi lần tạo | ≤ 0.02 USD ở MVP | > 0.05 USD |
| CSAT | Điểm hài lòng người dùng | ≥ 4.5/5 | < 4.0/5 |
| Day-30 Retention | Tỷ lệ người dùng quay lại sau 30 ngày | ≥ 40% | < 25% |
| Time Saved | Thời gian tiết kiệm so với tạo thủ công | ≥ 70% | < 40% |

### 14.1. North Star Metrics

| North Star Metric | Lý do chọn |
|---|---|
| Weekly Active Learners creating or reviewing flashcards | Phản ánh người dùng thật sự dùng sản phẩm để học |
| Acceptance Rate | Đo trực tiếp chất lượng đầu ra của AI |
| Time Saved | Gắn với giá trị cốt lõi của sản phẩm |
| Recall | Đảm bảo bộ thẻ bao phủ đủ kiến thức |

---

## 15. Top Failure Modes

| # | Failure Mode | Trigger | Hậu quả | Mitigation |
|---|---|---|---|---|
| 1 | AI tạo flashcard sai nhưng hiển thị tự tin | Tài liệu mơ hồ, OCR lỗi, retrieval sai đoạn | Người dùng học sai, mất niềm tin | RAG, source highlighting, confidence gating, report error, human review cho mẫu lỗi nghiêm trọng |
| 2 | AI bỏ sót ý quan trọng | Chunking kém, prompt chỉ chọn ý nổi bật, tài liệu dài | Bộ thẻ không đầy đủ, người dùng phải làm thủ công | Recall-first extraction, coverage checklist theo chương/trang, eval bằng gold dataset |
| 3 | Flashcard quá dài hoặc quá khó học | AI sao chép nguyên đoạn tài liệu hoặc tạo câu trả lời dài | Người dùng khó ôn tập, giảm retention | Ràng buộc format, giới hạn độ dài, rubric “atomic flashcard”, cảnh báo thẻ quá dài |
| 4 | Source không khớp với nội dung thẻ | Retrieval sai hoặc mapping nguồn lỗi | Người dùng không kiểm chứng được | Kiểm tra source-card consistency, chỉ hiển thị thẻ khi có source hợp lệ |
| 5 | Latency cao khi tài liệu dài | Upload nhiều trang, OCR chậm, LLM xử lý tuần tự | Người dùng chờ lâu hoặc bỏ phiên | Queue, async processing, progress indicator, streaming, giới hạn file trong MVP |
| 6 | Chi phí API tăng khi mở rộng | Tài liệu dài, nhiều lượt regenerate | Biên lợi nhuận thấp | Token budget, caching, model routing, giới hạn quota, batch processing |
| 7 | Rủi ro dữ liệu và bản quyền | Người dùng upload tài liệu nhạy cảm hoặc có bản quyền | Vấn đề pháp lý và niềm tin | Điều khoản sử dụng, không dùng dữ liệu cá nhân để train nếu chưa xin phép, mã hóa, xóa file theo yêu cầu |

---

## 16. Trust & Safety

### 16.1. Nguyên tắc xây dựng niềm tin

- Luôn cho người dùng biết flashcard được tạo từ nguồn nào.
- Không trình bày nội dung AI như đáp án tuyệt đối đúng.
- Cho phép chỉnh sửa và xóa dễ dàng.
- Gắn nhãn nội dung cần xem lại khi confidence thấp.
- Không sử dụng tài liệu cá nhân của người dùng để huấn luyện mô hình nếu chưa có sự đồng ý rõ ràng.

### 16.2. UX cho trường hợp AI không chắc

Khi AI có confidence thấp hoặc không tìm thấy nguồn đủ rõ, hệ thống nên hiển thị:

> “Một số flashcard cần được xem lại vì AI chưa đủ chắc chắn về nội dung. Bạn có thể kiểm tra nguồn, chỉnh sửa hoặc tạo lại.”

Các nút đi kèm:

- Xem nguồn
- Chỉnh sửa
- Tạo lại
- Xóa
- Báo lỗi

---

## 17. ROI – 3 Kịch bản

Các con số dưới đây là giả định để đánh giá sơ bộ tính khả thi. Khi có dữ liệu thực tế, cần cập nhật bằng số liệu vận hành thật như số lượt tạo flashcard, chi phí model, retention và conversion rate.

### 17.1. Bảng ROI giả định

| Chỉ số | Conservative | Realistic | Optimistic |
|---|---:|---:|---:|
| Người dùng hoạt động/ngày | 500 | 2,000 | 5,000 |
| Số lượt tạo/ngày | 250 | 1,200 | 3,500 |
| Chi phí AI/lượt tạo | $0.015 | $0.012 | $0.010 |
| Chi phí AI/ngày | $3.75 | $14.40 | $35.00 |
| Chi phí vận hành/ngày | $30 | $80 | $150 |
| Tổng chi phí/ngày | $33.75 | $94.40 | $185.00 |
| Thời gian tiết kiệm/ngày | 20 giờ | 100 giờ | 300 giờ |
| Giá trị thời gian quy đổi | $5/giờ | $5/giờ | $5/giờ |
| Benefit/ngày | $100 | $500 | $1,500 |
| Net benefit/ngày | $66.25 | $405.60 | $1,315.00 |

### 17.2. ROI hàng năm giả định

| Kịch bản | Net benefit/ngày | Net benefit/năm |
|---|---:|---:|
| Conservative | $66.25 | $24,181.25 |
| Realistic | $405.60 | $148,044.00 |
| Optimistic | $1,315.00 | $479,975.00 |

### 17.3. Diễn giải

- **Conservative:** chứng minh sản phẩm có thể tạo giá trị ngay cả khi quy mô nhỏ.
- **Realistic:** sản phẩm bắt đầu có lợi thế vận hành khi số lượt tạo flashcard ổn định và chi phí model được kiểm soát.
- **Optimistic:** sản phẩm có thể mở rộng mạnh nếu retention tốt, người dùng quay lại thường xuyên và dữ liệu phản hồi giúp AI cải thiện rõ rệt.

### 17.4. Kill Criteria

Dự án cần được đánh giá lại hoặc tạm dừng mở rộng nếu xảy ra một trong các điều kiện sau:

- Net benefit âm trong 2 tháng liên tục.
- Precision dưới 70% trong 2 tuần liên tục.
- Recall dưới 75% trong 2 tuần liên tục.
- Hallucination Rate trên 10%.
- Latency trung bình trên 10 giây với tài liệu ngắn.
- Edit Rate hoặc Regeneration Rate trên 35% trong 2 tuần.
- Day-30 Retention dưới 20% sau khi đã cải thiện onboarding.
- Chi phí trung bình mỗi lượt tạo vượt quá mức sản phẩm có thể chi trả.

---

## 18. Mini AI Spec

### Product Overview

Flashcard AI là trợ lý học tập dùng AI để chuyển đổi tài liệu thành flashcard. Sản phẩm giúp người dùng tạo bộ thẻ học nhanh, có nguồn kiểm chứng, có thể chỉnh sửa và có thể lưu lại để ôn tập theo thời gian.

### AI Role

AI đóng vai trò **augmentation copilot**:

- Tạo bản nháp flashcard từ tài liệu.
- Đề xuất câu hỏi – câu trả lời theo ý chính.
- Gắn nguồn tham chiếu.
- Gợi ý cải thiện hoặc tạo lại khi người dùng chưa hài lòng.
- Học từ phản hồi đã được xử lý và kiểm soát chất lượng.

### Input

- PDF rõ văn bản.
- PDF scan có OCR.
- Slide bài giảng.
- Văn bản người dùng nhập.
- Chủ đề hoặc khoảng trang người dùng chọn.

### Output

Mỗi flashcard nên có cấu trúc:

```text
Question: Câu hỏi ngắn gọn, tập trung vào một ý chính.
Answer: Câu trả lời chính xác, súc tích, dễ học.
Source: Trang / đoạn / heading liên quan trong tài liệu.
Confidence: High / Medium / Low.
Tags: Chủ đề, chương, thuật ngữ nếu có.
```

### Quality Bar

- Flashcard chỉ nên kiểm tra một ý chính.
- Câu hỏi rõ ràng, không mơ hồ.
- Câu trả lời ngắn gọn, đúng nguồn.
- Không thêm thông tin ngoài tài liệu nếu không được yêu cầu.
- Có source hợp lệ cho từng flashcard.
- Với nội dung không chắc chắn, phải gắn nhãn cần xem lại.

### Success Metrics

| Metric | Target |
|---|---:|
| Recall | ≥ 85% |
| Precision | ≥ 80% |
| Acceptance Rate | ≥ 80% |
| Hallucination Rate | ≤ 5% |
| CSAT | ≥ 4.5/5 |
| Latency | ≤ 5 giây với tài liệu ngắn |
| Time Saved | ≥ 70% |
| Day-30 Retention | ≥ 40% |

---

## 19. Roadmap đề xuất

### Phase 1 – MVP

- Upload PDF và nhập văn bản.
- Tạo flashcard theo chủ đề hoặc khoảng trang.
- Hiển thị source.
- Accept, Edit, Regenerate, Delete.
- Lưu deck vào thư viện.
- Thu thập feedback cơ bản.

### Phase 2 – Learning Experience

- Chế độ học lật thẻ.
- Quiz mode.
- Spaced repetition cơ bản.
- Thống kê tiến độ học.
- Gợi ý thẻ cần ôn lại.

### Phase 3 – Personalization & Scale

- Cá nhân hóa độ khó flashcard.
- Tạo flashcard theo mục tiêu thi.
- Chia sẻ deck.
- Học nhóm hoặc lớp học.
- Tối ưu chi phí model và latency.

### Phase 4 – Advanced AI

- Tự động phát hiện chương/chủ đề.
- Tạo nhiều loại câu hỏi: định nghĩa, so sánh, ví dụ, ứng dụng.
- Tự đánh giá độ khó.
- Tạo đề kiểm tra từ deck.
- Fine-tuning hoặc model customization nếu có đủ dữ liệu chất lượng.

---

## 20. Kết luận

Flashcard AI là một sản phẩm có giá trị thực tế vì giải quyết trực tiếp vấn đề tốn thời gian và thiếu hệ thống khi tạo flashcard thủ công. Điểm quan trọng nhất của sản phẩm không chỉ là “AI tạo thẻ nhanh”, mà là tạo ra một quy trình học tập có kiểm soát: AI đề xuất, người dùng kiểm chứng, hệ thống học từ phản hồi và chất lượng được cải thiện theo thời gian.

Chiến lược phù hợp cho sản phẩm là **Augmentation + Recall-first + Source Attribution + Human-in-the-loop**. Với cách tiếp cận này, Flashcard AI có thể vừa tạo giá trị ngay trong MVP, vừa xây dựng nền tảng dữ liệu và niềm tin để phát triển thành một hệ sinh thái học tập thông minh hơn trong tương lai.
