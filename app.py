import os
import time
import uuid
import random
import requests
from datetime import datetime

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Social Media Study",
    page_icon="🧠",
    layout="centered",
)

IMAGE_DIR = "images"
N_FEED_ITEMS = 10
N_FOILS = 4


def append_row_to_supabase(row: dict) -> None:
    url = st.secrets["SUPABASE_URL"].rstrip("/")
    key = st.secrets["SUPABASE_KEY"]

    endpoint = f"{url}/rest/v1/responses"

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    response = requests.post(endpoint, json=row, headers=headers, timeout=10)

    if response.status_code not in [200, 201, 204]:
        raise Exception(
            f"Supabase insert failed: {response.status_code} - {response.text}"
        )


def infer_metadata_from_filename(filename: str) -> dict:
    stem = os.path.splitext(filename)[0].lower()
    tokens = stem.split("_")
    base_token = tokens[0]

    category_map = {
        "beach": "travel",
        "eiffel": "travel",
        "forest": "travel",
        "lighthouse": "travel",
        "ocean": "travel",
        "sunset": "travel",
        "trees": "travel",
    }

    category = category_map.get(base_token, "unknown")
    has_face = 1 if "person" in tokens else 0
    has_text = 0

    if "bright" in tokens or "brighter" in tokens:
        colorfulness = "bright"
    elif "dark" in tokens or "darker" in tokens:
        colorfulness = "dark"
    else:
        colorfulness = "unknown"

    if base_token in {"ocean", "forest", "lighthouse"}:
        visual_complexity = "low"
    elif base_token in {"eiffel", "sunset", "trees", "beach"}:
        visual_complexity = "medium"
    else:
        visual_complexity = "unknown"

    return {
        "category": category,
        "has_face": has_face,
        "has_text": has_text,
        "colorfulness": colorfulness,
        "visual_complexity": visual_complexity,
    }


