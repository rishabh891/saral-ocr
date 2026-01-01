import streamlit as st
from helper import get_api_keys, encode_image, extract_with_openai, update_gsheet,get_gsheet_data
from PIL import Image
import pandas as pd
import json
import os
from datetime import datetime



st.set_page_config(page_title="SARAL OCR", layout="wide")


openai_api = get_api_keys()

# Initialize state
if "invoice_data" not in st.session_state:
    st.session_state.invoice_data = None
    st.session_state.model = None
if "refresh_gsheet" not in st.session_state:
    st.session_state.refresh_gsheet = False

with st.sidebar:
    st.title("SARAL OCR")

    model_name = st.selectbox(
        "Select Model",
        ["gpt-3.5-turbo", "gpt-4", "gpt-4o", "gpt-4o-mini", "gpt-4.1","gpt-4.1-mini"],
        index=0,
    )

    st.subheader("📤 Upload Invoice")

    uploaded_file = st.file_uploader(
        "Choose an invoice image",
        type=["png", "jpg", "jpeg"],  # removed pdf (important)
        help="Upload a clear image of your invoice",
    )

    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Invoice",width='stretch')
        original_filename = uploaded_file.name
        image_name = os.path.splitext(original_filename)[0]

        if st.button("Extract Invoice",width='stretch'):
            with st.spinner("Extracting Invoice..."):
                try:
                    uploaded_file.seek(0)
                    image_base64 = encode_image(uploaded_file)

                    st.session_state.invoice_data, st.session_state.model = extract_with_openai(
                        image_base64, model_name, openai_api
                    )

                except Exception as e:
                    st.error(f"Error extracting invoice: {str(e)}")

# ------------------ RESULT ------------------

if st.session_state.invoice_data and st.session_state.model:
  

    raw = st.session_state.invoice_data

    # Safe JSON extraction
    try:
        # First try to load it directly
        json_data = raw
        # If it contains markdown code blocks, strip them
        if "```json" in raw:
            json_data = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            json_data = raw.split("```")[1].split("```")[0]
            
        # Parse JSON

        parsed = json.loads(json_data)

        data_dict = {
            "id": image_name,
            **parsed,
            "model_name": st.session_state.model,
            "scan_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Invoice Data")
        with col2:
            if st.button("Save to Google Sheets"):
                with st.spinner("Saving to Google Sheets..."):
                    try:
                        update_gsheet(data_dict)
                        st.session_state.refresh_gsheet = True
                        st.rerun()
                        st.success("✅ Data successfully saved to Google Sheets!")
                    except Exception as e:
                        st.error(f"Error saving to Google Sheets: {e}")

        st.json(data_dict)
        if st.session_state.refresh_gsheet:
            sheet_df = get_gsheet_data()
            st.session_state.refresh_gsheet = False
        else:
            sheet_df = get_gsheet_data()

        st.subheader("📊 Google Sheets Data")
        st.dataframe(sheet_df, width='stretch')        
       
    except json.JSONDecodeError:
        st.error("Failed to parse JSON")
        st.code(raw)
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.code(raw)
