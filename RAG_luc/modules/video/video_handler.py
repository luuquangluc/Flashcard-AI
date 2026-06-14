import os
import re
import uuid
import json
import logging
import asyncio
import yt_dlp
from pathlib import Path
from typing import Optional, Tuple
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

# Removed faster_whisper import, use Groq instead
# from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

class VideoHandler:
    """Tích hợp tính năng Transcribe Video vào RAG System"""
    
    def __init__(self, model_size: str = "base", cost_logger: callable = None):
        self.model_size = model_size
        self.model = None
        self.cost_logger = cost_logger
        self.temp_dir = Path("temp_video")
        self.temp_dir.mkdir(exist_ok=True)
        # Setup ffmpeg & ffprobe paths via static-ffmpeg only if not already in PATH
        import shutil
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            try:
                import static_ffmpeg
                static_ffmpeg.add_paths() # Adds ffmpeg and ffprobe to PATH
                logger.info("Đã sử dụng static-ffmpeg vì không tìm thấy ffmpeg trong hệ thống.")
            except ImportError:
                logger.warning("Không tìm thấy ffmpeg trong hệ thống và cũng không có static-ffmpeg.")
            
        # Cấu hình yt-dlp để tải file có cả âm thanh, ưu tiên file có sẵn audio để không cần dùng FFmpeg tách nhạc
        self.ydl_opts = {
            'format': 'best[acodec!=none]/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            # Giả lập browser để tránh bị YouTube chặn trên server
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            },
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'mweb', 'web']}},
        }
        
        # Proxy (nếu YouTube chặn IP server)
        yt_proxy = os.environ.get("YT_PROXY")
        if yt_proxy:
            self.ydl_opts['proxy'] = yt_proxy
            logger.info(f"🌐 Đã cấu hình proxy cho yt-dlp: {yt_proxy[:20]}...")
        
        # Thêm xử lý cookies từ environment variable hoặc file
        self.cookies_path = None
        youtube_cookies = os.environ.get("YOUTUBE_COOKIES")
        if youtube_cookies:
            cookies_path = self.temp_dir / "cookies.txt"
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(youtube_cookies)
            self.cookies_path = str(cookies_path)
            self.ydl_opts['cookiefile'] = self.cookies_path
            logger.info(f"🍪 Đã cấu hình cookies từ biến môi trường YOUTUBE_COOKIES ({len(youtube_cookies)} bytes)")
        elif os.path.exists("cookies.txt"):
            self.cookies_path = "cookies.txt"
            self.ydl_opts['cookiefile'] = self.cookies_path
            logger.info("🍪 Sử dụng cookies từ file cookies.txt")
        else:
            logger.warning("⚠️ Không tìm thấy cookies YouTube. Video có thể bị chặn.")

    def _load_whisper(self):
        # Đã chuyển sang dùng Groq API nên không cần tải mô hình local nữa
        pass

    async def get_transcript(self, url: str) -> Tuple[str, str, str]:
        """
        Lấy văn bản từ video
        Returns: (raw_transcript, summarized_transcript, video_title)
        """
        # 1. Thử lấy phụ đề qua API (Không cần download, siêu ổn định)
        transcript, lang = await self._fetch_transcript_api(url)
        
        # Lấy title (Thử yt-dlp nhưng không block nếu lỗi)
        title = await self._get_video_title_safe(url)
        
        if not transcript:
            # 2. Thử lấy phụ đề qua yt-dlp (Nếu API fail)
            logger.info(f"🔍 Thử lấy phụ đề qua yt-dlp cho: {url}")
            transcript, _, lang = await self._fetch_subtitles(url)
        
        if not transcript:
            # 3. Nếu không có phụ đề, tải audio và Transcribe (Mất thời gian hơn)
            logger.info(f"🔊 Không tìm thấy phụ đề, bắt đầu tải audio để chuyển biên: {url}")
            audio_path, title = await self._download_audio(url)
            
            if audio_path == "NO_AUDIO":
                logger.warning("⚠️ Video không có âm thanh để chép lời.")
                transcript = "Video này không có âm thanh để chép lời."
            else:
                self._load_whisper()
                
                def _do_transcribe():
                    try:
                        from groq import Groq
                        # Tự động lấy GROQ_API_KEY từ biến môi trường
                        client = Groq()
                        
                        with open(audio_path, "rb") as file:
                            logger.info("🚀 Gửi audio lên Groq Whisper API...")
                            transcription = client.audio.transcriptions.create(
                                file=(os.path.basename(audio_path), file.read()),
                                model="whisper-large-v3",
                                prompt="",
                                response_format="verbose_json"
                            )
                            logger.info("✅ Nhận kết quả từ Groq thành công!")
                        
                        text_parts = []
                        # Trích xuất segments có timestamp nếu dùng verbose_json
                        segments = getattr(transcription, 'segments', None)
                        if not segments and isinstance(transcription, dict):
                            segments = transcription.get('segments', [])
                            
                        if segments:
                            for segment in segments:
                                start_time = segment.get('start', 0) if isinstance(segment, dict) else segment.start
                                text_val = segment.get('text', '') if isinstance(segment, dict) else segment.text
                                start_str = self._format_time(start_time)
                                text_parts.append(f"[{start_str}] {text_val.strip()}")
                            return "\n".join(text_parts)
                        else:
                            # Fallback nếu không có segment
                            text_val = getattr(transcription, 'text', '') if not isinstance(transcription, dict) else transcription.get('text', '')
                            return text_val
                    except Exception as e:
                        logger.error(f"❌ Lỗi khi gọi Groq API: {e}")
                        raise

                transcript = await asyncio.to_thread(_do_transcribe)
                
                # Dọn dẹp file tạm
                if os.path.exists(audio_path):
                    os.remove(audio_path)
        
        # 3. Tóm tắt nội dung (Summarize)
        logger.info(f"📝 Đang tóm tắt nội dung cho: {title}")
        summary = await self.summarize_transcript(transcript, title)
            
        return transcript, summary, title

    async def get_transcript_from_file(self, file_path: str, title: str) -> Tuple[str, str, str]:
        """
        Lấy văn bản từ file video/audio có sẵn
        Returns: (raw_transcript, summarized_transcript, video_title)
        """
        self._load_whisper()
        
        def _do_transcribe():
            try:
                from groq import Groq
                client = Groq()
                
                with open(file_path, "rb") as file:
                    logger.info("🚀 Gửi file lên Groq Whisper API...")
                    transcription = client.audio.transcriptions.create(
                        file=(os.path.basename(file_path), file.read()),
                        model="whisper-large-v3",
                        prompt="",
                        response_format="verbose_json"
                    )
                    logger.info("✅ Nhận kết quả từ Groq thành công!")
                
                text_parts = []
                segments = getattr(transcription, 'segments', None)
                if not segments and isinstance(transcription, dict):
                    segments = transcription.get('segments', [])
                    
                if segments:
                    for segment in segments:
                        start_time = segment.get('start', 0) if isinstance(segment, dict) else segment.start
                        text_val = segment.get('text', '') if isinstance(segment, dict) else segment.text
                        start_str = self._format_time(start_time)
                        text_parts.append(f"[{start_str}] {text_val.strip()}")
                    return "\n".join(text_parts)
                else:
                    text_val = getattr(transcription, 'text', '') if not isinstance(transcription, dict) else transcription.get('text', '')
                    return text_val
            except Exception as e:
                logger.error(f"❌ Lỗi khi gọi Groq API: {e}")
                if "no audio track found" in str(e):
                    return "Video này không có âm thanh để chép lời."
                raise

        import asyncio
        transcript = await asyncio.to_thread(_do_transcribe)
        
        # Tóm tắt nội dung
        logger.info(f"📝 Đang tóm tắt nội dung cho: {title}")
        summary = await self.summarize_transcript(transcript, title)
            
        return transcript, summary, title

    async def summarize_transcript(self, transcript: str, title: str) -> str:
        """Sử dụng LLM để tóm tắt bản chép lời"""
        try:
            from openai import OpenAI
            client = OpenAI() # Tự động lấy key từ môi trường

            model = "gpt-4o-mini"

            prompt = f"""
            Bạn là một chuyên gia biên tập. Hãy tóm tắt bản chép lời video sau đây thành một bản tóm tắt chuyên nghiệp.
            
            Tiêu đề video: {title}
            
            Yêu cầu:
            1. Chia nhỏ thành các đề mục lớn dựa trên nội dung.
            2. Mỗi đề mục tóm tắt các ý chính một cách súc tích.
            3. Giữ nguyên các thuật ngữ quan trọng.
            4. Trình bày bằng Markdown sạch sẽ.
            5. Ngôn ngữ: Tiếng Việt.

            Nội dung bản chép lời:
            {transcript[:15000]}
            """

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            # Ghi log chi phí nếu có callback
            if self.cost_logger:
                usage = response.usage
                self.cost_logger(
                    model=model,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    feature_name="Video Summarization"
                )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"❌ Lỗi tóm tắt: {e}")
            return "Không thể tạo tóm tắt vào lúc này."

    async def _get_video_title_safe(self, url: str) -> str:
        """Lấy title video mà không làm crash cả quy trình nếu yt-dlp lỗi"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'noplaylist': True, 'cookiefile': self.cookies_path if self.cookies_path else None}) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                return info.get('title', 'YouTube Video')
        except Exception as e:
            logger.warning(f"⚠️ Không lấy được title qua yt-dlp: {e}")
            # Thử regex đơn giản từ URL nếu là shorts
            match = re.search(r"shorts/([a-zA-Z0-9_-]+)", url)
            if match: return f"YouTube Shorts {match.group(1)}"
            return "YouTube Video"

    async def _fetch_transcript_api(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Sử dụng youtube-transcript-api để lấy sub mà không cần tải video"""
        try:
            video_id = None
            if "shorts/" in url:
                video_id = url.split("shorts/")[1].split("?")[0]
            elif "v=" in url:
                video_id = url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0]
            
            if not video_id:
                return None, None

            logger.info(f"🔍 Đang thử lấy transcript qua API cho ID: {video_id}")
            # Ưu tiên tiếng Việt, sau đó đến tiếng Anh
            yt_proxy = os.environ.get("YT_PROXY")
            proxies = {"https": yt_proxy, "http": yt_proxy} if yt_proxy else None
            
            transcript_list = await asyncio.to_thread(
                YouTubeTranscriptApi.list_transcripts, 
                video_id,
                proxies=proxies
            )
            
            try:
                t = transcript_list.find_transcript(['vi'])
            except:
                try:
                    t = transcript_list.find_generated_transcript(['vi'])
                except:
                    try:
                        t = transcript_list.find_transcript(['en'])
                    except:
                        t = transcript_list.find_generated_transcript(['en'])

            data = await asyncio.to_thread(t.fetch)
            formatter = TextFormatter()
            return formatter.format_transcript(data), t.language_code
        except Exception as e:
            logger.warning(f"⚠️ YouTubeTranscriptApi failed: {e}")
            return None, None

    async def _fetch_subtitles(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        try:
            sub_dir = self.temp_dir / f"subs_{uuid.uuid4().hex[:8]}"
            sub_dir.mkdir(exist_ok=True)
            
            opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['vi', 'en'],
                'outtmpl': str(sub_dir / "sub.%(ext)s"),
                'quiet': True
            }
            # Dùng chung cookies để tránh bị YouTube chặn
            if self.cookies_path:
                opts['cookiefile'] = self.cookies_path
                
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                title = info.get('title', 'Video')
                
                sub_files = list(sub_dir.glob("*.vtt")) + list(sub_dir.glob("*.srt"))
                if not sub_files:
                    return None, title, None
                
                with open(sub_files[0], 'r', encoding='utf-8') as f:
                    content = f.read()
                
                text = re.sub(r'<[^>]+>', '', content)
                text = re.sub(r'WEBVTT|Kind:.*|Language:.*|Style:.*', '', text)
                lines = []
                for line in text.split('\n'):
                    if '-->' not in line and line.strip() and not line.strip().isdigit():
                        lines.append(line.strip())
                
                import shutil
                shutil.rmtree(sub_dir)
                
                return "\n".join(lines), title, "auto"
        except Exception as e:
            logger.warning(f"⚠️ Không lấy được phụ đề: {e}")
            return None, None, None

    def _has_audio_stream(self, file_path: str) -> bool:
        """Kiểm tra file có audio stream hay không bằng ffprobe"""
        import subprocess
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a",
                 "-show_entries", "stream=codec_type", "-of", "csv=p=0", file_path],
                capture_output=True, text=True, timeout=10
            )
            return "audio" in result.stdout
        except Exception as e:
            logger.warning(f"⚠️ Không chạy được ffprobe: {e}")
            return True  # Giả sử có audio, để ffmpeg thử convert

    def _find_downloaded_file(self, unique_id: str) -> Optional[str]:
        """Tìm file đã tải về theo unique_id"""
        import glob
        files = glob.glob(str(self.temp_dir / f"audio_{unique_id}.*"))
        # Loại bỏ file _clean.mp3 khỏi kết quả
        files = [f for f in files if "_clean" not in f]
        return files[0] if files else None

    async def _download_audio(self, url: str) -> Tuple[str, str]:
        unique_id = uuid.uuid4().hex[:8]
        output_template = str(self.temp_dir / f"audio_{unique_id}.%(ext)s")
        import subprocess
        
        # === Bước 1: Thử tải audio-only trước ===
        opts = self.ydl_opts.copy()
        opts['outtmpl'] = output_template
        opts['format'] = 'bestaudio/best[acodec!=none]'
        
        title = 'Video'
        audio_path = None
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                title = info.get('title', 'Video')
                
                audio_path = info.get('_filename')
                if not audio_path or not os.path.exists(audio_path):
                    audio_path = self._find_downloaded_file(unique_id)
        except Exception as e:
            logger.warning(f"⚠️ Không tải được audio-only: {e}")
        
        # === Bước 2: Kiểm tra file có audio stream không ===
        if audio_path and os.path.exists(audio_path):
            if not self._has_audio_stream(audio_path):
                logger.warning(f"⚠️ File tải về không có audio stream, thử tải lại với format 'best' (video+audio muxed)")
                try:
                    os.remove(audio_path)
                except:
                    pass
                audio_path = None  # Reset để tải lại
        
        # === Bước 3: Nếu chưa có audio, tải best format (video+audio muxed, phổ biến trên TikTok) ===
        if not audio_path or not os.path.exists(audio_path):
            logger.info(f"🔄 Tải lại video với format 'best' để lấy audio muxed...")
            opts2 = self.ydl_opts.copy()
            # Dùng unique_id mới để tránh trùng file
            unique_id2 = uuid.uuid4().hex[:8]
            opts2['outtmpl'] = str(self.temp_dir / f"audio_{unique_id2}.%(ext)s")
            opts2['format'] = 'best'
            
            try:
                with yt_dlp.YoutubeDL(opts2) as ydl:
                    info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                    title = info.get('title', 'Video')
                    
                    audio_path = info.get('_filename')
                    if not audio_path or not os.path.exists(audio_path):
                        audio_path = self._find_downloaded_file(unique_id2)
                    
                    unique_id = unique_id2  # Cập nhật unique_id cho output
            except Exception as e:
                logger.error(f"❌ Không tải được video: {e}")
                return "NO_AUDIO", title
        
        if not audio_path or not os.path.exists(audio_path):
            return "NO_AUDIO", title
            
        # === Bước 4: Kiểm tra lần cuối bằng ffprobe ===
        if not self._has_audio_stream(audio_path):
            logger.warning("⚠️ File thực sự không có audio stream nào.")
            try:
                os.remove(audio_path)
            except:
                pass
            return "NO_AUDIO", title
        
        # === Bước 5: Extract audio sang MP3 bằng FFmpeg ===
        output_mp3 = str(self.temp_dir / f"audio_{unique_id}_clean.mp3")
        try:
            # -vn: bỏ video, -y: ghi đè nếu có, -b:a 64k để nén nhỏ
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, "-vn", "-b:a", "64k", output_mp3],
                check=True, capture_output=True, text=True
            )
            logger.info(f"✅ Đã convert file sang MP3 thành công: {output_mp3}")
            
            # Xóa file gốc chưa convert để tiết kiệm bộ nhớ
            try:
                os.remove(audio_path)
            except:
                pass
                
            return output_mp3, title
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode()
            logger.error(f"❌ Lỗi khi convert sang MP3 bằng FFmpeg: {stderr}")
            if "Output file does not contain any stream" in stderr or "Output file is empty" in stderr:
                try:
                    os.remove(audio_path)
                except:
                    pass
                return "NO_AUDIO", title
            # Nếu lỗi khác, trả về file gốc xem Groq có đọc được không
            return audio_path, title

    def _format_time(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
