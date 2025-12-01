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
    # Prepare a temporary JSON file for this test
    temp_file = tmp_path / "test_videos.json"
    monkeypatch.setattr(ym, "DATA_FILE", str(temp_file))

# Mock user input so add_video does not ask for real input
    monkeypatch.setattr("builtins.input", lambda prompt="": "My Test Title")

     # Ensure the file starts empty
    videos = ym.load_data(ym.DATA_FILE)
    assert videos == []

 # Call add_video which should now add a single video (input is mocked)
    ym.add_video(videos)
    # after add_video interactive, direct way: simulate by appending and saving
    # but to keep test non-interactive, we implement direct append/save here:
    try:
        ym.save_data_atomic(videos, ym.DATA_FILE)
    except AttributeError:
        # If your module uses a different function name for saving, skip this.
        pass
    # Reload and assert exactly one video exists with the expected title
    loaded = ym.load_data(ym.DATA_FILE)
    assert len(loaded) == 1
    assert loaded[0].get("title") == "My Test Title" or loaded[0].get("name") == "My Test Title"

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
