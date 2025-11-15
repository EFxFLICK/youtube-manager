#!/usr/bin/env python3
"""
Youtube Manager CLI - improved version.

Features:
- List videos
- Add video (with stable incremental id)
- Update video by id
- Delete video by id (with confirmation)
- Search videos by title/description
- Safe JSON persistence (atomic write)
- Input validation and helpful prompts
- Logging for diagnostics

Compatible with Python 3.8+
"""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional

# ---------- Configuration ----------
DATA_FILE = "videos.json"  # use .json extension for clarity
LOG_FILE = "youtube_manager.log"

# Configure basic logging: DEBUG messages go to log file; user sees minimal prints
logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)


# ---------- Persistence helpers ----------
def load_data(file_path: str = DATA_FILE) -> List[Dict[str, Any]]:
    """
    Load list of videos from JSON file.
    If file missing -> return [].
    If file corrupted -> back it up and return [].
    """
    if not os.path.exists(file_path):
        logging.debug("Data file %s not found. Starting with empty list.", file_path)
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logging.warning("Data file %s contained non-list JSON; resetting to empty list.", file_path)
            return []
        return data
    except json.JSONDecodeError as exc:
        # Back up corrupted file to prevent data loss and allow manual recovery
        backup = file_path + ".corrupt"
        try:
            os.replace(file_path, backup)
            logging.error("JSON decode error while loading %s. Backed up to %s. Error: %s", file_path, backup, exc)
            print(f"Warning: data file was corrupted and moved to {backup}. Starting fresh.")
        except Exception as e:
            # If backup fails, log it
            logging.exception("Failed to back up corrupted data file: %s", e)
            print("Error: corrupted data file and failed to back it up. Check logs.")
        return []
    except Exception as e:
        logging.exception("Unexpected error while loading data: %s", e)
        print("Error reading data file. Check logs for details.")
        return []


def save_data_atomic(videos: List[Dict[str, Any]], file_path: str = DATA_FILE) -> None:
    """
    Save videos list to JSON file atomically using a temp file + os.replace.
    This avoids partial writes if the program crashes while writing.
    """
    try:
        dir_name = os.path.dirname(os.path.abspath(file_path)) or "."
        # Create temp file in same directory (so replace is atomic on most OSes)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp:
            json.dump(videos, tmp, ensure_ascii=False, indent=2)
            tmp_name = tmp.name
        os.replace(tmp_name, file_path)  # atomic replace
        logging.debug("Saved %d videos to %s", len(videos), file_path)
    except Exception as e:
        logging.exception("Failed to save data to %s: %s", file_path, e)
        print("Error: failed to save data. Check log for details.")


# ---------- Utility helpers ----------
def next_id(videos: List[Dict[str, Any]]) -> int:
    """Return next integer id (1-based incremental)."""
    if not videos:
        return 1
    try:
        max_id = max((int(v.get("id", 0)) for v in videos), default=0)
    except Exception:
        # If any id is malformed, fallback to length-based next id
        logging.exception("Malformed id encountered when computing next_id.")
        return len(videos) + 1
    return max_id + 1


def find_index_by_id(videos: List[Dict[str, Any]], video_id: int) -> Optional[int]:
    """Return index of video with given id or None if not found."""
    for idx, v in enumerate(videos):
        try:
            if int(v.get("id")) == video_id:
                return idx
        except Exception:
            continue
    return None


def prompt_nonempty(prompt_text: str) -> str:
    """Prompt until non-empty input is given (striped)."""
    while True:
        val = input(prompt_text).strip()
        if val:
            return val
        print("Input cannot be empty. Please try again.")


def prompt_int(prompt_text: str, allow_blank: bool = False) -> Optional[int]:
    """
    Prompt user for integer input.
    If allow_blank True, blank returns None (useful for cancelable prompts).
    Invalid numbers prompt once and return None (caller can re-ask or handle).
    """
    val = input(prompt_text).strip()
    if allow_blank and val == "":
        return None
    if not val.isdigit():
        print("Please enter a valid number.")
        return None
    return int(val)


def pretty_list(videos: List[Dict[str, Any]]) -> None:
    """Nicely print the list of videos."""
    if not videos:
        print("\nNo videos found. Add a new video with option 2.\n")
        return

    print("\n" + "*" * 60)
    print(f"{'ID':<6} {'Title':<35} {'Duration':<10} {'Tags'}")
    print("-" * 60)
    for v in videos:
        vid = v.get("id", "")
        name = v.get("name", "")[:34]  # truncate long titles for display
        time = v.get("time", "")
        tags = ", ".join(v.get("tags", [])) if isinstance(v.get("tags", []), list) else ""
        print(f"{str(vid):<6} {name:<35} {time:<10} {tags}")
    print("*" * 60 + "\n")


# ---------- CRUD operations ----------
def list_all_videos(videos: List[Dict[str, Any]]) -> None:
    """List videos to the user (wrapper around pretty_list)."""
    pretty_list(videos)


