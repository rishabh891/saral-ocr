from datetime import date, datetime
import re

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
