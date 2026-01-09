import streamlit as st
from openai import OpenAI
import base64
import json
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from pypdf import PdfReader
from docx import Document
from google import genai
from google.genai import types
import re

INVOICE_SCHEMA={
    "invoice_number": "",
    "invoice_date": "",
    "invoice_type" : "Tax Invoice | Credit Note | Or anything else",
    "grand_total": 'The final payable amount',
    "seller_name" : "Name of the vendor",
    "buyer_name" : "Name of the buyer",
"total_taxable_value":"Base amount before tax",
"total_tax_amount": "Total GST amount",
"currency_code": "USD, INR, GB  P, JPY, AED etc",
"purchase_order_numbers": "Comma-separated list (e.g., 'PO-01, PO-02').",
"delivery_challan_numbers" : "Comma-separated list of Challans/GRNs.",
"line_items": [
    {
    "line_number": "Sequential ID (1, 2...)",
    "description": "Item description.",
    "classification":{
        "hsn_sac_code": " GST Classification Code (Critical)",
        "is_service": "True for Services, False for Goods"
    },
    "quantity": {
        "billed_quantity":"Quantity invoiced",
        "unit_of_measure": " Standard UOM (NOS, KGS, MTR)"
    },
    'financial':{
"unit_price": "Rate per unit",
"gross_amount": "Qty * Price",
"discount_amount" : "Line level discount",
"taxable_value" : "Base value for tax calculation",
    },
    'taxes':{
        "tax_rate_percentage" : "5, 12, 18, or 28",
        "igst_amount": "Integrated GST",
        "cgst_amount" : "Central GST",
        "sgst_amount" : "State GST"
    },
    "total_line_amount" : "Final line value"
}],
'seller_details': {
    "name" : " Legal Name",
    "gstin" : "15-digit Tax ID (Validated Regex)",
    "pan" : "10-digit PAN",
    "state_code" : "2-digit GST State Code (e.g., '27').",
    "address":{
"street" : "",
"city" : "",
"state" : "",
"pincode" : "",
"country" : "",
    },
    "email": "",
    "phone": "",
    'bank_details' : {
        'account_number': "",
        'ifsc_code': "",
        'bank_name': "",
    }
},
'buyer_details': {
    "name" : " Legal Name",
    "gstin" : "15-digit Tax ID (Validated Regex)",
    "pan" : "10-digit PAN",
    "state_code" : "2-digit GST State Code (e.g., '27').",
    "address":{
"street" : "",
"city" : "",
"state" : "",
"pincode" : "",
"country" : "",
    },
    "email": "",
    "phone": ""
},
'financial_totals':{
'total_taxable_value' : 'Decimal value',
'total_tax_amount' : 'Decimal value',
'tax_breakup' : {
    'total_igst' : 'Decimal value',
    'total_cgst' : 'Decimal value',
    'total_sgst' : 'Decimal value',
    'total_cess' : 'Decimal value',
},
'charges' : {
    'shipping_charges' : 'Decimal value',
    'packaging_charges' : 'Decimal value',
    'insurance_charges' : 'Decimal value',
},
'header_discount_amount' : "Global invoice discount in decimal number",
'tcs_details':{
    'applicable' : "Tax Collected at Source applicability - Boolean",
    'rate_percentage' : "Decimal value",
    'amount' : " TCS Amount",
},
'rounding_adjustment' : "Decimal value",
'grand_total' : 'Decimal value',
'amount_in_words' : "Amount in words",
},
'logistics_details' : {
    'transporter_name': "",
    'vehicle_number': "e.g., KA-01-AB-1234",
    'lr_number' : "Lorry Receipt No",
    'mode_of_transport' : "e.g., Road, Air, Sea"
},
'compliance_markers': {
    'irn_hash' : '64-char E-Invoice Hash (Mandatory for >5 Cr turnover)',
    'e_way_bill_number' : 'Logistics compliance number',
    'delivery_proof_present' : 'True if LR/POD/E-Way Bill is found - Boolean',
    'delivery_proof_type' : "ewaybill, LR ,  POD - ENUM",
    'signature_present' : 'True if signed - Boolean',
    'is_digitally_signed' : " True if DSC is detected - Boolean"
},
'invoice_header_meta' : {
    'supply_type' : "Defines the GST nature of the transaction. Critical for validating tax rates (e.g., SEZ supplies are often zero-rated) - B2B/ B2C/ SEZ/ Deemed Export/ Export - ENUM",
    'place_of_supply' : "The destination state code and name where goods are consumed. Determines IGST vs. CGST/SGST logic. Format: [State Code]-[State Name] (e.g., 27-Maharashtra, 29-Karnataka)",
    'reverse_charge_applicable' : " true if the Buyer is liable to pay the tax directly to the government (common for Goods Transport Agencies or Legal Services).",
    'due_date' : "The specific date by which payment is expected. Format: YYYY-MM-DD (e.g., 2024-01-15)",
    'payment_terms' : 'The textual description of payment conditions. e.g Net 30 Days, Immediate, 50% Advance',
    'payment_instruction' : "Specific text instructions for the bank transfer. Example: Please quote invoice no in transfer remarks",
},
'additional_attributes': {
    'remarks' : 'Any "Notes" or "Remarks" text found on the invoice (e.g., "Handle with care").',
    'sales_person' : 'Name of the Sales Representative or Account Manager mentioned.',
    'delivery_slot' : 'Specific delivery timing or location instructions (e.g., "Morning Slot", "Dock 4")',
    'customer_notes' : ' Specific instructions provided by the buyer printed on the invoice.'
}


}