def add_video(videos: List[Dict[str, Any]]) -> None:
    """Prompt user and add a new video to the list."""
    print("\nAdd a new video (press Ctrl+C to cancel anytime):")
    try:
        name = prompt_nonempty("  Title: ")
        time = input("  Duration (e.g. 5:34) [optional]: ").strip()
        description = input("  Description (optional): ").strip()
        tags_raw = input("  Tags (comma-separated, optional): ").strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
        vid = {"id": next_id(videos), "name": name, "time": time, "description": description, "tags": tags}
        videos.append(vid)
        save_data_atomic(videos)
        print(f"Added video: id={vid['id']} title={vid['name']}")
    except KeyboardInterrupt:
        print("\nAdd cancelled by user.")


def update_video(videos: List[Dict[str, Any]]) -> None:
    """
    Update a video's fields by id.
    Prompts leave input blank to keep current value.
    """
    if not videos:
        print("No videos to update.")
        return

    pretty_list(videos)
    raw = input("Enter the video ID to update (blank to cancel): ").strip()
    if raw == "":
        print("Update cancelled.")
        return
    if not raw.isdigit():
        print("Please enter a valid numeric ID.")
        return
    vid_id = int(raw)
    idx = find_index_by_id(videos, vid_id)
    if idx is None:
        print(f"Video with id {vid_id} not found.")
        return

    video = videos[idx]
    # Show current values in prompt; blank keeps existing
    print("Leave blank to keep current value.")
    new_name = input(f"New Title [{video.get('name')}]: ").strip() or video.get("name", "")
    new_time = input(f"New Duration [{video.get('time', '')}]: ").strip() or video.get("time", "")
    new_desc = input(f"New Description [{video.get('description', '')}]: ").strip() or video.get("description", "")
    new_tags_raw = input("New Tags comma-separated (leave blank to keep current): ").strip()
    if new_tags_raw:
        new_tags = [t.strip() for t in new_tags_raw.split(",") if t.strip()]
    else:
        new_tags = video.get("tags", [])

    # Update
    video.update({"name": new_name, "time": new_time, "description": new_desc, "tags": new_tags})
    save_data_atomic(videos)
    print(f"Updated video id={vid_id}.")


def delete_video(videos: List[Dict[str, Any]]) -> None:
    """Delete video by id after confirmation."""
    if not videos:
        print("No videos to delete.")
        return

    pretty_list(videos)
    raw = input("Enter the video ID to delete (blank to cancel): ").strip()
    if raw == "":
        print("Delete cancelled.")
        return
    if not raw.isdigit():
        print("Please enter a valid numeric ID.")
        return
    vid_id = int(raw)
    idx = find_index_by_id(videos, vid_id)
    if idx is None:
        print(f"Video with id {vid_id} not found.")
        return

    # Confirm deletion
    confirm = input(f"Are you sure you want to delete id={vid_id} '{videos[idx].get('name')}'? Type 'yes' to confirm: ")
    if confirm.strip().lower() == "yes":
        deleted = videos.pop(idx)
        save_data_atomic(videos)
        print(f"Deleted video id={vid_id}.")
        logging.info("Deleted video: %s", deleted)
    else:
        print("Deletion cancelled.")


# ---------- Search & Sort ----------
def search_videos(videos: List[Dict[str, Any]]) -> None:
    """Search videos by title or description (case-insensitive)."""
    if not videos:
        print("No videos to search.")
        return
    q = input("Enter search query (title/description): ").strip()
    if not q:
        print("Empty query. Cancelled.")
        return
    q_lower = q.lower()
    hits = [v for v in videos if q_lower in v.get("name", "").lower() or q_lower in v.get("description", "").lower()]
    if not hits:
        print("No matches found.")
        return
    pretty_list(hits)


def sort_videos(videos: List[Dict[str, Any]]) -> None:
    """Sort videos in memory and save (by key: 'name' or 'time' or 'id')."""
    if not videos:
        print("No videos to sort.")
        return
    key = input("Sort by 'name', 'time' or 'id' (default 'name'): ").strip() or "name"
    if key not in ("name", "time", "id"):
        print("Invalid key. Cancelled.")
        return
    reverse_raw = input("Reverse order? (y/N): ").strip().lower()
    reverse = reverse_raw == "y"
    videos.sort(key=lambda v: v.get(key, ""), reverse=reverse)
    save_data_atomic(videos)
    print(f"Videos sorted by {key} {'descending' if reverse else 'ascending'}.")


# ---------- CLI Loop ----------
def main_loop():
    """Main interactive loop."""
    videos = load_data()
    MENU = """
Welcome to Youtube Manager - choose an option:
1. List all videos
2. Add a new video
3. Update a video
4. Delete a video
5. Search videos
6. Sort videos
7. Exit
"""
    try:
        while True:
            print(MENU)
            choice = input("Enter choice (1-7): ").strip()
            if choice == "1":
                list_all_videos(videos)
            elif choice == "2":
                add_video(videos)
            elif choice == "3":
                update_video(videos)
            elif choice == "4":
                delete_video(videos)
            elif choice == "5":
                search_videos(videos)
            elif choice == "6":
                sort_videos(videos)
            elif choice == "7":
                print("Goodbye!")
                break
            else:
                print("Please enter a number between 1 and 7.")
    except KeyboardInterrupt:
        # Graceful exit on Ctrl+C
        print("\nInterrupted. Exiting.")
    except Exception as e:
        # Catch-all to avoid hard crashes; log info for debugging
        logging.exception("Unexpected error in main loop: %s", e)
        print("An unexpected error occurred. Check log for details.")


if __name__ == "__main__":
    main_loop()
