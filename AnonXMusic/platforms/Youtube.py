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
        txt_files = glob.glob(os.path.join(folder_path, "*.txt"))

        if not txt_files:
            return None

        selected = random.choice(txt_files)

        try:
            os.makedirs(folder_path, exist_ok=True)
            filename = os.path.join(folder_path, "logs.csv")

            with open(filename, "a", encoding="utf-8") as file:
                file.write(f"Chosen File : {selected}\n")
        except Exception:
            pass

        return selected

    except Exception:
        return None


def cookie_files():
    """Return all available cookie files."""
    try:
        folder_path = os.path.join(os.getcwd(), "cookies")

        if not os.path.isdir(folder_path):
            return []

        return glob.glob(os.path.join(folder_path, "*.txt"))

    except Exception:
        return []


class YouTubeAPI:
    """
    YouTube helper using yt-dlp directly.

    The public API is kept compatible with the existing AnonXMusic code.

    403 handling:
      1. Normal yt-dlp extraction.
      2. Alternate YouTube player clients.
      3. Cookie fallback when cookies are available.
      4. Alternate audio/video format fallback.
      5. Fresh extraction is performed for every retry.
    """

    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="

        self.reg = re.compile(
            r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
        )

        self.dl_stats = {
            "total_requests": 0,
            "direct_downloads": 0,
            "cookie_downloads": 0,
            "existing_files": 0,
            "fallback_attempts": 0,
            "failed_requests": 0,
        }

    # ---------------------------------------------------------
    # URL helpers
    # ---------------------------------------------------------

    @staticmethod
    def _clean_link(link: str) -> str:
        if not link:
            return link

        link = str(link).strip()

        # Remove tracking parameters while preserving the video ID.
        if "&" in link:
            link = link.split("&", 1)[0]

        if "?si=" in link:
            link = link.split("?si=", 1)[0]

        return link

    def _video_url(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ) -> str:

        if videoid:
            link = self.base + str(link)

        return self._clean_link(link)

    # ---------------------------------------------------------
    # yt-dlp options
    # ---------------------------------------------------------

    def _ydl_opts(
        self,
        cookies=None,
        player_client=None,
        **extra,
    ):
        """
        Build yt-dlp options.

        We intentionally let yt-dlp handle YouTube's current request
        headers/signatures instead of manually constructing media URLs.
        """

        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,

            # Retry transient HTTP failures.
            "retries": 3,
            "fragment_retries": 3,
            "file_access_retries": 3,

            # Do not abort immediately on temporary network errors.
            "extractor_retries": 2,

            # Avoid unnecessary IPv6 problems on some Railway hosts.
            "source_address": "0.0.0.0",

            # Normal browser-like headers.
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        if cookies:
            opts["cookiefile"] = cookies

        if player_client:
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": player_client,
                }
            }

        opts.update(extra)

        return opts

    # ---------------------------------------------------------
    # Search / metadata
    # ---------------------------------------------------------

    async def exists(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):
        link = self._video_url(link, videoid)
        return bool(re.search(self.regex, link))

    async def url(
        self,
        message_1: Message,
    ) -> Union[str, None]:

        messages = [message_1]

        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:

            if message.entities:
                text = message.text or message.caption or ""

                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        return text[
                            entity.offset:
                            entity.offset + entity.length
                        ]

            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url

        return None

    async def details(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(link, videoid)

        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])

        if not data:
            raise ValueError("No YouTube result found")

        result = data[0]

        title = result.get("title", "Unknown")
        duration_min = result.get("duration")

        thumbnails = result.get("thumbnails") or []
        thumbnail = (
            thumbnails[0].get("url", "").split("?")[0]
            if thumbnails
            else ""
        )

        vidid = result.get("id")

        duration_sec = (
            0
            if not duration_min
            else int(time_to_seconds(duration_min))
        )

        return (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid,
        )

    async def title(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(link, videoid)

        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])

        if not data:
            raise ValueError("No YouTube result found")

        return data[0].get("title", "Unknown")

    async def duration(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(link, videoid)

        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])

        if not data:
            raise ValueError("No YouTube result found")

        return data[0].get("duration")

    async def thumbnail(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(link, videoid)

        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])

        if not data:
            raise ValueError("No YouTube result found")

        thumbnails = data[0].get("thumbnails") or []

        if not thumbnails:
            return ""

        return thumbnails[0].get("url", "").split("?")[0]

    # ---------------------------------------------------------
    # Direct media URL
    # ---------------------------------------------------------

    async def video(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(link, videoid)

        attempts = [
            {
                "name": "default",
                "client": None,
            },
            {
                "name": "web",
                "client": ["web"],
            },
            {
                "name": "android",
                "client": ["android"],
            },
            {
                "name": "ios",
                "client": ["ios"],
            },
        ]

        last_error = None

        for attempt in attempts:

            try:
                logger.info(
                    f"YouTube direct URL attempt: "
                    f"{attempt['name']}"
                )

                opts = self._ydl_opts(
                    player_client=attempt["client"],
                    format=(
                        "best[height<=720][width<=1280]"
                        "/best[height<=720]"
                        "/best"
                    ),
                    skip_download=True,
                )

                direct_url = await asyncio.to_thread(
                    self._extract_direct,
                    link,
                    opts,
                )

                if direct_url:
                    return 1, direct_url

            except Exception as e:
                last_error = e

                logger.warning(
                    f"YouTube URL attempt "
                    f"{attempt['name']} failed: {e}"
                )

                self.dl_stats["fallback_attempts"] += 1

        logger.error(
            f"Unable to resolve YouTube media URL: "
            f"{last_error}"
        )

        return 0, str(
            last_error or
            "Unable to resolve YouTube media URL"
        )

    @staticmethod
    def _extract_direct(link, opts):

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                link,
                download=False,
            )

            if not info:
                return None

            return info.get("url")

    # ---------------------------------------------------------
    # Playlist
    # ---------------------------------------------------------

    async def playlist(
        self,
        link,
        limit,
        user_id,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(link, videoid)

        playlist = await Playlist.get(link)

        if not playlist:
            return None

        videos = []

        for video in playlist.get("videos", [])[:limit]:

            try:
                duration = video.get("duration")

                duration_sec = (
                    int(time_to_seconds(duration))
                    if duration
                    else 0
                )

                thumbnails = video.get("thumbnails") or []

                thumbnail = (
                    thumbnails[0].get("url", "").split("?")[0]
                    if thumbnails
                    else ""
                )

                videos.append(
                    {
                        "vidid": video.get("id"),
                        "title": video.get(
                            "title",
                            "Unknown",
                        ),
                        "duration_min": duration,
                        "duration_sec": duration_sec,
                        "thumbnail": thumbnail,
                    }
                )

            except Exception:
                continue

        return videos

    # ---------------------------------------------------------
    # Track
    # ---------------------------------------------------------

    async def track(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(link, videoid)

        results = VideosSearch(link, limit=1)
        data = (await results.next()).get("result", [])

        if not data:
            raise ValueError("No YouTube result found")

        result = data[0]

        thumbnails = result.get("thumbnails") or []

        thumb = (
            thumbnails[0].get("url", "").split("?")[0]
            if thumbnails
            else ""
        )

        track_details = {
            "title": result.get(
                "title",
                "Unknown",
            ),
            "link": result.get("link"),
            "vidid": result.get("id"),
            "duration_min": result.get("duration"),
            "thumb": thumb,
        }

        return (
            track_details,
            result.get("id"),
        )

    # ---------------------------------------------------------
    # Formats
    # ---------------------------------------------------------

    async def formats(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(link, videoid)

        def extract():

            with yt_dlp.YoutubeDL(
                self._ydl_opts()
            ) as ydl:

                info = ydl.extract_info(
                    link,
                    download=False,
                )

                available = []

                for fmt in info.get(
                    "formats",
                    [],
                ):

                    if (
                        "dash"
                        in str(
                            fmt.get("format", "")
                        ).lower()
                    ):
                        continue

                    available.append(
                        {
                            "format": fmt.get(
                                "format"
                            ),
                            "filesize": (
                                fmt.get("filesize")
                                or fmt.get(
                                    "filesize_approx"
                                )
                            ),
                            "format_id": fmt.get(
                                "format_id"
                            ),
                            "ext": fmt.get("ext"),
                            "format_note": fmt.get(
                                "format_note"
                            ),
                            "yturl": link,
                        }
                    )

                return available

        return (
            await asyncio.to_thread(extract),
            link,
        )

    # ---------------------------------------------------------
    # Slider
    # ---------------------------------------------------------

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(link, videoid)

        try:

            search = VideosSearch(
                link,
                limit=10,
            )

            search_results = (
                await search.next()
            ).get("result", [])

            results = []

            for result in search_results:

                duration_str = (
                    result.get("duration")
                    or "0:00"
                )

                try:

                    parts = duration_str.split(":")

                    if len(parts) == 3:

                        duration_secs = (
                            int(parts[0]) * 3600
                            + int(parts[1]) * 60
                            + int(parts[2])
                        )

                    elif len(parts) == 2:

                        duration_secs = (
                            int(parts[0]) * 60
                            + int(parts[1])
                        )

                    else:

                        duration_secs = 0

                    if duration_secs <= 3600:
                        results.append(result)

                except (
                    ValueError,
                    IndexError,
                ):
                    continue

            if (
                not results
                or query_type >= len(results)
            ):
                raise ValueError(
                    "No suitable videos found "
                    "within duration limit"
                )

            selected = results[query_type]

            thumbnails = (
                selected.get("thumbnails")
                or []
            )

            thumbnail = (
                thumbnails[0].get(
                    "url",
                    "",
                ).split("?")[0]
                if thumbnails
                else ""
            )

            return (
                selected.get(
                    "title",
                    "Unknown",
                ),
                selected.get("duration"),
                thumbnail,
                selected.get("id"),
            )

        except Exception as e:

            logger.error(
                f"Error in slider: {e}"
            )

            raise ValueError(
                "Failed to fetch video details"
            )

    # ---------------------------------------------------------
    # Download
    # ---------------------------------------------------------

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
    ):

        self.dl_stats["total_requests"] += 1

        vid_id = (
            str(link)
            if videoid
            else None
        )

        url = self._video_url(
            link,
            videoid,
        )

        os.makedirs(
            "downloads",
            exist_ok=True,
        )

        safe_id = re.sub(
            r"[^A-Za-z0-9_-]",
            "_",
            vid_id or "track",
        )

        is_video = bool(
            video or songvideo
        )

        output = os.path.join(
            "downloads",
            (
                f"{safe_id}.mp4"
                if is_video
                else f"{safe_id}.mp3"
            ),
        )

        # Existing valid file.
        if (
            os.path.exists(output)
            and os.path.getsize(output) > 0
        ):
            self.dl_stats[
                "existing_files"
            ] += 1

            return output, True

        # -----------------------------------------------------
        # Build fallback attempts
        # -----------------------------------------------------

        attempts = []

        # First attempt: normal yt-dlp.
        attempts.append(
            {
                "name": "default",
                "client": None,
                "cookies": None,
            }
        )

        # Alternate YouTube clients.
        attempts.extend(
            [
                {
                    "name": "web",
                    "client": ["web"],
                    "cookies": None,
                },
                {
                    "name": "android",
                    "client": ["android"],
                    "cookies": None,
                },
                {
                    "name": "ios",
                    "client": ["ios"],
                    "cookies": None,
                },
            ]
        )

        # -----------------------------------------------------
        # Cookie fallback
        # -----------------------------------------------------

        cookies = cookie_files()

        # Try a small number of cookie files rather than randomly
        # selecting a bad cookie on every request.
        if cookies:

            random.shuffle(cookies)

            for index, cookie in enumerate(cookies[:3]):

                attempts.append(
                    {
                        "name": f"cookie-{index + 1}",
                        "client": None,
                        "cookies": cookie,
                    }
                )

                attempts.append(
                    {
                        "name": f"cookie-web-{index + 1}",
                        "client": ["web"],
                        "cookies": cookie,
                    }
                )

        # -----------------------------------------------------
        # Format selection
        # -----------------------------------------------------

        if is_video:

            formats = [
                (
                    format_id
                    if format_id
                    else
                    "bestvideo[height<=720]"
                    "+bestaudio/"
                    "best[height<=720]/"
                    "best"
                ),
                "best[height<=720]/best",
                "best",
            ]

        else:

            formats = [
                (
                    format_id
                    if format_id
                    else
                    "bestaudio[ext=m4a]/"
                    "bestaudio/"
                    "best"
                ),
                "bestaudio/best",
                "best",
            ]

        last_error = None

        # -----------------------------------------------------
        # Try downloads
        # -----------------------------------------------------

        for attempt_index, attempt in enumerate(
            attempts
        ):

            for format_index, selected_format in enumerate(
                formats
            ):

                try:

                    logger.info(
                        "YouTube download attempt "
                        f"{attempt_index + 1}/"
                        f"{len(attempts)} "
                        f"({attempt['name']}) "
                        f"format={selected_format}"
                    )

                    ydl_opts = self._ydl_opts(
                        cookies=attempt[
                            "cookies"
                        ],
                        player_client=attempt[
                            "client"
                        ],
                        format=selected_format,
                        outtmpl=output,
                        noplaylist=True,

                        # Let yt-dlp retry temporary 403/
                        # network failures.
                        retries=3,
                        fragment_retries=3,

                        # Merge video/audio when needed.
                        merge_output_format=(
                            "mp4"
                            if is_video
                            else None
                        ),
                    )

                    if not is_video:

                        ydl_opts[
                            "postprocessors"
                        ] = [
                            {
                                "key":
                                "FFmpegExtractAudio",
                                "preferredcodec":
                                "mp3",
                                "preferredquality":
                                "192",
                            }
                        ]

                    await asyncio.to_thread(
                        self._download_sync,
                        url,
                        ydl_opts,
                    )

                    # yt-dlp may create a different extension
                    # before FFmpeg conversion.
                    if (
                        not os.path.exists(
                            output
                        )
                        and not is_video
                    ):

                        candidates = glob.glob(
                            os.path.join(
                                "downloads",
                                f"{safe_id}.*",
                            )
                        )

                        mp3_candidates = [
                            p
                            for p in candidates
                            if p.lower().endswith(
                                ".mp3"
                            )
                        ]

                        if mp3_candidates:
                            output = (
                                mp3_candidates[0]
                            )

                    # Success.
                    if (
                        os.path.exists(output)
                        and os.path.getsize(
                            output
                        ) > 0
                    ):

                        self.dl_stats[
                            "direct_downloads"
                        ] += 1

                        logger.info(
                            "YouTube download "
                            "successful: "
                            f"{attempt['name']}"
                        )

                        return output, True

                    raise RuntimeError(
                        "yt-dlp completed but "
                        "no media file was created"
                    )

                except Exception as e:

                    last_error = e

                    error_text = str(e)

                    if (
                        "403" in error_text
                        or "Forbidden"
                        in error_text
                    ):

                        logger.warning(
                            "YouTube returned "
                            "HTTP 403. Trying "
                            "fallback..."
                        )

                    else:

                        logger.warning(
                            "YouTube download "
                            f"failed: {e}"
                        )

                    self.dl_stats[
                        "fallback_attempts"
                    ] += 1

                    # Remove partial output.
                    self._remove_download_files(
                        safe_id
                    )

                    # Continue with next format/
                    # client/cookie combination.
                    continue

        self.dl_stats[
            "failed_requests"
        ] += 1

        logger.error(
            "All YouTube download attempts "
            f"failed: {last_error}"
        )

        raise RuntimeError(
            f"YouTube download failed: "
            f"{last_error}"
        )

    # ---------------------------------------------------------
    # Download helpers
    # ---------------------------------------------------------

    @staticmethod
    def _remove_download_files(
        safe_id: str,
    ):

        for candidate in glob.glob(
            os.path.join(
                "downloads",
                f"{safe_id}.*",
            )
        ):

            try:

                if os.path.isfile(
                    candidate
                ):
                    os.remove(candidate)

            except OSError:
                pass

    @staticmethod
    def _download_sync(
        url,
        opts,
    ):

        with yt_dlp.YoutubeDL(
            opts
        ) as ydl:

            ydl.download([url])