def get_api_keys():
    try:
        openai_api = st.secrets.get("OPENAI_API_KEY", "")
    except:
        openai_api = ""
    return openai_api

def encode_image(uploaded_image):
    if uploaded_image is not None:
       byte_data = uploaded_image.getvalue()
       return base64.b64encode(byte_data).decode('utf-8')
    return None

def update_gsheet(data_dict):
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(spreadsheet=st.secrets.get("spreadsheet", ""), ttl=5)
    except (pd.errors.EmptyDataError, Exception):
        df = pd.DataFrame()
    new_row_df = pd.DataFrame([data_dict])
    if "invoice_number" in new_row_df.columns:
        new_row_df["invoice_number"] = new_row_df["invoice_number"].astype(str)
    updated_df = pd.concat([df, new_row_df], ignore_index=True)
    conn.update(spreadsheet=st.secrets.get("spreadsheet", ""), data=updated_df)
                        
def get_gsheet_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(spreadsheet=st.secrets.get("spreadsheet", ""), ttl=5)
    except (pd.errors.EmptyDataError, Exception):
        df = pd.DataFrame()
    
    if "invoice_number" in df.columns:
        df["invoice_number"] = df["invoice_number"].astype(str)
    return df


def extract_prompt_from_file(uploaded_file):
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".pdf"):
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()

    elif file_name.endswith(".docx"):
        doc = Document(io.BytesIO(uploaded_file.read()))
        return "\n".join([p.text for p in doc.paragraphs]).strip()

    elif file_name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8").strip()

    else:
        raise ValueError("Unsupported prompt file format")

def get_prompt(prompt = None):
    if prompt and prompt.strip():
        base_prompt = f"""
Extract all information from this invoice image and return it as a JSON object
according to the following instructions:
{prompt}
"""
    else:
        base_prompt = f"""
Extract all information from this invoice image and return it as a JSON object
with the following structure:

{json.dumps(INVOICE_SCHEMA, indent=2)}
"""

    final_prompt = f"""
{base_prompt}

Extract all visible information accurately.
If a field is not present, leave it empty or as 0.

IMPORTANT RULES:
- Output valid JSON only
- Do NOT wrap the output in markdown
"""
    return final_prompt


def extract_with_openai(image_base64, model_name, prompt=None):
    client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))

    final_prompt=get_prompt(prompt)
    if model_name.startswith("gpt-5"):
        reasoning = {"effort": "low"}
        text_cfg = {"verbosity": "low"}
    else:
        # GPT-4o family
        reasoning = None
        text_cfg = None

    # -----------------------------
    # Build request
    # -----------------------------
    request = {
        "model": model_name,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": final_prompt.strip()},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_base64}"
                    }
                ]
            }
        ],
        "max_output_tokens": 4000,
    }

    if reasoning:
        request["reasoning"] = reasoning
    if text_cfg:
        request["text"] = text_cfg

    response = client.responses.create(**request)

    return response.output_text, response.model

def extract_with_gemini(image_base64, model_name, prompt=None):
    client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY", ""))

    final_prompt=get_prompt(prompt)

    image_bytes = base64.b64decode(image_base64)

    response = client.models.generate_content(
        model=model_name,
        config={
            "temperature": 0,
            "top_p": 0.1,
            "max_output_tokens": 6000,
        },
        contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=final_prompt),
                        types.Part.from_bytes(
                            data=image_bytes, 
                            mime_type="image/png"
                        )
                    ]
                )
            ]
    )
    return response.text.strip(), model_name

def invoice_validator(data_dict):
    gstin_regex = re.compile(
        r'^(0[1-9]|[1-2][0-9]|3[0-8])[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'
    )

    errors = []

    seller_gstin = data_dict.get('seller_details', {}).get('gstin')
    buyer_gstin = data_dict.get('buyer_details', {}).get('gstin')

    if not seller_gstin:
        errors.append('SELLER GSTIN IS MISSING')
    else:
        if not gstin_regex.fullmatch(str(seller_gstin)):
            errors.append('INVALID SELLER GSTIN')


    if not buyer_gstin:
        errors.append('BUYER GSTIN IS MISSING')
    else:
        if not gstin_regex.fullmatch(str(buyer_gstin)):
            errors.append('INVALID BUYER GSTIN')

    return errors






    
        
    