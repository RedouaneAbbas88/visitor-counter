import streamlit as st
import cv2
from ultralytics import YOLO
import pandas as pd
from datetime import datetime

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="Visitor Counter", layout="wide")
st.title("📊 Visitor Counter - Stand Foire")

# URL CAMERA (ton téléphone)
URL = "http://10.50.144.69:8080/video"

# Charger modèle YOLO
model = YOLO("yolov8n.pt")

# Session state
if "count" not in st.session_state:
    st.session_state.count = 0

if "tracked_ids" not in st.session_state:
    st.session_state.tracked_ids = set()

# ---------------------------
# FONCTION DE TRAITEMENT
# ---------------------------
def process_frame(frame):
    results = model.track(frame, persist=True, verbose=False)

    if results[0].boxes.id is not None:
        boxes = results[0].boxes

        for box in boxes:
            cls = int(box.cls[0])

            # 0 = person
            if cls == 0:
                obj_id = int(box.id[0])

                if obj_id not in st.session_state.tracked_ids:
                    st.session_state.tracked_ids.add(obj_id)
                    st.session_state.count += 1

    return frame

# ---------------------------
# STREAMLIT UI
# ---------------------------
start = st.button("🎥 Start Camera")

frame_window = st.image([])
counter = st.metric("👥 Visitors", 0)

# ---------------------------
# CAMERA LOOP
# ---------------------------
if start:
    cap = cv2.VideoCapture(URL)

    while True:
        ret, frame = cap.read()

        if not ret:
            st.error("Camera not working")
            break

        frame = process_frame(frame)

        # Affichage
        frame_window.image(frame, channels="BGR")
        counter.metric("👥 Visitors", st.session_state.count)
