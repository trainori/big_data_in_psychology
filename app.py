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

    st.subheader("University of Chicago Online Consent Form for Research Participation")

    st.markdown(
        """
        **Study Number:** IRB19-1395  
        **Researcher:** Wilma A. Bainbridge, PhD  

        **Description:**  
        We are researchers at the University of Chicago doing a research study about how human sensation 
        (vision, audition) and memory interact. During this study, you will see visual stimuli 
        (e.g., images, videos, text) presented on a computer monitor, and/or hear sounds 
        (e.g., music, tones, voices, sounds from a video) through headphones or speakers. 
        You will respond to the task instructions with a button press, typing, mouse movement, 
        drawing, or speaking through a microphone. You may also be asked to complete questionnaires 
        that assess cognitive abilities. Participation will take less than 1 hour. Your participation 
        is voluntary and you can withdraw at any time, although data collected up until the point of 
        withdrawal may still be included in the analysis.

        **Incentives:**  
        Compensation will be provided as listed for the individual task. MTurk/Prolific does not allow 
        for prorated compensation. In the event of an incomplete HIT, you must contact the research team 
        and compensation will be determined based on what was completed and at the researchers' discretion.

        **Please note:**  
        This study contains attention checks to make sure that participants are finishing the tasks honestly 
        and completely. As long as you read the instructions and complete the tasks, your HIT will be approved. 
        If you fail these checks, your HIT will be rejected.

        **Risks and Benefits:**  
        Taking part in this research study may not benefit you personally, but we may learn new things that 
        could help others. Your participation in this study does not involve any risk to you beyond that of 
        everyday life.

        **Confidentiality:**  
        Your Mechanical Turk Worker ID / Prolific ID will be used to distribute payment to you but will not 
        be stored with the research data we collect from you. Please be aware that your MTurk Worker ID can 
        potentially be linked to information about you on your Amazon public profile page, depending on the 
        settings you have for your Amazon profile. We will not be accessing any personally identifying 
        information about you that you may have put on your Amazon public profile page. De-identified data 
        from this study may be used for future research studies or shared with other researchers for future 
        research without your additional informed consent. If you decide to withdraw from this study, data 
        collected up until the point of withdrawal may still be included in the analysis.

        **Contacts & Questions:**  
        If you have questions or concerns about the study, you can contact the Principal Investigator 
        Dr. Wilma A. Bainbridge at bainbridgelab@uchicago.edu.

        If you have any questions about your rights as a participant in this research, feel you have been 
        harmed, or wish to discuss other study-related concerns with someone who is not part of the research 
        team, you can contact the University of Chicago Social & Behavioral Sciences Institutional Review 
        Board Office by phone at (773) 702-2915, or by email at sbs-irb@uchicago.edu.

        **Consent:**  
        Participation is voluntary. Refusal to participate or withdrawing from the research will involve no 
        penalty or loss of benefits to which you might otherwise be entitled.

        By clicking **“Agree”** below, you confirm that you have read the consent form, are at least 
        18 years old, and agree to participate in the research. Please print or save a copy of this page 
        for your records.
        """
    )

    agreed = st.checkbox("I am at least 18 years old, have read the consent form, and agree to participate.")

    if st.button("Agree and Begin Study", type="primary", disabled=not agreed):
        prepare_experiment()
        st.session_state.phase = "feed"
        st.rerun()

    if st.button("I Do Not Agree"):
        st.warning("You have chosen not to participate. You may close this page.")

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