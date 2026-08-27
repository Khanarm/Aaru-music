import os

from config import autoclean


async def auto_clean(popped):
    try:
        rem = popped.get("file")

        if not rem:
            return

        # Remove from autoclean list if present
        try:
            autoclean.remove(rem)
        except ValueError:
            pass

        # If the same file is still used by another queue item,
        # don't remove it.
        if autoclean.count(rem) > 0:
            return

        # Direct URLs are streams, NOT local files.
        if rem.startswith(("http://", "https://")):
            return

        # Queue references are not local files.
        if (
            str(rem).startswith("vid_")
            or str(rem).startswith("live_")
            or str(rem).startswith("index_")
        ):
            return

        # Only delete actual local files.
        if os.path.isfile(rem):
            try:
                os.remove(rem)
            except OSError:
                pass

    except Exception:
        pass
