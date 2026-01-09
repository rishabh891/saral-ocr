import streamlit as st
from helper import encode_image, extract_with_openai, update_gsheet,get_gsheet_data, extract_prompt_from_file, extract_with_gemini, invoice_validator
from PIL import Image
import pandas as pd
import json
import os
from datetime import datetime



st.set_page_config(page_title="SARAL OCR", layout="wide", initial_sidebar_state="expanded")

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
        ["gpt-4.1", "gpt-5-mini","gpt-5-nano",  "gpt-5.2", "gemini-2.5-flash-lite", "gemini-2.5-flash"],
        index=0,
    )

    prompt_file = st.file_uploader(
    "Upload Prompt File (PDF / DOCX / TXT)",
    type=["pdf", "docx", "txt"]
     )

    st.subheader("📤 Upload Invoice")

    uploaded_file = st.file_uploader(
        "Choose an invoice image",
        type=["png", "jpg", "jpeg"],  # removed pdf (important)
        help="Upload a clear image of your invoice",
    )

    if uploaded_file:
        image = Image.open(uploaded_file)
        image = image.rotate(-90)
        st.image(image, caption="Uploaded Invoice")
        original_filename = uploaded_file.name
        image_name = os.path.splitext(original_filename)[0]

        if st.button("Extract Invoice",width='stretch'):
            with st.spinner("Extracting Invoice..."):
                try:
                    uploaded_file.seek(0)
                    if prompt_file:
                        prompt = extract_prompt_from_file(prompt_file)
                    else:
                        prompt = ""
                    image_base64 = encode_image(uploaded_file)

                    if model_name.startswith('gpt'):
                        st.session_state.invoice_data, st.session_state.model = extract_with_openai(
                        image_base64, model_name, prompt)
                    else:
                        st.session_state.invoice_data, st.session_state.model = extract_with_gemini(
                        image_base64, model_name, prompt)

                except Exception as e:
                    st.error(f"Error extracting invoice: {str(e)}")

# ------------------ RESULT ------------------

if st.session_state.invoice_data and st.session_state.model:
  
    raw = st.session_state.invoice_data
    try:
        json_data = raw
        if "```json" in raw:
            json_data = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            json_data = raw.split("```")[1].split("```")[0]
            
        
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
        st.divider()
        errors = invoice_validator(data_dict=data_dict)
        if len(errors) > 0:
            st.text("Errors after initial extraction")
            image_base64 = encode_image(uploaded_file)
            probable_schema= {
                "buyer_gstin": "This represents the GST number of the buyer in the invoice.",
                "seller_gstin": "This represents the GST number of the seller in the invoice.",
            }
            concat_error=""
            for e in errors:
                concat_error+=e+"\n"
                st.error(e)

            new_prompt = f"""We ran OCR on the invoice to get necessary information. However, we found some errors. Please try to find the information again . The error is {concat_error}. Respond the answer in JSON format using the schema {probable_schema}. Do not include any other text in your response other than the JSON object."""

            new_json_data , model= extract_with_gemini(image_base64, 'gemini-2.5-flash-lite', new_prompt)
            if "```json" in new_json_data:
                new_json_data = new_json_data.split("```json")[1].split("```")[0]
            elif "```" in new_json_data:
                new_json_data = new_json_data.split("```")[1].split("```")[0]
            parsed_new_json= json.loads(new_json_data)
            st.json(parsed_new_json)
            data_dict['buyer_details']['gstin'] = parsed_new_json['buyer_gstin']
            data_dict['seller_details']['gstin'] = parsed_new_json['seller_gstin']
            st.text('Values after 1st retry')
            st.json(parsed_new_json)
            
            st.divider()
           
        else:
            st.success("✅ Data successfully validated!")
        st.text('Final extracted data')
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
