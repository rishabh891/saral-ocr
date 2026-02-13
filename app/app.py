import streamlit as st
from helper import encode_image, extract_with_openai, update_gsheet,get_gsheet_data, extract_prompt_from_file, extract_with_gemini, extract_validator
from PIL import Image
import pandas as pd
import json
import os
from datetime import datetime
from invoice import invoice_page
from po import po_page
from two_way_matching import two_way_matching
import concurrent.futures

st.set_page_config(page_title="SARAL OCR", layout="wide", initial_sidebar_state="expanded")

# Initialize state
if "invoice_data" not in st.session_state:
    st.session_state.invoice_data = None
    st.session_state.model_name = None
    st.session_state.token_split_invoice = None
if "po_data" not in st.session_state:
    st.session_state.po_data = None
    st.session_state.token_split_po = None

if "refresh_gsheet" not in st.session_state:
    st.session_state.refresh_gsheet = False

with st.sidebar:
    st.title("SARAL OCR")

    st.session_state.model_name = st.selectbox(
        "Select Model",
        ["gpt-4.1", "gpt-5-mini","gpt-5-nano",  "gpt-5.2", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3-flash-preview"],
        index=6,
    )


    st.subheader("2 way matching")

    uploaded_invoice = st.file_uploader(
        "Choose an invoice image",
        type=["png", "jpg", "jpeg"],  # removed pdf (important)
        help="Upload a clear image of your invoice",
    )
    # uploaded_po = st.file_uploader(
    #     "Choose PO image",
    #     type=["png", "jpg", "jpeg"],  # removed pdf (important)
    #     help="Upload a clear image of your PO",
    # )

    if uploaded_invoice:
        invoice = Image.open(uploaded_invoice)
        invoice = invoice.rotate(-90)
        original_filename_invoice = uploaded_invoice.name
        image_name_invoice = os.path.splitext(original_filename_invoice)[0]
        st.image(invoice, caption="Uploaded Invoice")

        if st.button("Extract", use_container_width=True):
            with st.spinner("Extracting Invoice..."):
                try:
                    st.session_state.invoice_data, st.session_state.token_split_invoice = extract_validator(uploaded_invoice, st.session_state.model_name, "invoice")
                except Exception as e:
                    st.error(f"Extraction failed: {e}")

if st.session_state.invoice_data:
    raw = st.session_state.invoice_data
    token_split_invoice = st.session_state.token_split_invoice
    invoice_page(raw, image_name_invoice, token_split_invoice)


#     if uploaded_invoice and uploaded_po:
#         invoice = Image.open(uploaded_invoice)
#         invoice = invoice.rotate(-90)
#         original_filename_invoice = uploaded_invoice.name
#         image_name_invoice = os.path.splitext(original_filename_invoice)[0]
#         po = Image.open(uploaded_po)
#         po = po.rotate(-90)
#         original_filename_po = uploaded_po.name
#         image_name_po = os.path.splitext(original_filename_po)[0]
#         col1, col2 = st.columns(2)
#         with col1:
#             st.image(invoice, caption="Uploaded Invoice")
#         with col2:
#             st.image(po, caption="Uploaded PO")

#         if st.button("Extract and validate", use_container_width=True):
#             with st.spinner("Extracting Invoice & PO simultaneously..."):
#                 try:
#                     with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
#                         future_invoice = executor.submit(
#                             extract_validator,
#                             uploaded_invoice,
#                             st.session_state.model_name,
#                             "invoice"
#                         )

#                         future_po = executor.submit(
#                             extract_validator,
#                             uploaded_po,
#                             st.session_state.model_name,
#                             "po"
#                         )

#                         invoice_result = future_invoice.result()
#                         po_result = future_po.result()

#                     st.session_state.invoice_data, st.session_state.token_split_invoice = invoice_result
#                     st.session_state.po_data, st.session_state.token_split_po = po_result

#                 except Exception as e:
#                     st.error(f"Extraction failed: {e}")
            
        

# # ------------------ RESULT ------------------

# if st.session_state.invoice_data:
#     raw = st.session_state.invoice_data
#     token_split_invoice = st.session_state.token_split_invoice
#     invoice_page(raw, image_name_invoice, token_split_invoice)

# if st.session_state.po_data:
#     raw = st.session_state.po_data
#     token_split_po = st.session_state.token_split_po
#     po_page(raw, image_name_po, token_split_po)

# if st.session_state.invoice_data and st.session_state.po_data:
#     two_way_matching(st.session_state.invoice_data, st.session_state.po_data)

   
   