def load_stimuli(image_dir: str) -> list[dict]:
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp"}

    if not os.path.exists(image_dir):
        return []

    files = []
    for fname in sorted(os.listdir(image_dir)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in allowed_exts:
            metadata = infer_metadata_from_filename(fname)
            files.append(
                {
                    "post_id": os.path.splitext(fname)[0],
                    "image_path": os.path.join(image_dir, fname),
                    **metadata,
                }
            )

    return files


def initialize_session_state() -> None:
    defaults = {
        "participant_id": str(uuid.uuid4()),
        "phase": "consent",
        "stimuli": [],
        "feed_order": [],
        "memory_items": [],
        "feed_index": 0,
        "memory_index": 0,
        "current_start_time": None,
        "responses": [],
        "liked_posts": set(),
        "supabase_error": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def prepare_experiment() -> None:
    stimuli = load_stimuli(IMAGE_DIR)

    if len(stimuli) < N_FEED_ITEMS + N_FOILS:
        st.error(
            f"You need at least {N_FEED_ITEMS + N_FOILS} images in your images/ folder."
        )
        st.stop()

    shuffled = stimuli.copy()
    random.shuffle(shuffled)

    seen_items = shuffled[:N_FEED_ITEMS]
    foil_items = shuffled[N_FEED_ITEMS:N_FEED_ITEMS + N_FOILS]

    memory_items = [{**item, "was_seen": 1} for item in seen_items]
    memory_items += [{**item, "was_seen": 0} for item in foil_items]
    random.shuffle(memory_items)

    st.session_state.stimuli = stimuli
    st.session_state.feed_order = seen_items
    st.session_state.memory_items = memory_items
    st.session_state.feed_index = 0
    st.session_state.memory_index = 0
    st.session_state.responses = []
    st.session_state.liked_posts = set()
    st.session_state.current_start_time = time.time()
    st.session_state.supabase_error = None


def log_response(row: dict) -> None:
    st.session_state.responses.append(row)

    try:
        append_row_to_supabase(row)
    except Exception as e:
        st.session_state.supabase_error = str(e)


def reset_study() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def render_header() -> None:
    st.title("Social Media Study")
    st.caption("A classroom research project on engagement and memory")

    if st.session_state.get("supabase_error"):
        st.warning(
            "Data may not be saving to Supabase right now. "
            "Please check your connection or table permissions."
        )
        st.error(st.session_state.supabase_error)


def render_progress(current: int, total: int, label: str) -> None:
    progress = current / total if total > 0 else 0
    st.progress(progress, text=f"{label}: {current} / {total}")


def render_consent() -> None:
    render_header()

    st.subheader("Consent")
    st.write(
        "You are being asked to take part in a short study about how people view "
        "and remember social media content. Your responses are anonymous. Please "
        "do not enter any personal identifying information."
    )
    st.write(
        "By continuing, you confirm that you are at least 18 years old and consent "
        "to participate in this study."
    )

    agreed = st.checkbox("I agree to participate.")

    if st.button("Begin Study", type="primary", disabled=not agreed):
        prepare_experiment()
        st.session_state.phase = "feed"
        st.rerun()


def render_feed() -> None:
    render_header()

    feed_items = st.session_state.feed_order
    idx = st.session_state.feed_index
    total = len(feed_items)

    if idx >= total:
        st.session_state.phase = "distractor"
        st.session_state.current_start_time = time.time()
        st.rerun()

    item = feed_items[idx]
    post_id = item["post_id"]
    liked_already = post_id in st.session_state.liked_posts

    render_progress(idx + 1, total, "Viewing feed")

    st.subheader("View this post as you normally would")
    st.image(item["image_path"], use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "❤️ Liked" if liked_already else "🤍 Like",
            key=f"like_{idx}",
            use_container_width=True,
        ):
            if not liked_already:
                st.session_state.liked_posts.add(post_id)
            else:
                st.session_state.liked_posts.remove(post_id)
            st.rerun()

    with col2:
        if st.button("Next", key=f"next_{idx}", use_container_width=True):
            end_time = time.time()
            start_time = st.session_state.current_start_time or end_time
            dwell_time = round(end_time - start_time, 3)

            row = {
                "participant_id": st.session_state.participant_id,
                "timestamp_utc": datetime.utcnow().isoformat(),
                "phase": "feed",
                "post_id": item["post_id"],
                "category": item.get("category"),
                "has_face": item.get("has_face"),
                "has_text": item.get("has_text"),
                "colorfulness": item.get("colorfulness"),
                "visual_complexity": item.get("visual_complexity"),
                "was_seen": 1,
                "liked": 1 if post_id in st.session_state.liked_posts else 0,
                "response": None,
                "correct": None,
                "confidence": None,
                "dwell_time_sec": dwell_time,
                "feed_position": idx + 1,
            }

            log_response(row)

            st.session_state.feed_index += 1
            st.session_state.current_start_time = time.time()
            st.rerun()


def render_distractor() -> None:
    render_header()

    st.subheader("Quick reset task")
    st.write("Before the memory section, please answer this simple question.")

    choice = st.radio(
        "Which of these do you prefer?",
        ["Coffee", "Tea", "Neither"],
        index=None,
    )

    if st.button("Continue to Memory Test", type="primary", disabled=choice is None):
        row = {
            "participant_id": st.session_state.participant_id,
            "timestamp_utc": datetime.utcnow().isoformat(),
            "phase": "distractor",
            "post_id": None,
            "category": None,
            "has_face": None,
            "has_text": None,
            "colorfulness": None,
            "visual_complexity": None,
            "was_seen": None,
            "liked": None,
            "response": choice,
            "correct": None,
            "confidence": None,
            "dwell_time_sec": None,
            "feed_position": None,
        }

        log_response(row)
        st.session_state.phase = "memory"
        st.session_state.current_start_time = time.time()
        st.rerun()


def render_memory_test() -> None:
    render_header()

    memory_items = st.session_state.memory_items
    idx = st.session_state.memory_index
    total = len(memory_items)

    if idx >= total:
        st.session_state.phase = "done"
        st.rerun()

    item = memory_items[idx]
    render_progress(idx + 1, total, "Memory test")

    st.subheader("Have you seen this post before in the feed?")
    st.image(item["image_path"], use_container_width=True)

    seen_before = st.radio(
        "Your answer:",
        ["Yes, I saw it", "No, I did not see it"],
        index=None,
        key=f"memory_answer_{idx}",
    )

    confidence = st.slider(
        "How confident are you?",
        min_value=1,
        max_value=5,
        value=3,
        key=f"confidence_{idx}",
    )

    if st.button("Submit Answer", type="primary", disabled=seen_before is None):
        end_time = time.time()
        start_time = st.session_state.current_start_time or end_time
        dwell_time = round(end_time - start_time, 3)

        guessed_seen = 1 if seen_before == "Yes, I saw it" else 0
        correct = 1 if guessed_seen == item["was_seen"] else 0

        row = {
            "participant_id": st.session_state.participant_id,
            "timestamp_utc": datetime.utcnow().isoformat(),
            "phase": "memory",
            "post_id": item["post_id"],
            "category": item.get("category"),
            "has_face": item.get("has_face"),
            "has_text": item.get("has_text"),
            "colorfulness": item.get("colorfulness"),
            "visual_complexity": item.get("visual_complexity"),
            "was_seen": item["was_seen"],
            "liked": None,
            "response": str(guessed_seen),
            "correct": correct,
            "confidence": confidence,
            "dwell_time_sec": dwell_time,
            "feed_position": None,
        }

        log_response(row)

        st.session_state.memory_index += 1
        st.session_state.current_start_time = time.time()
        st.rerun()


def render_done() -> None:
    render_header()

    st.success("You have completed the study. Thank you!")
    st.write("Your responses have been recorded.")

    if st.button("Start Over"):
        reset_study()

    with st.expander("Researcher view: session summary"):
        df = pd.DataFrame(st.session_state.responses)
        st.dataframe(df, use_container_width=True)


def main() -> None:
    initialize_session_state()

    phase = st.session_state.phase

    if phase == "consent":
        render_consent()
    elif phase == "feed":
        render_feed()
    elif phase == "distractor":
        render_distractor()
    elif phase == "memory":
        render_memory_test()
    elif phase == "done":
        render_done()
    else:
        st.error("Unknown app state. Resetting session.")
        reset_study()


if __name__ == "__main__":
    main()