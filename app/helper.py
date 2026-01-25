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

    return response.output_text

# 1. Initialize client globally once to save handshake time
client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY", ""))
po_target_schema = {
    "type": "OBJECT",
    "properties": {
        "purchase_order_number": {"type": "STRING"},
        "purchase_order_date": {"type": "STRING", "description": "YYYY-MM-DD"},
        "purchase_order_type": {"type": "STRING", "nullable": True},

        "seller_name": {"type": "STRING"},
        "buyer_name": {"type": "STRING"},

        "currency_code": {"type": "STRING", "nullable": True},
        "model_name": {"type": "STRING"},
        "scan_timestamp": {"type": "STRING", "description": "ISO-8601-with-TZ"},

        "linked_contract_number": {"type": "STRING", "nullable": True},

        "line_items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "line_number": {
                        "type": "NUMBER",
                        "nullable": False,
                        "description": "Set to 0 if not found"
                    },

                    "item_code": {
                        "type": "STRING",
                        "nullable": True,
                        "description": "Material / SKU / Service code"
                    },

                    "description": {"type": "STRING"},

                    "classification": {
                        "type": "OBJECT",
                        "properties": {
                            "hsn_sac_code": {"type": "STRING", "nullable": True},
                            "is_service": {"type": "BOOLEAN", "nullable": True}
                        }
                    },

                    "quantities": {
                        "type": "OBJECT",
                        "properties": {
                            "ordered_quantity": {
                                "type": "NUMBER",
                                "nullable": False,
                                "description": "Set to 0.0 if not found"
                            },
                            "unit_of_measure": {"type": "STRING", "nullable": True}
                        },
                        "required": ["ordered_quantity"]
                    },

                    "financials": {
                        "type": "OBJECT",
                        "properties": {
                            "unit_price": {
                                "type": "NUMBER",
                                "nullable": False,
                                "description": "Authoritative PO price"
                            },
                            "gross_amount": {
                                "type": "NUMBER",
                                "nullable": False,
                                "description": "ordered_quantity * unit_price"
                            },
                            "discount_amount": {
                                "type": "NUMBER",
                                "nullable": False,
                                "description": "Set to 0.0 if not found"
                            },
                            "taxable_value": {
                                "type": "NUMBER",
                                "nullable": False,
                                "description": "Gross - discount"
                            }
                        },
                        "required": [
                            "unit_price",
                            "gross_amount",
                            "discount_amount",
                            "taxable_value"
                        ]
                    },

                    "taxes": {
                        "type": "OBJECT",
                        "properties": {
                            "tax_rate_percentage": {"type": "NUMBER", "nullable": False},
                            "igst_applicable": {"type": "BOOLEAN", "nullable": True},
                            "cgst_applicable": {"type": "BOOLEAN", "nullable": True},
                            "sgst_applicable": {"type": "BOOLEAN", "nullable": True}
                        },
                        "required": ["tax_rate_percentage"]
                    },

                    "total_line_amount": {
                        "type": "NUMBER",
                        "nullable": False,
                        "description": "Taxable + taxes (if included in PO)"
                    }
                },
                "required": ["line_number", "description", "total_line_amount"]
            }
        },

        "seller_details": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "nullable": True},
                "gstin": {"type": "STRING", "nullable": True},
                "pan": {"type": "STRING", "nullable": True},
                "state_code": {"type": "STRING", "nullable": True}
            }
        },

        "buyer_details": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "nullable": True},
                "gstin": {"type": "STRING", "nullable": True},
                "pan": {"type": "STRING", "nullable": True},
                "state_code": {"type": "STRING", "nullable": True}
            }
        },

        "financial_totals": {
            "type": "OBJECT",
            "properties": {
                "total_taxable_value": {
                    "type": "NUMBER",
                    "nullable": False,
                    "description": "Set to 0.0 if not found"
                },
                "total_tax_amount": {
                    "type": "NUMBER",
                    "nullable": False,
                    "description": "Set to 0.0 if not found"
                },
                "grand_total": {
                    "type": "NUMBER",
                    "nullable": False,
                    "description": "Expected invoice cap"
                }
            },
            "required": [
                "total_taxable_value",
                "total_tax_amount",
                "grand_total"
            ]
        },

        "tolerance_rules": {
            "type": "OBJECT",
            "properties": {
                "quantity_tolerance_percentage": {
                    "type": "NUMBER",
                    "nullable": False,
                    "description": "e.g. 5 means ±5%"
                },
                "price_tolerance_percentage": {
                    "type": "NUMBER",
                    "nullable": False
                }
            },
            "required": [
                "quantity_tolerance_percentage",
                "price_tolerance_percentage"
            ]
        },

        "delivery_terms": {
            "type": "OBJECT",
            "properties": {
                "delivery_date": {"type": "STRING", "nullable": True},
                "delivery_location": {"type": "STRING", "nullable": True},
                "incoterms": {"type": "STRING", "nullable": True}
            }
        },

        "approval_metadata": {
            "type": "OBJECT",
            "properties": {
                "approved_by": {"type": "STRING", "nullable": True},
                "approval_date": {"type": "STRING", "nullable": True},
                "approval_status": {"type": "STRING", "nullable": True}
            }
        }
    },

    "required": [
        "purchase_order_number",
        "purchase_order_date",
        "seller_name",
        "buyer_name",
        "model_name",
        "scan_timestamp",
        "financial_totals"
    ]
}

