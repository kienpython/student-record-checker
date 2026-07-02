# Student Record Checker — Hướng dẫn cho AI/Codex

Đọc file này trước khi chỉnh sửa project. Đây là ngữ cảnh bền vững để người dùng
không phải giải thích lại yêu cầu ở mỗi phiên làm việc.

## Mục tiêu

Xây dựng AI Agent kiểm tra bài báo cáo nhóm từ Lark Base:

1. Đọc các record chưa có trạng thái `Đã kiểm tra`.
2. Ưu tiên nguồn theo thứ tự:
   - field `Record`;
   - nếu `Record` rỗng thì dùng `File báo cáo chi tiết`.
3. Tải audio/video từ YouTube, Google Drive hoặc Lark attachment.
4. Transcribe bằng `faster-whisper` local và cache transcript.
5. Đếm người nói bằng `pyannote.audio` nếu có `PYANNOTE_TOKEN`.
6. Dùng Gemini đánh giá nội dung có bám đề và viết nhận xét.
7. Chỉ cập nhật hai field Lark:
   - `Nhận xét`;
   - `Trạng thái`.
8. Lỗi một record không được làm dừng toàn bộ chương trình.

## Kiến trúc bắt buộc

Giữ kiến trúc Agent + Skills + Memory. Không gom mọi logic vào một file.
Mỗi chức năng phải nằm trong skill tương ứng:

```text
src/
├── main.py
├── agent.py
├── config.py
├── logger.py
├── memory.py
├── llm_client.py
└── skills/
    ├── read_lark_base_skill.py
    ├── lark_file_handler_skill.py
    ├── download_audio_skill.py
    ├── transcribe_skill.py
    ├── speaker_detect_skill.py
    ├── topic_judge_skill.py
    ├── comment_writer_skill.py
    └── update_lark_base_skill.py
```

## Field Lark Base

Tên field phải giữ đúng Unicode tiếng Việt:

- `Group ID`
- `Nhóm`
- `Thời gian nộp`
- `Record`
- `Tóm tắt báo cáo`
- `File báo cáo chi tiết`
- `Trợ giảng`
- `Nhận xét`
- `Trạng thái`

Giá trị trạng thái:

- Thành công: `Đã kiểm tra`
- Thất bại: `Lỗi kiểm tra`

Không đổi tên field và không dùng chuỗi mojibake như `Tráº¡ng thÃ¡i`.

## Phong cách nhận xét

Nhận xét phải giống trợ giảng thật:

- Chỉ 1–2 câu.
- Ngắn, trực tiếp, thân thiện.
- Không chào hỏi hoặc gọi tên/mã nhóm.
- Không viết kiểu thông báo hành chính.
- Không nhắc `AI`, `hệ thống`, `transcript`, `record`, `video đang xử lý`.
- Không bịa rằng đã nghe/xem hoặc đếm speaker khi chưa có kết quả thật.
- Khi thiếu dữ liệu, dùng lời động viên trung tính, không giải thích lỗi kỹ thuật.

Mẫu giọng văn người dùng mong muốn:

- `Nhóm tích cực tham gia hoạt động, đánh giá cao.`
- `Nhóm có tiến hành thảo luận, nhưng cần thêm cho thầy một phần quiz hay mindmap để ôn lại kiến thức nha.`
- `Nhóm hoạt động tốt, cứ thế phát huy.`
- `Nhóm có tiến hành thảo luận, nhưng cần có thêm phần kiểm tra kiến thức của các thành viên trong nhóm em nhé.`

Prompt runtime hiện nằm trong `src/skills/comment_writer_skill.py`. Nếu chỉnh
phong cách, cập nhật cả prompt và test liên quan.

## Trạng thái triển khai hiện tại

Đã hoạt động:

- Xác thực Lark bằng tenant access token.
- Đọc record từ Lark Base.
- Lọc record chưa phải `Đã kiểm tra`.
- In `Group ID`, `Record`, `Trạng thái`.
- Cập nhật đúng hai field `Nhận xét`, `Trạng thái`.
- `--dry-run`.
- Gemini sinh nhận xét qua SDK `google-genai`.
- Retry Gemini khi gặp 429/503 và fallback model.
- Trong luồng demo hiện tại, record không phải YouTube được ghi
  `Không phải link YouTube để kiểm tra.` và không gọi Gemini.
