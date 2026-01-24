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
from datetime import date, datetime

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

def validator(data_dict):
    validator_json = {}

    # Invoice number validation
    if not data_dict.get("invoice_number"):
        validator_json["invoice_number"] = {
            "message": "INVOICE NUMBER is missing",
            "status": "error"
        }
    else:
        validator_json["invoice_number"] = {
            "message": "INVOICE NUMBER is present",
            "status": "warning"
        }
    
    # Invoice date validation
 

    invoice_date = data_dict.get("invoice_date")

    if not invoice_date:
        validator_json["invoice_date"] = {
            "message": "INVOICE DATE is missing",
            "status": "error"
        }
    else:
        try:
            # Adjust format if your input is different (YYYY-MM-DD assumed)
            invoice_date_obj = datetime.strptime(invoice_date, "%Y-%m-%d").date()

            if invoice_date_obj > date.today():
                validator_json["invoice_date"] = {
                    "message": "INVOICE DATE is in the future",
                    "status": "error"
                }
            else:
                validator_json["invoice_date"] = {
                    "message": "INVOICE DATE is valid",
                    "status": "ok"
                }

        except ValueError:
            validator_json["invoice_date"] = {
                "message": "INVOICE DATE format is invalid (expected YYYY-MM-DD)",
                "status": "error"
            }


    # Invoice type validation
    invoice_type = data_dict.get("invoice_type")
    if not invoice_type:
        validator_json["invoice_type"] = {
            "message": "INVOICE TYPE is missing",
            "status": "error"
        }
    else:
        validator_json["invoice_type"] = {
            "message": "INVOICE TYPE is present",
            "status": "ok"
        }
    
    # Grand total validation
    grand_total = data_dict.get("grand_total")
    if not grand_total:
        validator_json["grand_total"] = {
            "message": "GRAND TOTAL is missing",
            "status": "error"
        }
    else:
        if grand_total != data_dict.get("financial_totals", {}).get("grand_total"):
            validator_json["grand_total"] = {
                "message": "GRAND TOTAL does not match with financial totals",
                "status": "warning"
            }
        else:
            validator_json["grand_total"] = {
                "message": "GRAND TOTAL is valid",
                "status": "ok"
            }

    # Financials
    financial_totals = data_dict.get("financial_totals")
    total_igst = financial_totals.get("tax_breakup").get("total_igst")
    total_cgst = financial_totals.get("tax_breakup").get("total_cgst")
    total_sgst = financial_totals.get("tax_breakup").get("total_sgst")
    total_cess = financial_totals.get("tax_breakup").get("total_cess")
    message = []
    status = 'ok'

    if abs(financial_totals.get("total_tax_amount") - data_dict.get("total_tax_amount")) > 1:
        message.append("TOTAL TAX AMOUNT does not match with financial totals")
        status = 'warning'
    
    if abs(financial_totals.get("total_taxable_value") - data_dict.get("total_taxable_value")) > 1:
        message.append("TOTAL TAXABLE VALUE does not match with financial totals")
        status = 'warning'

    if abs(total_igst + total_cgst + total_sgst + total_cess - financial_totals.get("total_tax_amount")) > 1:
        message.append("Total tax amount is not matching with the sum of individual taxes")
        status = 'warning'

    if abs(financial_totals['grand_total'] - (financial_totals['total_taxable_value'] + financial_totals['total_tax_amount'] - financial_totals['header_discount_amount'] + financial_totals['rounding_adjustment'])) > 2:
        message.append("GRAND TOTAL does not match with financial totals")
        status = 'warning'
    
    validator_json['financial_totals']={
        "message": 'Financial totals is valid' if not message else message,
        "status": status
    }   

    
    # Line items
    line_items = data_dict.get("line_items")
    hsn_sac_regex = re.compile(r'^[0-9]{4,8}$')
    message = []
    status = 'ok'
    if not line_items or len(line_items) == 0:
       message.append("LINE ITEMS are missing")
       status = 'error'
  
    for item in line_items:
        if not hsn_sac_regex.fullmatch(str(item.get("classification").get("hsn_sac_code"))):
            message.append(f"HSN/SAC code is invalid for {item.get('description')}")
            status = 'warning'
        
        if item.get("quantities").get("billed_quantity")*item.get("financials").get("unit_price") != item.get("financials").get("gross_amount"):
            message.append(f"Gross amount is not matching for {item.get('description')}")
            status = 'warning'
        

        if abs(item['financials']['gross_amount'] -(item['financials']['taxable_value'] + item['financials']['discount_amount'])) > 1:
            message.append(f"Gross amount is not matching for {item.get('description')}")
            status = 'warning'

    validator_json["line_items"] = {
        "message": 'Line item is valid' if not message else message,
        "status": status
    }

    
    gstin_regex = re.compile(
        r'^(0[1-9]|[1-2][0-9]|3[0-8])[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'
    )
    pan_regex = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')
    ifsc_regex = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')

    # Seller details

    seller_details = data_dict.get("seller_details")
    message =[]
    status = 'ok'
    if not seller_details.get('gstin'):
        message.append("SELLER GSTIN is missing")
        status = 'error'
    else:
        if not gstin_regex.fullmatch(str(seller_details.get('gstin'))):
            message.append("SELLER GSTIN is invalid")
            status= 'warning'
        else:
            if str(seller_details.get('gstin'))[0:2] != str(seller_details.get("state_code", "")):
                message.append("SELLER GSTIN did not match with seller state code")
                status= 'warning'
            if str(seller_details.get('gstin'))[2:12] != str(seller_details.get("pan", "")):
                message.append("SELLER GSTIN did not match with seller pan")
                status= 'warning'

    if not seller_details.get('pan'):
        message.append("SELLER PAN is missing")
        status = 'warning'
    else:
        if not pan_regex.fullmatch(str(seller_details.get('pan'))):
            message.append("SELLER PAN is invalid")
            status= 'warning'

    if seller_details.get("name") != data_dict.get("seller_name"):
        message.append("SELLER NAME did not match with Header seller name")
        status= 'warning'
    
    bank_details = seller_details.get("bank_details")

    if not bank_details.get("ifsc_code"):
        message.append("SELLER BANK IFSC CODE is missing")
        status = 'warning'
    else:
        if not ifsc_regex.fullmatch(str(bank_details.get("ifsc_code"))):
            message.append("SELLER BANK IFSC CODE is invalid")
            status= 'warning'
    
    if not bank_details.get("account_number"):
        message.append("SELLER BANK ACCOUNT NUMBER is missing")
        status = 'warning'
    else:
        if not bank_details.get("account_number").isdigit():
            message.append("SELLER BANK ACCOUNT NUMBER is invalid")
            status= 'warning'
    
    validator_json["seller_details"] = {
        "message": "SELLER DETAILS are valid" if not message else message,
        "status": status
    }

    # Buyer details
    buyer_details = data_dict.get("buyer_details")
    message =[]
    status = 'ok'
    if not buyer_details.get('gstin'):
        message.append("BUYER GSTIN is missing")
        status = 'error'
    else:
        if not gstin_regex.fullmatch(str(buyer_details.get('gstin'))):
            message.append("BUYER GSTIN is invalid")
            status= 'warning'
        else:
            if str(buyer_details.get('gstin'))[0:2] != str(buyer_details.get("state_code", "")):
                message.append("BUYER GSTIN did not match with buyer state code")
                status= 'warning'
            if str(buyer_details.get('gstin'))[2:12] != str(buyer_details.get("pan", "")):
                message.append("BUYER GSTIN did not match with buyer pan")
                status= 'warning'
    
    if not buyer_details.get('pan'):
        message.append("BUYER PAN is missing")
        status = 'warning'
    else:
        if not pan_regex.fullmatch(str(buyer_details.get('pan'))):
            message.append("BUYER PAN is invalid")
            status= 'warning'
    
    if buyer_details.get("name") != data_dict.get("buyer_name"):
        message.append("BUYER NAME did not match with Header buyer name")
        status= 'warning'
    
    validator_json["buyer_details"] = {
        "message": "BUYER DETAILS are valid" if not message else message,
        "status": status
    }



    # compliance markers
    eway_bill_regex = re.compile(r'^[0-9]{12}$')
    hsn_regex = re.compile(r'^[0-9]{6,8}$')
    compliance_markers = data_dict.get("compliance_markers")

    if compliance_markers.get("e_way_bill_number"):
        if not eway_bill_regex.fullmatch(str(compliance_markers.get("e_way_bill_number"))):
           validator_json['compliance_markers']['e_way_bill_number'] = {
               "message": "E-WAY BILL NUMBER is invalid",
               "status": "warning"
           }
    # Purchase order number

    if not data_dict.get("purchase_order_numbers") or len(data_dict.get("purchase_order_numbers")) == 0:
        validator_json['purchase_order_numbers'] = {
            "message": "PURCHASE ORDER NUMBER is missing",
            "status": "error"
        }
    else:
        validator_json['purchase_order_numbers'] = {
            "message": "PURCHASE ORDER NUMBER is present",
            "status": "ok"
        }
    return validator_json







    
        
    