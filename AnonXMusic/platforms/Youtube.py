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


# =========================================================
# COOKIE HELPERS
# =========================================================


def cookie_txt_file():
    """
    Return one random cookie file from cookies/*.txt
    """

    try:
        folder_path = os.path.join(
            os.getcwd(),
            "cookies",
        )

        if not os.path.isdir(folder_path):
            return None

        txt_files = glob.glob(
            os.path.join(
                folder_path,
                "*.txt",
            )
        )

        if not txt_files:
            return None

        selected = random.choice(txt_files)

        return selected

    except Exception:
        return None


def cookie_files():
    """
    Return all cookie files.
    """

    try:
        folder_path = os.path.join(
            os.getcwd(),
            "cookies",
        )

        if not os.path.isdir(folder_path):
            return []

        files = glob.glob(
            os.path.join(
                folder_path,
                "*.txt",
            )
        )

        return [
            f
            for f in files
            if os.path.isfile(f)
            and os.path.getsize(f) > 0
        ]

    except Exception:
        return []


def valid_cookie_file(path):
    """
    Basic cookie file validation.
    Does not validate whether the cookies are still
    accepted by YouTube.
    """

    try:

        if not path:
            return False

        if not os.path.isfile(path):
            return False

        if os.path.getsize(path) <= 0:
            return False

        return True

    except Exception:
        return False


# =========================================================
# YOUTUBE API
# =========================================================