invoice_target_schema = {
    "type": "OBJECT",
    "properties": {
        "invoice_number": {"type": "STRING"},
        "invoice_date": {"type": "STRING", "description": "YYYY-MM-DD"},
        "invoice_type": {"type": "STRING", "nullable": True},
        "grand_total": {"type": "NUMBER", "description": "Final payable amount. Set to 0.0 if not found."},
        "seller_name": {"type": "STRING"},
        "buyer_name": {"type": "STRING"},
        "total_taxable_value": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
        "total_tax_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
        "model_name": {"type": "STRING"},
        "currency_code": {"type": "STRING", "nullable": True},
        "scan_timestamp": {"type": "STRING", "description": "ISO-8601-with-TZ"},
        "purchase_order_numbers": {"type": "ARRAY", "items": {"type": "STRING"}},
        "delivery_challan_numbers": {"type": "ARRAY", "items": {"type": "STRING"}},
        "line_items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "description": "DO NOT add Freight charges/Shipping Charges as a line item.",
                "properties": {
                    "line_number": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                    "description": {"type": "STRING"},
                    "classification": {
                        "type": "OBJECT",
                        "properties": {
                            "hsn_sac_code": {"type": "STRING", "nullable": True},
                            "is_service": {"type": "BOOLEAN", "nullable": True}
                        }
                    },
                    "quantities": {
                        "type": "OBJECT",
                        "properties": {
                            "billed_quantity": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                            "unit_of_measure": {"type": "STRING", "nullable": True}
                        },
                        "required": ["billed_quantity"]
                    },
                    "financials": {
                        "type": "OBJECT",
                        "properties": {
                            "unit_price": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                            "gross_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                            "discount_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                            "taxable_value": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."}
                        },
                        "required": ["unit_price", "gross_amount", "discount_amount", "taxable_value"]
                    },
                    "taxes": {
                        "type": "OBJECT",
                        "properties": {
                            "tax_rate_percentage": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                            "igst_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                            "cgst_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                            "sgst_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                            "cess_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."}
                        },
                        "required": ["tax_rate_percentage", "igst_amount", "cgst_amount", "sgst_amount", "cess_amount"]
                    },
                    "total_line_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."}
                },
                "required": ["line_number", "description", "total_line_amount"]
            }
        },
        "seller_details": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "nullable": True},
                "trade_name": {"type": "STRING", "nullable": True},
                "billing_address": {
                    "type": "OBJECT",
                    "properties": {
                        "raw": {"type": "STRING", "nullable": True},
                        "street": {"type": "STRING", "nullable": True},
                        "city": {"type": "STRING", "nullable": True},
                        "state": {"type": "STRING", "nullable": True},
                        "pincode": {"type": "STRING", "nullable": True},
                        "country": {"type": "STRING", "nullable": True}
                    }
                },
                "gstin": {"type": "STRING", "nullable": True},
                "pan": {"type": "STRING", "nullable": True},
                "state_code": {"type": "STRING", "nullable": True},
                "contact": {
                    "type": "OBJECT",
                    "properties": {
                        "phone": {"type": "STRING", "nullable": True},
                        "email": {"type": "STRING", "nullable": True}
                    }
                },
                "bank_details": {
                    "type": "OBJECT",
                    "properties": {
                        "account_number": {"type": "STRING", "nullable": True},
                        "ifsc_code": {"type": "STRING", "nullable": True},
                        "bank_name": {"type": "STRING", "nullable": True}
                    }
                }
            }
        },
        "buyer_details": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "nullable": True},
                "billing_address": {
                    "type": "OBJECT",
                    "properties": {
                        "raw": {"type": "STRING", "nullable": True},
                        "street": {"type": "STRING", "nullable": True},
                        "city": {"type": "STRING", "nullable": True},
                        "state": {"type": "STRING", "nullable": True},
                        "pincode": {"type": "STRING", "nullable": True},
                        "country": {"type": "STRING", "nullable": True}
                    }
                },
                "shipping_address": {
                    "type": "OBJECT",
                    "properties": {
                        "raw": {"type": "STRING", "nullable": True},
                        "street": {"type": "STRING", "nullable": True},
                        "city": {"type": "STRING", "nullable": True},
                        "state": {"type": "STRING", "nullable": True},
                        "pincode": {"type": "STRING", "nullable": True},
                        "country": {"type": "STRING", "nullable": True}
                    }
                },
                "gstin": {"type": "STRING", "nullable": True},
                "pan": {"type": "STRING", "nullable": True},
                "state_code": {"type": "STRING", "nullable": True}
            }
        },
        "financial_totals": {
            "type": "OBJECT",
            "properties": {
                "total_taxable_value": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                "total_tax_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                "tax_breakup": {
                    "type": "OBJECT",
                    "properties": {
                        "total_igst": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                        "total_cgst": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                        "total_sgst": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                        "total_cess": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."}
                    },
                    "required": ["total_igst", "total_cgst", "total_sgst", "total_cess"]
                },
                "charges": {
            "type": "OBJECT",
            "properties": {
                "shipping_charges": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                "packaging_charges": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                "insurance_charges": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."}
            },
            "required": ["shipping_charges", "packaging_charges", "insurance_charges"]
        },
         "header_discount_amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},

        "tcs_details": {
            "type": "OBJECT",
            "properties": {
                "applicable": {"type": "BOOLEAN", "nullable": True},
                "rate_percentage": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
                "amount": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."}
            },
            "required": ["rate_percentage", "amount"]
        },
         "grand_total": {"type": "NUMBER", "description": "Final payable amount. Set to 0.0 if not found."},
     "rounding_adjustment": {"type": "NUMBER", "nullable": False, "description": "Set to 0.0 if not found."},
        "amount_in_words": {"type": "STRING", "nullable": True},

            },
            "required": ["total_taxable_value", "total_tax_amount", "header_discount_amount", "rounding_adjustment", "grand_total", "amount_in_words"]
        },
        "logistics_details": {
            "type": "OBJECT",
            "properties": {
                "transporter_name": {"type": "STRING", "nullable": True},
                "vehicle_number": {"type": "STRING", "nullable": True},
                "Ir_number": {"type": "STRING", "nullable": True},
                "Ir_date": {"type": "STRING", "nullable": True},
                "mode_of_transport": {"type": "STRING", "nullable": True}
            }
        },
        "compliance_markers": {
            "type": "OBJECT",
            "properties": {
                "irn_hash": {"type": "STRING", "nullable": True},
                "e_way_bill_number": {"type": "STRING", "nullable": True},
                "ack_number": {"type": "STRING", "nullable": True},
                "ack_date": {"type": "STRING", "nullable": True},
                "delivery_proof_present": {"type": "BOOLEAN", "nullable": True},
                "delivery_proof_type": {"type": "STRING", "nullable": True},
                "signature_present": {"type": "BOOLEAN", "nullable": True},
                "is_digitally_signed": {"type": "BOOLEAN", "nullable": True}
            }
        },
        "invoice_header_meta": {
            "type": "OBJECT",
            "properties": {
                "supply_type": {"type": "STRING", "nullable": True},
                "place_of_supply": {"type": "STRING", "nullable": True},
                "reverse_charge_applicable": {"type": "BOOLEAN", "nullable": True},
                "due_date": {"type": "STRING", "nullable": True},
                "payment_terms": {"type": "STRING", "nullable": True},
                "payment_instruction": {"type": "STRING", "nullable": True}
            }
        },
        "additional_attributes": {
            "type": "OBJECT",
            "properties": {
                "remarks": {"type": "STRING", "nullable": True},
                "sales_person": {"type": "STRING", "nullable": True},
                "delivery_slot": {"type": "STRING", "nullable": True},
                "customer_notes": {"type": "STRING", "nullable": True}
            }
        }
    },
    "required": [
        "invoice_number",
        "invoice_date",
        "grand_total",
        "seller_name",
        "buyer_name",
        "model_name",
        "scan_timestamp",
        "total_taxable_value",
        "total_tax_amount",
    ]
}

def extract_with_gemini(image_base64, model_name, doc_type):
   
    image_bytes = base64.b64decode(image_base64)

    if doc_type == "invoice":
        response_schema=invoice_target_schema
    else:
        response_schema=po_target_schema
    
    # 2. Generate content with static instructions separated
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        ],
        config=types.GenerateContentConfig(
           system_instruction="Extract the requested data from the image accurately.",
            temperature=0,
            top_p=0.1,
            max_output_tokens=6000,
            response_mime_type="application/json",
            response_schema=response_schema
        )
    )

    usage = response.usage_metadata
    token_split = {
        "prompt": usage.prompt_token_count,
        "thoughts": getattr(usage, 'thoughts_token_count', 0),
        "candidates": usage.candidates_token_count,
        "total": usage.total_token_count
    }

    return response.text.strip(), token_split

def extract_validator(uploaded_doc, model_name, doc_type):
    uploaded_doc.seek(0)
    image_base64 = encode_image(uploaded_doc)
    
    if model_name.startswith('gpt'):
        data = extract_with_openai(image_base64, model_name, prompt="")
    else:
        data, token_split = extract_with_gemini(image_base64, model_name, doc_type)
    
    return data, token_split
