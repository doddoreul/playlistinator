import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.metadata import parse_filename


def test_pattern_artist_title():
    r = parse_filename("Daft Punk - Harder Better.mp3")
    assert r["artist"] == "Daft Punk"
    assert r["title"] == "Harder Better"

def test_pattern_tracknum():
    r = parse_filename("01 - Daft Punk - Harder Better.mp3")
    assert r["tracknum"] == "01"
    assert r["artist"] == "Daft Punk"
    assert r["title"] == "Harder Better"

def test_pattern_artist_title_dash():
    r = parse_filename("DaftPunk-HarderBetter.mp3")
    assert r["artist"] == "DaftPunk"
    assert r["title"] == "HarderBetter"

def test_fallback_title():
    r = parse_filename("randomsong.mp3")
    assert r["title"] == "randomsong"
    assert r["artist"] is None