class YouTubeAPI:

    def __init__(self):

        self.base = (
            "https://www.youtube.com/watch?v="
        )

        self.regex = (
            r"(?:youtube\.com|youtu\.be)"
        )

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
    # URL CLEAN
    # =====================================================

    @staticmethod
    def _clean_link(link: str) -> str:

        if not link:
            return link

        link = str(link).strip()

        # Remove common tracking parameters.
        if "&si=" in link:
            link = link.split("&si=", 1)[0]

        if "?si=" in link:
            link = link.split("?si=", 1)[0]

        if "&feature=" in link:
            link = link.split("&feature=", 1)[0]

        return link

    # =====================================================
    # VIDEO URL
    # =====================================================

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
        player_client=None,
        **extra,
    ):

        opts = {

            "quiet": True,

            "no_warnings": True,

            "noplaylist": True,

            "restrictfilenames": True,

            "retries": 3,

            "fragment_retries": 3,

            "file_access_retries": 3,

            "extractor_retries": 3,

            "socket_timeout": 20,

            "source_address": "0.0.0.0",

            "nocheckcertificate": True,

            "geo_bypass": True,

            "concurrent_fragment_downloads": 3,

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

        # -------------------------------------------------
        # COOKIE
        # -------------------------------------------------

        if cookies and valid_cookie_file(cookies):

            opts["cookiefile"] = cookies

        # -------------------------------------------------
        # PLAYER CLIENT
        # -------------------------------------------------

        if player_client:

            opts["extractor_args"] = {
                "youtube": {
                    "player_client": player_client,
                }
            }

        opts.update(extra)

        return opts

    # =====================================================
    # BUILD ATTEMPTS
    # =====================================================

    def _build_attempts(self):

        attempts = []

        # -------------------------------------------------
        # NO COOKIE CLIENTS
        # -------------------------------------------------

        attempts.extend(
            [
                {
                    "name": "default",
                    "client": None,
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
                {
                    "name": "web",
                    "client": ["web"],
                    "cookies": None,
                },
            ]
        )

        # -------------------------------------------------
        # COOKIE CLIENTS
        # -------------------------------------------------

        cookies = cookie_files()

        if cookies:

            random.shuffle(cookies)

            # Maximum 5 cookies per request cycle.
            for index, cookie in enumerate(
                cookies[:5]
            ):

                attempts.append(
                    {
                        "name": (
                            f"cookie-{index + 1}"
                        ),
                        "client": None,
                        "cookies": cookie,
                    }
                )

                attempts.append(
                    {
                        "name": (
                            f"cookie-web-{index + 1}"
                        ),
                        "client": ["web"],
                        "cookies": cookie,
                    }
                )

                attempts.append(
                    {
                        "name": (
                            f"cookie-ios-{index + 1}"
                        ),
                        "client": ["ios"],
                        "cookies": cookie,
                    }
                )

        return attempts

    # =====================================================
    # EXISTS
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
    # URL FROM MESSAGE
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

            # -------------------------------------------------
            # NORMAL URL
            # -------------------------------------------------

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

                    if (
                        entity.type
                        == MessageEntityType.TEXT_LINK
                    ):

                        return entity.url

            # -------------------------------------------------
            # CAPTION URL
            # -------------------------------------------------

            if message.caption_entities:

                text = (
                    message.caption
                    or ""
                )

                for entity in (
                    message.caption_entities
                ):

                    if (
                        entity.type
                        == MessageEntityType.URL
                    ):

                        return text[
                            entity.offset:
                            entity.offset
                            + entity.length
                        ]

                    if (
                        entity.type
                        == MessageEntityType.TEXT_LINK
                    ):

                        return entity.url

        return None

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

        results = VideosSearch(
            link,
            limit=1,
        )

        data = (
            await results.next()
        ).get(
            "result",
            [],
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

        duration_sec = (
            0
            if not duration_min
            else int(
                time_to_seconds(
                    duration_min
                )
            )
        )

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

        results = VideosSearch(
            link,
            limit=1,
        )

        data = (
            await results.next()
        ).get(
            "result",
            [],
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

        results = VideosSearch(
            link,
            limit=1,
        )

        data = (
            await results.next()
        ).get(
            "result",
            [],
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

        results = VideosSearch(
            link,
            limit=1,
        )

        data = (
            await results.next()
        ).get(
            "result",
            [],
        )

        if not data:
            raise ValueError(
                "No YouTube result found"
            )

        thumbnails = (
            data[0].get(
                "thumbnails"
            )
            or []
        )

        if not thumbnails:
            return ""

        return thumbnails[0].get(
            "url",
            "",
        ).split("?")[0]

    # =====================================================
    # DIRECT STREAM
    # =====================================================

    async def video(
        self,
        link: str,
        videoid: Union[bool, str] = None,
        audio: bool = False,
    ):
        """
        Resolve a fresh YouTube direct media URL.

        audio=True:
            Return audio-only URL.

        audio=False:
            Return video URL with audio if available.
        """

        link = self._video_url(
            link,
            videoid,
        )

        attempts = self._build_attempts()

        # -------------------------------------------------
        # AUDIO FORMATS
        # -------------------------------------------------

        if audio:

            formats = [

                (
                    "bestaudio[ext=m4a]/"
                    "bestaudio[ext=webm]/"
                    "bestaudio/"
                    "best"
                ),

                "bestaudio/best",

                "best",
            ]

        # -------------------------------------------------
        # VIDEO FORMATS
        # -------------------------------------------------

        else:

            formats = [

                (
                    "bestvideo[height<=720]"
                    "+bestaudio/"
                    "best[height<=720]/"
                    "best"
                ),

                (
                    "bestvideo[height<=720]"
                    "+bestaudio/best"
                ),

                "best[height<=720]",

                "best",
            ]

        last_error = None

        # -------------------------------------------------
        # ATTEMPT LOOP
        # -------------------------------------------------

        for attempt in attempts:

            for selected_format in formats:

                try:

                    logger.info(
                        "YouTube DIRECT STREAM attempt: "
                        f"{attempt['name']} "
                        f"format={selected_format} "
                        f"audio={audio}"
                    )

                    opts = self._ydl_opts(

                        cookies=attempt[
                            "cookies"
                        ],

                        player_client=attempt[
                            "client"
                        ],

                        format=selected_format,

                        skip_download=True,

                        noplaylist=True,

                    )

                    direct_url = (
                        await asyncio.to_thread(
                            self._extract_direct,
                            link,
                            opts,
                            audio,
                        )
                    )

                    if direct_url:

                        if attempt[
                            "cookies"
                        ]:

                            self.dl_stats[
                                "cookie_downloads"
                            ] += 1

                        else:

                            self.dl_stats[
                                "direct_downloads"
                            ] += 1

                        logger.info(
                            "YouTube direct stream "
                            "URL resolved successfully."
                        )

                        return (
                            1,
                            direct_url,
                        )

                except Exception as e:

                    last_error = e

                    logger.warning(
                        "Direct YouTube stream failed: "
                        f"{attempt['name']} "
                        f"{selected_format}: {e}"
                    )

                    self.dl_stats[
                        "fallback_attempts"
                    ] += 1

                    continue

        logger.error(
            "Unable to resolve YouTube direct "
            f"stream URL: {last_error}"
        )

        return (
            0,
            str(
                last_error
                or
                "Unable to resolve YouTube media URL"
            ),
        )

    # =====================================================
    # EXTRACT DIRECT URL
    # =====================================================

    @staticmethod
    def _extract_direct(
        link,
        opts,
        audio=False,
    ):

        with yt_dlp.YoutubeDL(
            opts
        ) as ydl:

            info = ydl.extract_info(
                link,
                download=False,
            )

            if not info:

                return None

            # -------------------------------------------------
            # AUDIO
            # -------------------------------------------------

            if audio:

                formats = (
                    info.get(
                        "formats"
                    )
                    or []
                )

                audio_formats = []

                for fmt in formats:

                    url = fmt.get(
                        "url"
                    )

                    if not url:
                        continue

                    # Must have audio.
                    acodec = fmt.get(
                        "acodec"
                    )

                    if (
                        not acodec
                        or acodec == "none"
                    ):
                        continue

                    audio_formats.append(
                        fmt
                    )

                # Highest quality audio first.
                audio_formats.sort(
                    key=lambda x: (
                        x.get(
                            "abr"
                        )
                        or 0,
                        x.get(
                            "tbr"
                        )
                        or 0,
                    ),
                    reverse=True,
                )

                if audio_formats:

                    return audio_formats[
                        0
                    ].get("url")

                # Fallback.
                direct_url = info.get(
                    "url"
                )

                if direct_url:

                    return direct_url

                return None

            # -------------------------------------------------
            # VIDEO
            # -------------------------------------------------

            formats = (
                info.get(
                    "formats"
                )
                or []
            )

            video_formats = []

            for fmt in formats:

                url = fmt.get(
                    "url"
                )

                if not url:
                    continue

                vcodec = fmt.get(
                    "vcodec"
                )

                if (
                    not vcodec
                    or vcodec == "none"
                ):
                    continue

                video_formats.append(
                    fmt
                )

            # Prefer formats containing
            # both video and audio.
            combined = [
                fmt
                for fmt in video_formats
                if (
                    fmt.get(
                        "acodec"
                    )
                    and fmt.get(
                        "acodec"
                    ) != "none"
                )
            ]

            if combined:

                combined.sort(
                    key=lambda x: (
                        x.get(
                            "height"
                        )
                        or 0,
                        x.get(
                            "tbr"
                        )
                        or 0,
                    ),
                    reverse=True,
                )

                return combined[
                    0
                ].get("url")

            # Video-only fallback.
            if video_formats:

                video_formats.sort(
                    key=lambda x: (
                        x.get(
                            "height"
                        )
                        or 0,
                        x.get(
                            "tbr"
                        )
                        or 0,
                    ),
                    reverse=True,
                )

                return video_formats[
                    0
                ].get("url")

            # Final fallback.
            direct_url = info.get(
                "url"
            )

            if direct_url:

                return direct_url

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

                duration_sec = (
                    int(
                        time_to_seconds(
                            duration
                        )
                    )
                    if duration
                    else 0
                )

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

        results = VideosSearch(
            link,
            limit=1,
        )

        data = (
            await results.next()
        ).get(
            "result",
            [],
        )

        if not data:

            raise ValueError(
                "No YouTube result found"
            )

        result = data[0]

        thumbnails = (
            result.get(
                "thumbnails"
            )
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
            result.get(
                "id"
            ),
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

            attempts = self._build_attempts()

            last_error = None

            for attempt in attempts:

                try:

                    opts = self._ydl_opts(
                        cookies=attempt[
                            "cookies"
                        ],
                        player_client=attempt[
                            "client"
                        ],
                    )

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
                                "dash"
                                in str(
                                    fmt.get(
                                        "format",
                                        ""
                                    )
                                ).lower()
                            ):
                                continue

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

                        if available:

                            return available

                except Exception as e:

                    last_error = e

                    continue

            raise RuntimeError(
                f"Unable to fetch formats: "
                f"{last_error}"
            )

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
                    or
                    "0:00"
                )

                try:

                    parts = (
                        duration_str.split(":")
                    )

                    if len(parts) == 3:

                        duration_secs = (
                            int(parts[0])
                            * 3600
                            +
                            int(parts[1])
                            * 60
                            +
                            int(parts[2])
                        )

                    elif len(parts) == 2:

                        duration_secs = (
                            int(parts[0])
                            * 60
                            +
                            int(parts[1])
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
                or
                query_type >= len(results)
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
            video
            or songvideo
        )

        output = os.path.join(
            "downloads",
            (
                f"{safe_id}.mp4"
                if is_video
                else
                f"{safe_id}.mp3"
            ),
        )

        # -------------------------------------------------
        # EXISTING FILE
        # -------------------------------------------------

        if (
            os.path.exists(output)
            and
            os.path.getsize(output) > 0
        ):

            self.dl_stats[
                "existing_files"
            ] += 1

            return (
                output,
                True,
            )

        attempts = self._build_attempts()

        # -------------------------------------------------
        # VIDEO FORMAT
        # -------------------------------------------------

        if is_video:

            formats = [

                (
                    format_id
                    if format_id
                    else
                    (
                        "bestvideo[height<=720]"
                        "+bestaudio/"
                        "best[height<=720]/"
                        "best"
                    )
                ),

                (
                    "best[height<=720]/best"
                ),

                "best",
            ]

        # -------------------------------------------------
        # AUDIO FORMAT
        # -------------------------------------------------

        else:

            formats = [

                (
                    format_id
                    if format_id
                    else
                    (
                        "bestaudio[ext=m4a]/"
                        "bestaudio/"
                        "best"
                    )
                ),

                "bestaudio/best",

                "best",
            ]

        last_error = None

        # -------------------------------------------------
        # DOWNLOAD LOOP
        # -------------------------------------------------

        for attempt in attempts:

            for selected_format in formats:

                try:

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

                        retries=3,

                        fragment_retries=3,

                        merge_output_format=(
                            "mp4"
                            if is_video
                            else None
                        ),
                    )

                    # -------------------------------------------------
                    # AUDIO POST PROCESSING
                    # -------------------------------------------------

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

                    # -------------------------------------------------
                    # FIND MP3
                    # -------------------------------------------------

                    if (
                        not os.path.exists(
                            output
                        )
                        and
                        not is_video
                    ):

                        candidates = (
                            glob.glob(
                                os.path.join(
                                    "downloads",
                                    f"{safe_id}.*",
                                )
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

                    # -------------------------------------------------
                    # SUCCESS
                    # -------------------------------------------------

                    if (
                        os.path.exists(
                            output
                        )
                        and
                        os.path.getsize(
                            output
                        ) > 0
                    ):

                        if attempt[
                            "cookies"
                        ]:

                            self.dl_stats[
                                "cookie_downloads"
                            ] += 1

                        else:

                            self.dl_stats[
                                "direct_downloads"
                            ] += 1

                        return (
                            output,
                            True,
                        )

                    raise RuntimeError(
                        "yt-dlp completed but "
                        "no media file was created"
                    )

                except Exception as e:

                    last_error = e

                    self.dl_stats[
                        "fallback_attempts"
                    ] += 1

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
