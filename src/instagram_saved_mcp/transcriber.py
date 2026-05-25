"""Reel/video transcription — v0.2 STUB.

Not implemented in v0.1. The real flow (below) downloads the video with yt-dlp
and transcribes it with faster-whisper. Those are heavy dependencies, so they
live behind the optional ``transcribe`` extra rather than the base install.

This module intentionally performs NO downloads and NO network calls yet.
"""

from __future__ import annotations


def extras_installed() -> bool:
    """True if the optional transcription dependencies are importable."""
    try:
        import faster_whisper  # noqa: F401
        import yt_dlp  # noqa: F401
    except ImportError:
        return False
    return True


def transcribe(url: str) -> str:
    """Stub: report that transcription is planned for v0.2 and how to prepare."""
    hint = (
        "Transcription requires the optional extra. Install it with:\n"
        "    uvx instagram-saved-mcp[transcribe]\n"
        "(or: pip install 'instagram-saved-mcp[transcribe]')"
    )
    if extras_installed():
        hint = (
            "Transcription dependencies are installed, but the feature itself "
            "ships in v0.2."
        )
    return (
        f"transcribe_post is not implemented yet (planned for v0.2). {hint}\n"
        f"Requested URL: {url}"
    )


# TODO v0.2: implement real transcription.
#   1. Warn the user this downloads media, then download audio with yt-dlp:
#        import yt_dlp
#        opts = {"format": "bestaudio/best", "outtmpl": "<tmp>/%(id)s.%(ext)s", "quiet": True}
#        with yt_dlp.YoutubeDL(opts) as ydl:
#            info = ydl.extract_info(url, download=True)   # may need cookiefile when gated
#   2. Pick device with graceful GPU->CPU fallback:
#        from faster_whisper import WhisperModel
#        try:
#            model = WhisperModel("large-v3", device="cuda", compute_type="float16")
#        except Exception:
#            model = WhisperModel("base", device="cpu", compute_type="int8")
#   3. Transcribe and join segments:
#        segments, _info = model.transcribe(audio_path, beam_size=5)
#        text = " ".join(s.text.strip() for s in segments)
#   4. Persist via cache.update_transcript(url, text); clean up the temp file.
#   5. Return the transcript (cache-first on subsequent calls).