- Đọc sĩ số nhóm từ `class/<mã-lớp>/<mã-lớp>.txt`.
- Tải audio-only YouTube bằng yt-dlp và cache WAV.
- Đếm speaker bằng pyannote community-1, cache kết quả.
- Thiếu speaker so với sĩ số thì nhắc toàn bộ thành viên tham gia.
- Logging, error isolation và unit tests.

Chưa hoàn thiện:

- Tải Google Drive.
- Tải Lark attachment trong luồng Agent.
- Transcribe bằng `faster-whisper`.
- Topic judging dựa trên transcript.
- Nhận xét đầy đủ dựa trên nội dung video.

Không được mô tả các phần chưa hoàn thiện như thể chúng đã hoạt động.

## Quy tắc xử lý nguồn record

- `Record` rỗng:
  - bỏ qua hoàn toàn;
  - không ghi nhận xét và không đổi trạng thái.
- `Record` bằng `no`:
  - `Nhận xét = Không có link record để kiểm tra.`
  - `Trạng thái = Đã kiểm tra`
- YouTube:
  - chỉ tải audio bằng `yt-dlp`, không tải full video nếu không cần.
- Google Drive:
  - thử tải nếu quyền cho phép; nếu thất bại ghi lỗi ngắn.
- Lark attachment:
  - dùng file/attachment token;
  - hỗ trợ `mp3`, `m4a`, `wav`, `mp4`, `mov`.
- Cache media trong `cache/audios` hoặc `cache/files`.
- Cache transcript trong `cache/transcripts`, theo `record_id` hoặc `Group ID`.
- Không có `PYANNOTE_TOKEN` thì không crash; ghi nhận nội bộ
  `Chưa bật speaker detection`.

## Cấu hình

Credential thật chỉ được đặt trong `.env`. `.env.example` luôn dùng placeholder.
Không in hoặc commit secret.

Các biến hiện dùng:

```env
LARK_APP_ID=
LARK_APP_SECRET=
LARK_APP_TOKEN=
LARK_TABLE_ID=
LARK_VIEW_ID=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_FALLBACK_MODEL=gemini-2.5-flash
GEMINI_MAX_RETRIES=3
PYANNOTE_TOKEN=
LOG_LEVEL=INFO
```

Nếu secret xuất hiện trong file tracked hoặc output, cảnh báo người dùng rotate
secret và xóa giá trị khỏi file mẫu.

## Lệnh chạy

Người dùng dùng Windows CMD:

```cmd
.venv\Scripts\activate.bat
pip install -r requirements.txt
python src\main.py --topic "Session 28, báo cáo bài tập nhóm" --expected-speakers 5 --limit 1 --dry-run
```

Chạy thật bằng cách bỏ `--dry-run`.

## Quy tắc an toàn khi phát triển

- Luôn thử với `--limit 1`.
- Ưu tiên `--dry-run` trước khi ghi thật.
- Không tự chạy lệnh ghi thật vào Lark nếu người dùng chưa yêu cầu rõ.
- Khi chạy thật, xử lý toàn bộ record được trả về trong phạm vi `--limit`;
  không giới hạn chỉ một record.
- Payload update chỉ được chứa `Nhận xét` và `Trạng thái`.
- Xử lý lỗi từng record, log ngắn gọn, tiếp tục record tiếp theo.
- Không làm mất thay đổi hoặc credential trong `.env`.
- Không commit cache, log, `.env` hoặc virtual environment.

## Kiểm thử bắt buộc

Sau mỗi thay đổi code, chạy:

```cmd
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q src tests
```

Giữ test cho:

- filter và pagination Lark;
- payload chỉ có hai field được phép;
- dry-run;
- lỗi AI ghi `Lỗi kiểm tra`;
- prompt nhận xét đúng phong cách;
- Gemini retry và fallback.
