import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.audio_source import validate_url


def test_valid_https():
    ok, _ = validate_url("https://example.com/song.mp3")
    assert ok

def test_invalid_scheme():
    ok, msg = validate_url("ftp://example.com/song.mp3")
    assert not ok

def test_empty():
    ok, _ = validate_url("")
    assert not ok

def test_no_host():
    ok, _ = validate_url("https:///song.mp3")
    assert not ok