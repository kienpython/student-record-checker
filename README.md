# Student Record Checker

MVP dùng Agent + Skills + Memory để đọc các record chưa có trạng thái
`Đã kiểm tra` từ Lark Base, in `Group ID`, `Record`, `Trạng thái`, và thử
cập nhật đúng hai field `Nhận xét` + `Trạng thái`.

## Cài đặt

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
```

Điền credential và ID vào `.env`. Lark app cần được cấp quyền đọc/ghi Base
(Bitable), được publish, và được thêm quyền truy cập vào Base cần xử lý.
`GEMINI_API_KEY` được dùng để sinh nhận xét. Tạo key miễn phí tại
https://aistudio.google.com/apikey. Có thể đổi model bằng `GEMINI_MODEL`;
mặc định là `gemini-2.5-flash-lite`.
Khi model chính quá tải, chương trình tự retry và chuyển sang
`GEMINI_FALLBACK_MODEL` (mặc định `gemini-2.5-flash`).

## Chạy an toàn trước

```powershell
python src/main.py --topic "Session 28, báo cáo bài tập nhóm" --expected-speakers 5 --limit 1 --dry-run
```

Khi log đọc đúng record, bỏ `--dry-run`. Ví dụ xử lý tối đa 100 record:

```powershell
python src/main.py --topic "Session 28, báo cáo bài tập nhóm" --expected-speakers 5 --limit 100
```

Chương trình xử lý lần lượt toàn bộ record chưa kiểm tra trong phạm vi
`--limit`. Payload update chỉ chứa:

- `Nhận xét`
- `Trạng thái`

Nhận xét hiện được Gemini sinh từ metadata và field `Tóm tắt báo cáo`. AI được
yêu cầu không giả định rằng nó đã xem record khi chưa có transcript.
`--dry-run` không ghi Lark Base nhưng vẫn gọi Gemini để tạo và hiển thị payload,
vì vậy vẫn có thể phát sinh chi phí API nhỏ.

Các mẫu giọng văn nằm trong `data/comment_examples.txt`. Mỗi dòng là một mẫu.
Có thể thêm nhận xét thật vào cuối file; chương trình sẽ tự đọc lại ở lần chạy
tiếp theo mà không cần sửa code.

## Sĩ số nhóm và đếm giọng nói

Với `Group ID` dạng `HN-KS25-CNTT4-G3`, chương trình đọc:

```text
class/HN-KS25-CNTT4/HN-KS25-CNTT4.txt
```

Nội dung:

```text
G1: 5 Sinh viên
G2: 6 Sinh viên
G3: 7 Sinh viên
```

Tên folder và file phải trùng chính xác phần mã lớp trong `Group ID`.
YouTube audio được cache trong `cache/audios`; kết quả speaker được cache để
không phải phân tích lại. Nếu số giọng nói ít hơn sĩ số, nhận xét sẽ nhắc nhóm
cần đảm bảo toàn bộ thành viên tham gia.

Trước lần chạy đầu, đăng nhập đúng tài khoản đã tạo `PYANNOTE_TOKEN` và chấp
nhận điều kiện tại:

https://huggingface.co/pyannote/speaker-diarization-community-1

Các skill tải file, transcription, speaker detection và topic judging đã được
tách module để nối vào phase xử lý media tiếp theo.
