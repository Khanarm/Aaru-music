import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup

from pytgcalls import PyTgCalls
from pytgcalls import filters as fl
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import (
    AudioQuality,
    ChatUpdate,
    GroupCallConfig,
    MediaStream,
    StreamEnded,
    Update,
    VideoQuality,
)

from ntgcalls import FFmpegError, TelegramServerError

import config
from config import autoclean

from AnonXMusic import LOGGER, YouTube, app
from AnonXMusic.misc import db

from AnonXMusic.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)

from AnonXMusic.utils.exceptions import AssistantErr
from AnonXMusic.utils.formatters import (
    check_duration,
    seconds_to_min,
    speed_converter,
)
from AnonXMusic.utils.inline.play import stream_markup
from AnonXMusic.utils.thumbnails import get_thumb

from strings import get_string


# ============================================================
# GLOBALS
# ============================================================

autoend = {}
counter = {}


# ============================================================
# CLEAR CHAT
# ============================================================

async def _clear_(chat_id):
    db[chat_id] = []

    try:
        await remove_active_video_chat(chat_id)
    except Exception:
        pass

    try:
        await remove_active_chat(chat_id)
    except Exception:
        pass


# ============================================================
# CALL CLASS
# ============================================================

class Call(PyTgCalls):

    def __init__(self):
        # ----------------------------------------------------
        # USERBOT 1
        # ----------------------------------------------------
        self.userbot1 = Client(
            name="AnonXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )

        self.one = PyTgCalls(
            self.userbot1,
            cache_duration=100,
        )

        # ----------------------------------------------------
        # USERBOT 2
        # ----------------------------------------------------
        self.userbot2 = Client(
            name="AnonXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )

        self.two = PyTgCalls(
            self.userbot2,
            cache_duration=100,
        )

        # ----------------------------------------------------
        # USERBOT 3
        # ----------------------------------------------------
        self.userbot3 = Client(
            name="AnonXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )

        self.three = PyTgCalls(
            self.userbot3,
            cache_duration=100,
        )

        # ----------------------------------------------------
        # USERBOT 4
        # ----------------------------------------------------
        self.userbot4 = Client(
            name="AnonXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )

        self.four = PyTgCalls(
            self.userbot4,
            cache_duration=100,
        )

        # ----------------------------------------------------
        # USERBOT 5
        # ----------------------------------------------------
        self.userbot5 = Client(
            name="AnonXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )

        self.five = PyTgCalls(
            self.userbot5,
            cache_duration=100,
        )

    # ========================================================
    # PAUSE
    # ========================================================

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    # ========================================================
    # RESUME
    # ========================================================

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    # ========================================================
    # STOP
    # ========================================================

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)

        try:
            await _clear_(chat_id)
            await assistant.leave_call(chat_id)
        except Exception:
            pass

    # ========================================================
    # FORCE STOP
    # ========================================================

    async def stop_stream_force(self, chat_id: int):

        assistants = [
            (config.STRING1, self.one),
            (config.STRING2, self.two),
            (config.STRING3, self.three),
            (config.STRING4, self.four),
            (config.STRING5, self.five),
        ]

        for string, assistant in assistants:
            if not string:
                continue

            try:
                await assistant.leave_call(chat_id)
            except Exception:
                pass

        try:
            await _clear_(chat_id)
        except Exception:
            pass

    # ========================================================
    # SPEED STREAM
    # ========================================================

    async def speedup_stream(
        self,
        chat_id: int,
        file_path,
        speed,
        playing,
    ):
        assistant = await group_assistant(self, chat_id)

        if str(speed) != "1.0":

            base = os.path.basename(file_path)

            chatdir = os.path.join(
                os.getcwd(),
                "playback",
                str(speed),
            )

            os.makedirs(
                chatdir,
                exist_ok=True,
            )

            out = os.path.join(
                chatdir,
                base,
            )

            if not os.path.isfile(out):

                speed_values = {
                    "0.5": 2.0,
                    "0.75": 1.35,
                    "1.5": 0.68,
                    "2.0": 0.5,
                }

                vs = speed_values.get(str(speed))

                if vs is None:
                    raise AssistantErr(
                        "Unsupported playback speed."
                    )

                proc = await asyncio.create_subprocess_shell(
                    (
                        "ffmpeg "
                        "-y "
                        "-i "
                        f'"{file_path}" '
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f'"{out}"'
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                await proc.communicate()

                if proc.returncode != 0:
                    raise AssistantErr(
                        "Unable to change playback speed."
                    )

        else:
            out = file_path

        dur = await asyncio.get_event_loop().run_in_executor(
            None,
            check_duration,
            out,
        )

        dur = int(dur)

        played, con_seconds = speed_converter(
            playing[0]["played"],
            speed,
        )

        duration = seconds_to_min(dur)

        if playing[0]["streamtype"] == "video":

            stream = MediaStream(
                out,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
                ffmpeg_parameters=(
                    f"-ss {played} "
                    f"-to {duration}"
                ),
            )

        else:

            stream = MediaStream(
                out,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
                ffmpeg_parameters=(
                    f"-ss {played} "
                    f"-to {duration}"
                ),
            )

        if str(db[chat_id][0]["file"]) != str(file_path):
            raise AssistantErr("Stream changed.")

        await assistant.play(
            chat_id,
            stream,
        )

        if str(db[chat_id][0]["file"]) == str(file_path):

            exis = playing[0].get("old_dur")

            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]

            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    # ========================================================
    # FORCE STOP CURRENT STREAM
    # ========================================================

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)

        try:
            check = db.get(chat_id)

            if check:
                check.pop(0)

        except Exception:
            pass

        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)

        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass

    # ========================================================
    # SKIP STREAM
    # ========================================================

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)

        if video:

            stream = MediaStream(
                link,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
            )

        else:

            stream = MediaStream(
                link,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
            )

        await assistant.play(
            chat_id,
            stream,
        )

    # ========================================================
    # SEEK STREAM
    # ========================================================

    async def seek_stream(
        self,
        chat_id,
        file_path,
        to_seek,
        duration,
        mode,
    ):
        assistant = await group_assistant(self, chat_id)

        if mode == "video":

            stream = MediaStream(
                file_path,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
                ffmpeg_parameters=(
                    f"-ss {to_seek} "
                    f"-to {duration}"
                ),
            )

        else:

            stream = MediaStream(
                file_path,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
                ffmpeg_parameters=(
                    f"-ss {to_seek} "
                    f"-to {duration}"
                ),
            )

        await assistant.play(
            chat_id,
            stream,
        )

    # ========================================================
    # STREAM CALL
    # ========================================================

    async def stream_call(self, link):
        assistant = await group_assistant(
            self,
            config.LOGGER_ID,
        )

        await assistant.play(
            config.LOGGER_ID,
            MediaStream(link),
        )

        await asyncio.sleep(0.2)

        try:
            await assistant.leave_call(
                config.LOGGER_ID,
            )
        except Exception:
            pass

    # ========================================================
    # JOIN CALL
    # ========================================================

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(
            self,
            chat_id,
        )

        language = await get_lang(chat_id)
        _ = get_string(language)

        if video:

            stream = MediaStream(
                link,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
            )

        else:

            stream = MediaStream(
                link,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
            )

        try:

            await assistant.play(
                chat_id,
                stream,
                config=GroupCallConfig(
                    auto_start=False,
                ),
            )

        except NoActiveGroupCall:

            raise AssistantErr(
                _["call_8"]
            )

        except FFmpegError:

            LOGGER(__name__).warning(
                "ffmpeg/ffprobe is not installed."
            )

            raise AssistantErr(
                "⚠️ <b>ffmpeg</b> is not installed "
                "on this server.\n\n"
                "Install it using:\n"
                "<code>apt install ffmpeg</code>"
            )

        except TelegramServerError:

            raise AssistantErr(
                _["call_10"]
            )

        await add_active_chat(chat_id)
        await music_on(chat_id)

        if video:
            await add_active_video_chat(chat_id)

        if await is_autoend():

            counter[chat_id] = {}

            try:
                users = len(
                    await assistant.get_participants(
                        chat_id
                    )
                )
            except Exception:
                users = 0

            if users == 1:

                autoend[chat_id] = (
                    datetime.now()
                    + timedelta(minutes=1)
                )

    # ========================================================
    # CHANGE STREAM
    # ========================================================

    async def change_stream(
        self,
        client,
        chat_id,
    ):
        check = db.get(chat_id)

        if not check:
            await _clear_(chat_id)

            try:
                await client.leave_call(chat_id)
            except Exception:
                pass

            return

        popped = None

        loop = await get_loop(chat_id)

        try:

            if loop == 0:

                popped = check.pop(0)

            else:

                loop = loop - 1

                await set_loop(
                    chat_id,
                    loop,
                )

            if popped:

                rem = popped.get("file")

                if rem:
                    try:
                        autoclean.remove(rem)
                    except Exception:
                        pass

            if not check:

                await _clear_(chat_id)

                try:
                    await client.leave_call(
                        chat_id
                    )
                except Exception:
                    pass

                return

        except Exception as e:

            LOGGER(__name__).error(
                f"Queue change error: {e}"
            )

            try:
                await _clear_(chat_id)
                await client.leave_call(chat_id)
            except Exception:
                pass

            return

        # ----------------------------------------------------
        # NEXT QUEUED SONG
        # ----------------------------------------------------

        queued = check[0]["file"]

        language = await get_lang(chat_id)
        _ = get_string(language)

        title = check[0]["title"].title()
        user = check[0]["by"]
        user_id = check[0]["user_id"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]

        db[chat_id][0]["played"] = 0

        exis = check[0].get("old_dur")

        if exis:

            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = (
                check[0]["old_second"]
            )
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0

        video = (
            str(streamtype) == "video"
        )

        # ----------------------------------------------------
        # YOUTUBE QUEUED TRACK
        # ----------------------------------------------------

        if str(queued).startswith("vid_"):

            mystic = await app.send_message(
                original_chat_id,
                _["call_7"],
            )

            try:

                code, direct_url = await YouTube.video(
                    videoid,
                    True,
                    audio=not video,
                )

                if code == 0:
                    raise Exception(
                        "Unable to resolve YouTube stream."
                    )

            except Exception as e:

                LOGGER(__name__).error(
                    f"YouTube resolve error: {e}"
                )

                try:
                    await mystic.edit_text(
                        _["call_6"],
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass

                return

            if video:

                stream = MediaStream(
                    direct_url,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.SD_480p,
                )

            else:

                stream = MediaStream(
                    direct_url,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.Flags.IGNORE,
                )

            try:

                await client.play(
                    chat_id,
                    stream,
                )

            except Exception as e:

                LOGGER(__name__).error(
                    f"YouTube direct stream error: {e}"
                )

                try:
                    await app.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                except Exception:
                    pass

                return

            img = await get_thumb(
                videoid,
                user_id,
            )

            button = stream_markup(
                _,
                chat_id,
            )

            try:
                await mystic.delete()
            except Exception:
                pass

            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    (
                        f"https://t.me/{app.username}"
                        f"?start=info_{videoid}"
                    ),
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(
                    button
                ),
            )

            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

            return

        # ----------------------------------------------------
        # LIVE STREAM
        # ----------------------------------------------------

        elif str(queued).startswith("live_"):

            try:

                n, link = await YouTube.video(
                    videoid,
                    True,
                    audio=not video,
                )

                if n == 0:

                    await app.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )

                    return

            except Exception:

                try:
                    await app.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                except Exception:
                    pass

                return

            if video:

                stream = MediaStream(
                    link,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.SD_480p,
                )

            else:

                stream = MediaStream(
                    link,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.Flags.IGNORE,
                )

            try:

                await client.play(
                    chat_id,
                    stream,
                )

            except Exception:

                try:
                    await app.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                except Exception:
                    pass

                return

            img = await get_thumb(
                videoid,
                user_id,
            )

            button = stream_markup(
                _,
                chat_id,
            )

            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    (
                        f"https://t.me/{app.username}"
                        f"?start=info_{videoid}"
                    ),
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(
                    button
                ),
            )

            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

            return

        # ----------------------------------------------------
        # INDEX / M3U8
        # ----------------------------------------------------

        elif str(queued).startswith("index_"):

            if str(streamtype) == "video":

                stream = MediaStream(
                    videoid,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.SD_480p,
                )

            else:

                stream = MediaStream(
                    videoid,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.Flags.IGNORE,
                )

            try:

                await client.play(
                    chat_id,
                    stream,
                )

            except Exception:

                try:
                    await app.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                except Exception:
                    pass

                return

            button = stream_markup(
                _,
                chat_id,
            )

            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(
                    user
                ),
                reply_markup=InlineKeyboardMarkup(
                    button
                ),
            )

            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

            return

        # ----------------------------------------------------
        # TELEGRAM / SOUNDCLOUD / LOCAL FILE
        # ----------------------------------------------------

        else:

            if video:

                stream = MediaStream(
                    queued,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.SD_480p,
                )

            else:

                stream = MediaStream(
                    queued,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.Flags.IGNORE,
                )

            try:

                await client.play(
                    chat_id,
                    stream,
                )

            except Exception as e:

                LOGGER(__name__).error(
                    f"Queued stream error: {e}"
                )

                try:
                    await app.send_message(
                        original_chat_id,
                        text=_["call_6"],
                    )
                except Exception:
                    pass

                return

            # ------------------------------------------------
            # TELEGRAM
            # ------------------------------------------------

            if videoid == "telegram":

                button = stream_markup(
                    _,
                    chat_id,
                )

                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=(
                        config.TELEGRAM_AUDIO_URL
                        if str(streamtype) == "audio"
                        else config.TELEGRAM_VIDEO_URL
                    ),
                    caption=_["stream_1"].format(
                        config.SUPPORT_CHAT,
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        button
                    ),
                )

                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            # ------------------------------------------------
            # SOUNDCLOUD
            # ------------------------------------------------

            elif videoid == "soundcloud":

                button = stream_markup(
                    _,
                    chat_id,
                )

                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.SOUNCLOUD_IMG_URL,
                    caption=_["stream_1"].format(
                        config.SUPPORT_CHAT,
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        button
                    ),
                )

                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            # ------------------------------------------------
            # OTHER
            # ------------------------------------------------

            else:

                img = await get_thumb(
                    videoid,
                    user_id,
                )

                button = stream_markup(
                    _,
                    chat_id,
                )

                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        (
                            f"https://t.me/{app.username}"
                            f"?start=info_{videoid}"
                        ),
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        button
                    ),
                )

                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

    # ========================================================
    # PING
    # ========================================================

    async def ping(self):
        pings = []

        assistants = [
            (config.STRING1, self.one),
            (config.STRING2, self.two),
            (config.STRING3, self.three),
            (config.STRING4, self.four),
            (config.STRING5, self.five),
        ]

        for string, assistant in assistants:

            if not string:
                continue

            try:
                ping = assistant.ping

                if callable(ping):
                    ping = ping()

                if asyncio.iscoroutine(ping):
                    ping = await ping

                pings.append(float(ping))

            except Exception:
                continue

        if not pings:
            return "0.0"

        return str(
            round(
                sum(pings) / len(pings),
                3,
            )
        )

    # ========================================================
    # START ALL CALL CLIENTS
    # ========================================================

    async def start(self):
        LOGGER(__name__).info(
            "Starting PyTgCalls Clients..."
        )

        assistants = [
            (config.STRING1, self.one),
            (config.STRING2, self.two),
            (config.STRING3, self.three),
            (config.STRING4, self.four),
            (config.STRING5, self.five),
        ]

        for string, assistant in assistants:

            if not string:
                continue

            try:

                await assistant.start()

                LOGGER(__name__).info(
                    "PyTgCalls assistant started."
                )

            except Exception as e:

                LOGGER(__name__).error(
                    f"Unable to start PyTgCalls assistant: {e}"
                )

    # ========================================================
    # DECORATORS / EVENTS
    # ========================================================

    async def decorators(self):

        # ----------------------------------------------------
        # CHAT CLOSED / LEFT / KICKED
        # ----------------------------------------------------

        chat_filter = fl.chat_update(
            ChatUpdate.Status.KICKED
            | ChatUpdate.Status.LEFT_GROUP
            | ChatUpdate.Status.CLOSED_VOICE_CHAT
        )

        @self.one.on_update(chat_filter)
        @self.two.on_update(chat_filter)
        @self.three.on_update(chat_filter)
        @self.four.on_update(chat_filter)
        @self.five.on_update(chat_filter)
        async def stream_services_handler(
            client,
            update: Update,
        ):
            await self.stop_stream(
                update.chat_id
            )

        # ----------------------------------------------------
        # STREAM ENDED
        # ----------------------------------------------------

        @self.one.on_update(fl.stream_end())
        @self.two.on_update(fl.stream_end())
        @self.three.on_update(fl.stream_end())
        @self.four.on_update(fl.stream_end())
        @self.five.on_update(fl.stream_end())
        async def stream_end_handler(
            client: PyTgCalls,
            update: StreamEnded,
        ):
            await self.change_stream(
                client,
                update.chat_id,
            )


# ============================================================
# GLOBAL INSTANCE
# ============================================================

Anony = Call()
