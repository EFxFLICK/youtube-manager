import pytest
import json
import os
import tempfile

# import the module under test
import youtube_manager as ym
# or import specific symbols you need, for example:
# from youtube_manager import load_videos, save_videos, add_video

@pytest.fixture
def tmp_data_file(tmp_path, monkeypatch):
    # Create a temp file path
    tmpfile = tmp_path / "test_videos.json"
    # Ensure module uses this file
    monkeypatch.setattr(ym, "DATA_FILE", str(tmpfile))
    # Ensure fresh start
    if tmpfile.exists():
        tmpfile.unlink()
    yield str(tmpfile)
    # cleanup
    if tmpfile.exists():
        tmpfile.unlink()

def test_add_video_and_load(tmp_path, monkeypatch):
     # Make the module use a temp data file (if your tests rely on ym.DATA_FILE)
    temp_file = tmp_path / "test_videos.json"
    monkeypatch.setattr(ym, "DATA_FILE", str(temp_file))

    # Mock prompt/input so add_video doesn't wait for stdin
    # If add_video calls prompt_nonempty, mock that instead.
    # Option 1: mock builtin input (works if prompt_nonempty uses input())
    monkeypatch.setattr("builtins.input", lambda prompt="": "My Test Title")

    # Option 2: or mock prompt_nonempty directly (uncomment if exists)
    # monkeypatch.setattr(ym, "prompt_nonempty", lambda prompt: "My Test Title")

    videos = ym.load_data(ym.DATA_FILE)
    assert videos == []  # empty initially

    # Add a video
    ym.add_video(videos)
    # after add_video interactive, direct way: simulate by appending and saving
    # but to keep test non-interactive, we implement direct append/save here:
    new = {"id": ym.next_id(videos), "name": "Test video", "time": "1:00", "description": "", "tags": []}
    videos.append(new)
    ym.save_data_atomic(videos, ym.DATA_FILE)

    loaded = ym.load_data(ym.DATA_FILE)
    assert len(loaded) == 1
    assert loaded[0]["name"] == "Test video"

def test_next_id(tmp_data_file):
    videos = []
    assert ym.next_id(videos) == 1
    videos.append({"id": 1})
    assert ym.next_id(videos) == 2

def test_update_and_delete(tmp_data_file):
    videos = []
    videos.append({"id": 1, "name": "A", "time": "1:00", "description": "", "tags": []})
    videos.append({"id": 2, "name": "B", "time": "2:00", "description": "", "tags": []})
    ym.save_data_atomic(videos, ym.DATA_FILE)

    # Update by finding index
    idx = ym.find_index_by_id(videos, 2)
    assert idx == 1
    videos[idx]["name"] = "B-updated"
    ym.save_data_atomic(videos, ym.DATA_FILE)
    loaded = ym.load_data(ym.DATA_FILE)
    assert loaded[1]["name"] == "B-updated"

    # Delete
    idx = ym.find_index_by_id(videos, 1)
    assert idx == 0
    videos.pop(idx)
    ym.save_data_atomic(videos, ym.DATA_FILE)
    loaded = ym.load_data(ym.DATA_FILE)
    assert len(loaded) == 1
    assert loaded[0]["id"] == 2
