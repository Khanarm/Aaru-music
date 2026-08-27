import asyncio
import glob
import os
import random
import re
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from ytSearch import VideosSearch, Playlist

from AnonXMusic import LOGGER
from AnonXMusic.utils.formatters import time_to_seconds

logger = LOGGER(__name__)


def cookie_txt_file():
    """Return a randomly selected cookies/*.txt file, if available."""
    try:
        folder_path = os.path.join(os.getcwd(), "cookies")
        filename = os.path.join(folder_path, "logs.csv")
        txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
        if not txt_files:
            return None

        selected = random.choice(txt_files)
        try:
            with open(filename, "a", encoding="utf-8") as file:
                file.write(f"Choosen File : {selected}\n")
        except Exception:
            pass
        return selected
    except Exception:
        return None


class YouTubeAPI:
    """YouTube helper used by the existing AnonXMusic playback code.

    This version does not use Fallen/xBit/other proxy APIs. Metadata/search is
    kept compatible with the original project, while media is resolved or
    downloaded directly through yt-dlp.
    """

    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.dl_stats = {
            "total_requests": 0,
            "direct_downloads": 0,
            "cookie_downloads": 0,
            "existing_files": 0,
        }

    @staticmethod
    def _clean_link(link: str) -> str:
        if "&" in link:
            link = link.split("&", 1)[0]
        if "?si=" in link:
            link = link.split("?si=", 1)[0]
        return link

    def _video_url(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + str(link)
        return self._clean_link(link)

    def _ydl_opts(self, **extra):
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
        }
        cookies = cookie_txt_file()
        if cookies:
            opts["cookiefile"] = cookies
        opts.update(extra)
        return opts

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        link = self._video_url(link, videoid)
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            if message.entities:
                text = message.text or message.caption or ""
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        return text[entity.offset: entity.offset + entity.length]

            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        link = self._video_url(link, videoid)
        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])
        if not data:
            raise ValueError("No YouTube result found")

        result = data[0]
        title = result.get("title", "Unknown")
        duration_min = result.get("duration")
        thumbnail = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        vidid = result.get("id")
        duration_sec = 0 if not duration_min else int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        link = self._video_url(link, videoid)
        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])
        if not data:
            raise ValueError("No YouTube result found")
        return data[0].get("title", "Unknown")

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        link = self._video_url(link, videoid)
        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])
        if not data:
            raise ValueError("No YouTube result found")
        return data[0].get("duration")

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        link = self._video_url(link, videoid)
        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])
        if not data:
            raise ValueError("No YouTube result found")
        return data[0].get("thumbnails", [{}])[0].get("url", "").split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        """Return a direct media URL, preserving the original (1, url) API."""
        link = self._video_url(link, videoid)
        try:
            opts = self._ydl_opts(
                format="best[height<=720][width<=1280]/best[height<=720]/best",
                skip_download=True,
            )
            direct_url = await asyncio.to_thread(self._extract_direct, link, opts)
            if direct_url:
                return 1, direct_url
            return 0, "Unable to resolve YouTube media URL"
        except Exception as e:
            logger.error(f"Direct video URL error: {e}")
            return 0, str(e)

    @staticmethod
    def _extract_direct(link, opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            return info.get("url")

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        link = self._video_url(link, videoid)
        playlist = await Playlist.get(link)
        if not playlist:
            return None

        videos = []
        for video in playlist.get("videos", [])[:limit]:
            try:
                duration = video.get("duration")
                duration_sec = int(time_to_seconds(duration)) if duration else 0
                videos.append({
                    "vidid": video.get("id"),
                    "title": video.get("title", "Unknown"),
                    "duration_min": duration,
                    "duration_sec": duration_sec,
                    "thumbnail": video.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
                    if video.get("thumbnails") else "",
                })
            except Exception:
                continue
        return videos

    async def track(self, link: str, videoid: Union[bool, str] = None):
        link = self._video_url(link, videoid)
        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])
        if not data:
            raise ValueError("No YouTube result found")

        result = data[0]
        track_details = {
            "title": result.get("title", "Unknown"),
            "link": result.get("link"),
            "vidid": result.get("id"),
            "duration_min": result.get("duration"),
            "thumb": result.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
        }
        return track_details, result.get("id")

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        link = self._video_url(link, videoid)

        def extract():
            with yt_dlp.YoutubeDL(self._ydl_opts()) as ydl:
                info = ydl.extract_info(link, download=False)
                available = []
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower():
                        continue
                    available.append({
                        "format": fmt.get("format"),
                        "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
                        "format_id": fmt.get("format_id"),
                        "ext": fmt.get("ext"),
                        "format_note": fmt.get("format_note"),
                        "yturl": link,
                    })
                return available

        return await asyncio.to_thread(extract), link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        link = self._video_url(link, videoid)
        try:
            search = VideosSearch(link, limit=10)
            search_results = (await search.next()).get("result", [])
            results = []

            for result in search_results:
                duration_str = result.get("duration") or "0:00"
                try:
                    parts = duration_str.split(":")
                    if len(parts) == 3:
                        duration_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:
                        duration_secs = int(parts[0]) * 60 + int(parts[1])
                    else:
                        duration_secs = 0
                    if duration_secs <= 3600:
                        results.append(result)
                except (ValueError, IndexError):
                    continue

            if not results or query_type >= len(results):
                raise ValueError("No suitable videos found within duration limit")

            selected = results[query_type]
            return (
                selected.get("title", "Unknown"),
                selected.get("duration"),
                selected.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
                selected.get("id"),
            )
        except Exception as e:
            logger.error(f"Error in slider: {e}")
            raise ValueError("Failed to fetch video details")

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        """Download media directly with yt-dlp.

        The return shape remains `(path, direct)` because the rest of
        AnonXMusic expects exactly that shape.
        """
        self.dl_stats["total_requests"] += 1

        vid_id = str(link) if videoid else None
        url = self._video_url(link, videoid)
        os.makedirs("downloads", exist_ok=True)

        # Keep filenames deterministic so the existing queue/replay logic can
        # find the same file again.
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", vid_id or "track")
        output = os.path.join("downloads", f"{safe_id}.mp4" if video or songvideo else f"{safe_id}.mp3")

        if os.path.exists(output) and os.path.getsize(output) > 0:
            self.dl_stats["existing_files"] += 1
            return output, True

        cookies = cookie_txt_file()
        if cookies:
            self.dl_stats["cookie_downloads"] += 1

        if video or songvideo:
            ydl_opts = self._ydl_opts(
                format=(
                    format_id
                    if format_id
                    else "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
                ),
                outtmpl=output,
                merge_output_format="mp4",
                noplaylist=True,
            )
        else:
            ydl_opts = self._ydl_opts(
                format=(format_id if format_id else "bestaudio/best"),
                outtmpl=output,
                noplaylist=True,
                postprocessors=[{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            )

        try:
            await asyncio.to_thread(self._download_sync, url, ydl_opts)

            # FFmpegExtractAudio may rewrite the extension; locate the expected
            # MP3 if yt-dlp created it from another source extension.
            if not os.path.exists(output) and not (video or songvideo):
                candidates = glob.glob(os.path.join("downloads", f"{safe_id}.*"))
                mp3_candidates = [p for p in candidates if p.lower().endswith(".mp3")]
                if mp3_candidates:
                    output = mp3_candidates[0]

            if not os.path.exists(output) or os.path.getsize(output) <= 0:
                raise RuntimeError("yt-dlp completed but no media file was created")

            self.dl_stats["direct_downloads"] += 1
            return output, True

        except Exception as e:
            # Remove partial files so a failed request does not poison the
            # queue/cache on the next attempt.
            for candidate in glob.glob(os.path.join("downloads", f"{safe_id}.*")):
                try:
                    if os.path.isfile(candidate):
                        os.remove(candidate)
                except OSError:
                    pass
            logger.error(f"Direct YouTube download failed: {e}")
            raise

    @staticmethod
    def _download_sync(url, opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
