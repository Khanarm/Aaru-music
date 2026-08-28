import asyncio
import glob
import os
import re
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from ytSearch import VideosSearch, Playlist

from AnonXMusic import LOGGER
from AnonXMusic.utils.formatters import time_to_seconds


logger = LOGGER(__name__)


# =========================================================
# COOKIE SUPPORT
# =========================================================

def cookie_txt_file():
    """
    Return one cookies/*.txt file if available.

    Cookies are optional.
    No browser extraction or cookie rotation is performed.
    """

    folder_path = os.path.join(
        os.getcwd(),
        "cookies",
    )

    if not os.path.isdir(folder_path):
        return None

    files = sorted(
        glob.glob(
            os.path.join(folder_path, "*.txt")
        )
    )

    return files[0] if files else None


def cookie_files():
    """
    Return available cookie files.

    Used only when the deployment explicitly provides
    a cookies/*.txt file.
    """

    folder_path = os.path.join(
        os.getcwd(),
        "cookies",
    )

    if not os.path.isdir(folder_path):
        return []

    return sorted(
        glob.glob(
            os.path.join(folder_path, "*.txt")
        )
    )


# =========================================================
# YOUTUBE API
# =========================================================

class YouTubeAPI:

    def __init__(self):

        self.base = (
            "https://www.youtube.com/watch?v="
        )

        self.regex = r"(?:youtube\.com|youtu\.be)"

        self.status = (
            "https://www.youtube.com/oembed?url="
        )

        self.listbase = (
            "https://youtube.com/playlist?list="
        )

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

    # =====================================================
    # URL
    # =====================================================

    @staticmethod
    def _clean_link(link: str) -> str:

        if not link:
            return link

        link = str(link).strip()

        # Remove Telegram / tracking fragments.
        link = link.split("#", 1)[0]

        # Keep the video ID from normal YouTube watch URLs.
        if "youtube.com/watch?" in link:

            match = re.search(
                r"[?&]v=([^&]+)",
                link,
            )

            if match:
                return (
                    "https://www.youtube.com/watch?v="
                    + match.group(1)
                )

        # youtu.be/<id>
        if "youtu.be/" in link:

            match = re.search(
                r"youtu\.be/([^?&/]+)",
                link,
            )

            if match:
                return (
                    "https://www.youtube.com/watch?v="
                    + match.group(1)
                )

        return link

    def _video_url(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ) -> str:

        if videoid:
            link = self.base + str(link)

        return self._clean_link(link)

    # =====================================================
    # YT-DLP OPTIONS
    # =====================================================

    def _ydl_opts(
        self,
        cookies=None,
        **extra,
    ):

        opts = {

            "quiet": True,

            "no_warnings": True,

            "noplaylist": True,

            "restrictfilenames": True,

            "nocheckcertificate": True,

            "retries": 3,

            "fragment_retries": 3,

            "file_access_retries": 3,

            "extractor_retries": 2,

            "continuedl": True,

            "concurrent_fragment_downloads": 1,

            "source_address": "0.0.0.0",

            "socket_timeout": 20,

            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(X11; Linux x86_64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 "
                    "Safari/537.36"
                ),
                "Accept-Language": (
                    "en-US,en;q=0.9"
                ),
            },
        }

        if cookies:
            if os.path.isfile(cookies):
                opts["cookiefile"] = cookies

        opts.update(extra)

        return opts

    # =====================================================
    # SEARCH / EXIST
    # =====================================================

    async def exists(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(
            link,
            videoid,
        )

        return bool(
            re.search(
                self.regex,
                link,
            )
        )

    # =====================================================
    # URL FROM TELEGRAM MESSAGE
    # =====================================================

    async def url(
        self,
        message_1: Message,
    ) -> Union[str, None]:

        messages = [message_1]

        if message_1.reply_to_message:
            messages.append(
                message_1.reply_to_message
            )

        for message in messages:

            if message.entities:

                text = (
                    message.text
                    or message.caption
                    or ""
                )

                for entity in message.entities:

                    if (
                        entity.type
                        == MessageEntityType.URL
                    ):

                        return text[
                            entity.offset:
                            entity.offset
                            + entity.length
                        ]

            if message.caption_entities:

                for entity in message.caption_entities:

                    if (
                        entity.type
                        == MessageEntityType.TEXT_LINK
                    ):

                        return entity.url

        return None

    # =====================================================
    # SEARCH HELPER
    # =====================================================

    async def _search(
        self,
        query: str,
        limit: int = 1,
    ):

        results = VideosSearch(
            query,
            limit=limit,
        )

        data = await results.next()

        return data.get(
            "result",
            [],
        )

    # =====================================================
    # DETAILS
    # =====================================================

    async def details(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(
            link,
            videoid,
        )

        data = await self._search(
            link,
            1,
        )

        if not data:
            raise ValueError(
                "No YouTube result found"
            )

        result = data[0]

        title = result.get(
            "title",
            "Unknown",
        )

        duration_min = result.get(
            "duration"
        )

        thumbnails = (
            result.get("thumbnails")
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

        vidid = result.get("id")

        duration_sec = 0

        if duration_min:

            try:
                duration_sec = int(
                    time_to_seconds(
                        duration_min
                    )
                )

            except Exception:
                duration_sec = 0

        return (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid,
        )

    # =====================================================
    # TITLE
    # =====================================================

    async def title(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(
            link,
            videoid,
        )

        data = await self._search(
            link,
            1,
        )

        if not data:
            raise ValueError(
                "No YouTube result found"
            )

        return data[0].get(
            "title",
            "Unknown",
        )

    # =====================================================
    # DURATION
    # =====================================================

    async def duration(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(
            link,
            videoid,
        )

        data = await self._search(
            link,
            1,
        )

        if not data:
            raise ValueError(
                "No YouTube result found"
            )

        return data[0].get(
            "duration"
        )

    # =====================================================
    # THUMBNAIL
    # =====================================================

    async def thumbnail(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(
            link,
            videoid,
        )

        data = await self._search(
            link,
            1,
        )

        if not data:
            raise ValueError(
                "No YouTube result found"
            )

        thumbnails = (
            data[0].get("thumbnails")
            or []
        )

        if not thumbnails:
            return ""

        return thumbnails[0].get(
            "url",
            "",
        ).split("?")[0]

    # =====================================================
    # DIRECT STREAM URL
    # =====================================================

    async def video(
        self,
        link: str,
        videoid: Union[bool, str] = None,
        audio: bool = False,
    ):
        """
        Resolve a fresh direct media URL.

        No media is downloaded here.

        Cookies are optional. If YouTube requires
        authentication for the current request, the
        caller should use the download fallback or
        provide an authorized cookie file.
        """

        link = self._video_url(
            link,
            videoid,
        )

        self.dl_stats[
            "total_requests"
        ] += 1

        if audio:

            formats = [
                "bestaudio[ext=m4a]/bestaudio/best",
                "bestaudio/best",
                "best",
            ]

        else:

            formats = [
                (
                    "best[height<=720][width<=1280]"
                    "/best[height<=720]/best"
                ),
                "best[height<=720]/best",
                "best",
            ]

        # First try without cookies.
        attempts = [
            {
                "name": "direct",
                "cookies": None,
            }
        ]

        # Optional explicit cookie file.
        cookie = cookie_txt_file()

        if cookie:

            attempts.append(
                {
                    "name": "configured-cookie",
                    "cookies": cookie,
                }
            )

        last_error = None

        for attempt in attempts:

            for selected_format in formats:

                try:

                    logger.info(
                        "YouTube direct stream: "
                        f"{attempt['name']} "
                        f"format={selected_format}"
                    )

                    opts = self._ydl_opts(
                        cookies=attempt[
                            "cookies"
                        ],
                        format=selected_format,
                        skip_download=True,
                        noplaylist=True,
                    )

                    direct_url = await asyncio.to_thread(
                        self._extract_direct,
                        link,
                        opts,
                    )

                    if direct_url:

                        if attempt["cookies"]:
                            self.dl_stats[
                                "cookie_downloads"
                            ] += 1
                        else:
                            self.dl_stats[
                                "direct_downloads"
                            ] += 1

                        logger.info(
                            "YouTube direct stream "
                            "URL resolved."
                        )

                        return (
                            1,
                            direct_url,
                        )

                except Exception as e:

                    last_error = e

                    self.dl_stats[
                        "fallback_attempts"
                    ] += 1

                    logger.warning(
                        "YouTube direct stream "
                        f"failed: {e}"
                    )

        logger.error(
            "Unable to resolve YouTube "
            f"direct stream URL: {last_error}"
        )

        return (
            0,
            str(
                last_error
                or
                "Unable to resolve "
                "YouTube media URL"
            ),
        )

    # =====================================================
    # DIRECT EXTRACTION
    # =====================================================

    @staticmethod
    def _extract_direct(
        link,
        opts,
    ):

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                link,
                download=False,
            )

            if not info:
                return None

            # Single-format extraction.
            direct_url = info.get(
                "url"
            )

            if direct_url:
                return direct_url

            # Format list fallback.
            formats = (
                info.get("formats")
                or []
            )

            # Prefer audio-only formats.
            audio_formats = [
                fmt
                for fmt in formats
                if fmt.get("acodec")
                not in (
                    None,
                    "none",
                )
                and fmt.get("vcodec")
                in (
                    None,
                    "none",
                )
                and fmt.get("url")
            ]

            if audio_formats:

                # Prefer m4a/mp4.
                audio_formats.sort(
                    key=lambda x: (
                        x.get("ext")
                        not in (
                            "m4a",
                            "mp4",
                        ),
                        -(
                            x.get(
                                "abr"
                            )
                            or 0
                        ),
                    )
                )

                return audio_formats[0][
                    "url"
                ]

            # Generic fallback.
            for fmt in reversed(formats):

                url = fmt.get(
                    "url"
                )

                if url:
                    return url

            return None

    # =====================================================
    # PLAYLIST
    # =====================================================

    async def playlist(
        self,
        link,
        limit,
        user_id,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(
            link,
            videoid,
        )

        playlist = await Playlist.get(
            link
        )

        if not playlist:
            return None

        videos = []

        for video in playlist.get(
            "videos",
            [],
        )[:limit]:

            try:

                duration = video.get(
                    "duration"
                )

                duration_sec = 0

                if duration:

                    try:
                        duration_sec = int(
                            time_to_seconds(
                                duration
                            )
                        )

                    except Exception:
                        duration_sec = 0

                thumbnails = (
                    video.get(
                        "thumbnails"
                    )
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

                videos.append(
                    {
                        "vidid": video.get(
                            "id"
                        ),
                        "title": video.get(
                            "title",
                            "Unknown",
                        ),
                        "duration_min": duration,
                        "duration_sec": (
                            duration_sec
                        ),
                        "thumbnail": thumbnail,
                    }
                )

            except Exception:
                continue

        return videos

    # =====================================================
    # TRACK
    # =====================================================

    async def track(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(
            link,
            videoid,
        )

        data = await self._search(
            link,
            1,
        )

        if not data:
            raise ValueError(
                "No YouTube result found"
            )

        result = data[0]

        thumbnails = (
            result.get("thumbnails")
            or []
        )

        thumb = (
            thumbnails[0].get(
                "url",
                "",
            ).split("?")[0]
            if thumbnails
            else ""
        )

        track_details = {
            "title": result.get(
                "title",
                "Unknown",
            ),
            "link": result.get(
                "link"
            ),
            "vidid": result.get(
                "id"
            ),
            "duration_min": result.get(
                "duration"
            ),
            "thumb": thumb,
        }

        return (
            track_details,
            result.get("id"),
        )

    # =====================================================
    # FORMATS
    # =====================================================

    async def formats(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(
            link,
            videoid,
        )

        def extract():

            opts = self._ydl_opts()

            with yt_dlp.YoutubeDL(
                opts
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
                        fmt.get("vcodec")
                        == "none"
                        and fmt.get("acodec")
                        not in (
                            None,
                            "none",
                        )
                    ):

                        available.append(
                            {
                                "format": fmt.get(
                                    "format"
                                ),
                                "filesize": (
                                    fmt.get(
                                        "filesize"
                                    )
                                    or
                                    fmt.get(
                                        "filesize_approx"
                                    )
                                ),
                                "format_id": fmt.get(
                                    "format_id"
                                ),
                                "ext": fmt.get(
                                    "ext"
                                ),
                                "format_note": fmt.get(
                                    "format_note"
                                ),
                                "yturl": link,
                            }
                        )

                return available

        return (
            await asyncio.to_thread(
                extract
            ),
            link,
        )

    # =====================================================
    # SLIDER
    # =====================================================

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):

        link = self._video_url(
            link,
            videoid,
        )

        try:

            search = VideosSearch(
                link,
                limit=10,
            )

            search_results = (
                await search.next()
            ).get(
                "result",
                [],
            )

            results = []

            for result in search_results:

                duration_str = (
                    result.get(
                        "duration"
                    )
                    or "0:00"
                )

                try:

                    parts = duration_str.split(
                        ":"
                    )

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
                        results.append(
                            result
                        )

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

            selected = results[
                query_type
            ]

            thumbnails = (
                selected.get(
                    "thumbnails"
                )
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
                selected.get(
                    "duration"
                ),
                thumbnail,
                selected.get(
                    "id"
                ),
            )

        except Exception as e:

            logger.error(
                f"Error in slider: {e}"
            )

            raise ValueError(
                "Failed to fetch video details"
            )

    # =====================================================
    # DOWNLOAD
    # =====================================================

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

        self.dl_stats[
            "total_requests"
        ] += 1

        # -------------------------------------------------
        # Resolve video ID
        # -------------------------------------------------

        if videoid:
            vid_id = str(link)

        else:
            vid_id = None

            match = re.search(
                r"(?:v=|youtu\.be/)([^&?/]+)",
                str(link),
            )

            if match:
                vid_id = match.group(1)

        url = self._video_url(
            link,
            videoid,
        )

        # -------------------------------------------------
        # Downloads directory
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Final expected path
        # -------------------------------------------------

        if is_video:

            output = os.path.join(
                "downloads",
                f"{safe_id}.mp4",
            )

        else:

            output = os.path.join(
                "downloads",
                f"{safe_id}.mp3",
            )

        # -------------------------------------------------
        # Existing file
        # -------------------------------------------------

        if (
            os.path.exists(output)
            and os.path.getsize(output) > 0
        ):

            self.dl_stats[
                "existing_files"
            ] += 1

            return (
                output,
                True,
            )

        # -------------------------------------------------
        # Formats
        # -------------------------------------------------

        if is_video:

            if format_id:

                formats = [
                    format_id,
                    (
                        "bestvideo[height<=720]"
                        "+bestaudio/"
                        "best[height<=720]/best"
                    ),
                    "best[height<=720]/best",
                    "best",
                ]

            else:

                formats = [
                    (
                        "bestvideo[height<=720]"
                        "+bestaudio/"
                        "best[height<=720]/best"
                    ),
                    "best[height<=720]/best",
                    "best",
                ]

        else:

            if format_id:

                formats = [
                    format_id,
                    "bestaudio[ext=m4a]/bestaudio/best",
                    "bestaudio/best",
                    "best",
                ]

            else:

                formats = [
                    "bestaudio[ext=m4a]/bestaudio/best",
                    "bestaudio/best",
                    "best",
                ]

        # -------------------------------------------------
        # Attempt list
        # -------------------------------------------------

        attempts = [
            {
                "name": "direct",
                "cookies": None,
            }
        ]

        cookie = cookie_txt_file()

        if cookie:

            attempts.append(
                {
                    "name": "configured-cookie",
                    "cookies": cookie,
                }
            )

        last_error = None

        # -------------------------------------------------
        # Download
        # -------------------------------------------------

        for attempt in attempts:

            for selected_format in formats:

                try:

                    logger.info(
                        "YouTube download attempt: "
                        f"{attempt['name']} "
                        f"format={selected_format}"
                    )

                    self._remove_download_files(
                        safe_id
                    )

                    # Use a temporary output name.
                    temp_output = os.path.join(
                        "downloads",
                        f"{safe_id}.%(ext)s",
                    )

                    ydl_opts = self._ydl_opts(
                        cookies=attempt[
                            "cookies"
                        ],
                        format=selected_format,
                        outtmpl=temp_output,
                        noplaylist=True,
                        skip_download=False,
                    )

                    # -------------------------------------
                    # AUDIO
                    # -------------------------------------

                    if not is_video:

                        ydl_opts[
                            "postprocessors"
                        ] = [
                            {
                                "key": (
                                    "FFmpegExtractAudio"
                                ),
                                "preferredcodec": "mp3",
                                "preferredquality": "192",
                            }
                        ]

                        ydl_opts[
                            "postprocessor_args"
                        ] = {
                            "ffmpeg": [
                                "-vn",
                            ]
                        }

                    # -------------------------------------
                    # VIDEO
                    # -------------------------------------

                    else:

                        ydl_opts[
                            "merge_output_format"
                        ] = "mp4"

                    await asyncio.to_thread(
                        self._download_sync,
                        url,
                        ydl_opts,
                    )

                    # -------------------------------------
                    # Find resulting media
                    # -------------------------------------

                    candidates = []

                    for path in glob.glob(
                        os.path.join(
                            "downloads",
                            f"{safe_id}.*",
                        )
                    ):

                        if (
                            os.path.isfile(path)
                            and os.path.getsize(path)
                            > 0
                        ):

                            if not path.endswith(
                                ".part"
                            ):

                                candidates.append(
                                    path
                                )

                    if not candidates:

                        raise RuntimeError(
                            "yt-dlp completed but "
                            "no media file was created"
                        )

                    # -------------------------------------
                    # Prefer final extension
                    # -------------------------------------

                    if is_video:

                        preferred = [
                            p
                            for p in candidates
                            if p.lower().endswith(
                                ".mp4"
                            )
                        ]

                    else:

                        preferred = [
                            p
                            for p in candidates
                            if p.lower().endswith(
                                ".mp3"
                            )
                        ]

                    if preferred:

                        final_file = max(
                            preferred,
                            key=os.path.getsize,
                        )

                    else:

                        final_file = max(
                            candidates,
                            key=os.path.getsize,
                        )

                    # -------------------------------------
                    # Rename to expected path
                    # -------------------------------------

                    if (
                        os.path.abspath(
                            final_file
                        )
                        != os.path.abspath(
                            output
                        )
                    ):

                        try:

                            if os.path.exists(
                                output
                            ):

                                os.remove(
                                    output
                                )

                            os.replace(
                                final_file,
                                output,
                            )

                        except OSError:

                            output = final_file

                    # -------------------------------------
                    # Validate
                    # -------------------------------------

                    if (
                        not os.path.exists(
                            output
                        )
                        or
                        os.path.getsize(
                            output
                        ) <= 0
                    ):

                        raise RuntimeError(
                            "Downloaded file is "
                            "empty or missing"
                        )

                    if attempt["cookies"]:

                        self.dl_stats[
                            "cookie_downloads"
                        ] += 1

                    else:

                        self.dl_stats[
                            "direct_downloads"
                        ] += 1

                    logger.info(
                        "YouTube download "
                        "successful: "
                        f"{output}"
                    )

                    return (
                        output,
                        True,
                    )

                except Exception as e:

                    last_error = e

                    self.dl_stats[
                        "fallback_attempts"
                    ] += 1

                    logger.warning(
                        "YouTube download failed: "
                        f"{attempt['name']} "
                        f"{selected_format}: {e}"
                    )

                    self._remove_download_files(
                        safe_id
                    )

                    continue

        self.dl_stats[
            "failed_requests"
        ] += 1

        raise RuntimeError(
            "YouTube download failed: "
            f"{last_error}"
        )

    # =====================================================
    # REMOVE DOWNLOAD FILES
    # =====================================================

    @staticmethod
    def _remove_download_files(
        safe_id: str,
    ):

        pattern = os.path.join(
            "downloads",
            f"{safe_id}.*",
        )

        for candidate in glob.glob(
            pattern
        ):

            try:

                if os.path.isfile(
                    candidate
                ):

                    os.remove(
                        candidate
                    )

            except OSError:
                pass

    # =====================================================
    # DOWNLOAD SYNC
    # =====================================================

    @staticmethod
    def _download_sync(
        url,
        opts,
    ):

        with yt_dlp.YoutubeDL(
            opts
        ) as ydl:

            ydl.download(
                [url]
            )
