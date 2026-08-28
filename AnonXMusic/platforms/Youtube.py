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

        return random.choice(txt_files)

    except Exception:
        return None


def cookie_files():
    """
    Return all valid cookie files.
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
    # CLEAN URL
    # =====================================================

    @staticmethod
    def _clean_link(link: str) -> str:

        if not link:
            return link

        link = str(link).strip()

        try:

            if "&si=" in link:
                link = link.split("&si=", 1)[0]

            if "?si=" in link:
                link = link.split("?si=", 1)[0]

            if "&feature=" in link:
                link = link.split("&feature=", 1)[0]

        except Exception:
            pass

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

            "fragment_retries": 5,

            "file_access_retries": 3,

            "extractor_retries": 3,

            "socket_timeout": 30,

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
        # WITHOUT COOKIE
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
        # COOKIE ATTEMPTS
        # -------------------------------------------------

        cookies = cookie_files()

        if cookies:

            random.shuffle(cookies)

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
            # MESSAGE URL
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
        Resolve a fresh YouTube direct URL.

        audio=True:
            Audio-only stream.

        audio=False:
            Video + audio stream.
        """

        link = self._video_url(
            link,
            videoid,
        )

        attempts = self._build_attempts()

        # -------------------------------------------------
        # AUDIO
        # -------------------------------------------------

        if audio:

            formats = [

                (
                    "bestaudio[ext=m4a]/"
                    "bestaudio[ext=webm]/"
                    "bestaudio/best"
                ),

                "bestaudio/best",

                "best",
            ]

        # -------------------------------------------------
        # VIDEO
        # -------------------------------------------------

        else:

            formats = [

                (
                    "best[height<=720]"
                    "[vcodec!=none]"
                    "[acodec!=none]"
                ),

                (
                    "best[height<=720]/best"
                ),

                "best",
            ]

        last_error = None

        # -------------------------------------------------
        # ATTEMPTS
        # -------------------------------------------------

        for attempt in attempts:

            for selected_format in formats:

                try:

                    logger.info(
                        "YouTube DIRECT STREAM: "
                        f"{attempt['name']} | "
                        f"{selected_format} | "
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

                        check_formats=False,

                    )

                    direct_url = (
                        await asyncio.to_thread(
                            self._extract_direct,
                            link,
                            opts,
                        )
                    )

                    if not direct_url:

                        raise RuntimeError(
                            "No direct media URL "
                            "returned by yt-dlp"
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
                        "YouTube direct URL "
                        "resolved successfully."
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
                        f"failed: {attempt['name']} "
                        f"| {selected_format} "
                        f"| {e}"
                    )

                    continue

        logger.error(
            "Unable to resolve YouTube "
            f"direct stream: {last_error}"
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
    ):
        """
        IMPORTANT:

        Do not manually select a random item from
        info['formats'].

        yt-dlp has already selected the requested
        format. We use info['url'] directly.

        This prevents audio/video mismatch and is
        especially important for long YouTube songs.
        """

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
            # NORMAL RESOLVED URL
            # -------------------------------------------------

            direct_url = info.get(
                "url"
            )

            if direct_url:

                return direct_url

            # -------------------------------------------------
            # REQUESTED FORMATS
            # -------------------------------------------------

            requested = (
                info.get(
                    "requested_formats"
                )
                or []
            )

            if requested:

                # Prefer a format that contains audio.
                for fmt in requested:

                    fmt_url = fmt.get(
                        "url"
                    )

                    acodec = fmt.get(
                        "acodec"
                    )

                    if (
                        fmt_url
                        and acodec
                        and acodec != "none"
                    ):

                        return fmt_url

                # Any valid requested URL.
                for fmt in requested:

                    fmt_url = fmt.get(
                        "url"
                    )

                    if fmt_url:

                        return fmt_url

            # -------------------------------------------------
            # LAST FALLBACK
            # -------------------------------------------------

            for fmt in (
                info.get(
                    "formats"
                )
                or []
            ):

                fmt_url = fmt.get(
                    "url"
                )

                if fmt_url:

                    return fmt_url

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

                    duration_sec = int(
                        time_to_seconds(
                            duration
                        )
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

            attempts = (
                self._build_attempts()
            )

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

                        if not info:

                            continue

                        available = []

                        for fmt in (
                            info.get(
                                "formats",
                                [],
                            )
                        ):

                            if (
                                "dash"
                                in str(
                                    fmt.get(
                                        "format",
                                        "",
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
                "Unable to fetch formats: "
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
                            int(parts[0]) * 3600
                            +
                            int(parts[1]) * 60
                            +
                            int(parts[2])
                        )

                    elif len(parts) == 2:

                        duration_secs = (
                            int(parts[0]) * 60
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
        # VIDEO
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
        # AUDIO
        # -------------------------------------------------

        else:

            formats = [

                (
                    format_id
                    if format_id
                    else
                    (
                        "bestaudio[ext=m4a]/"
                        "bestaudio/best"
                    )
                ),

                "bestaudio/best",

                "best",
            ]

        last_error = None

        # -------------------------------------------------
        # DOWNLOAD ATTEMPTS
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

                        retries=5,

                        fragment_retries=5,

                        file_access_retries=3,

                        merge_output_format=(
                            "mp4"
                            if is_video
                            else None
                        ),

                    )

                    # -------------------------------------------------
                    # AUDIO TO MP3
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
