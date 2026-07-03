from kel.realtime.audio import PcmPlaybackBuffer


def test_playback_buffer_tracks_played_audio_for_interruption() -> None:
    playback = PcmPlaybackBuffer(sample_rate=1_000)
    playback.append(item_id="item-1", content_index=0, audio=b"a" * 2_000)

    assert playback.read(500) == b"a" * 500
    progress = playback.interrupt()

    assert progress is not None
    assert progress.item_id == "item-1"
    assert progress.content_index == 0
    assert progress.audio_end_ms == 250
    assert playback.read(100) == b""


def test_playback_buffer_does_not_truncate_a_fully_drained_response() -> None:
    playback = PcmPlaybackBuffer(sample_rate=1_000)
    playback.append(item_id="item-1", content_index=0, audio=b"a" * 200)
    playback.read(200)

    assert playback.interrupt() is None


def test_playback_buffer_reports_playing_while_audio_remains() -> None:
    playback = PcmPlaybackBuffer(sample_rate=1_000)
    assert playback.is_playing() is False

    playback.append(item_id="item-1", content_index=0, audio=b"a" * 100)
    assert playback.is_playing() is True

    playback.read(100)
    assert playback.is_playing() is False


def test_playback_buffer_stops_playing_after_clear() -> None:
    playback = PcmPlaybackBuffer(sample_rate=1_000)
    playback.append(item_id="item-1", content_index=0, audio=b"a" * 100)

    playback.clear()

    assert playback.is_playing() is False
