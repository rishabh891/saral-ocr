import streamlit as st
import json
from difflib import SequenceMatcher
import pandas as pd


def similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_value(val):
    """Ensure Arrow-safe values"""
    if isinstance(val, list):
        return ", ".join(map(str, val))
    if isinstance(val, dict):
        return json.dumps(val)
    return val


def two_way_matching(invoice_data, po_data):

    invoice_json = json.loads(invoice_data)
    po_json = json.loads(po_data)

    results = []

    # -----------------------
    # Header-level checks
    # -----------------------
    po_numbers = invoice_json.get("purchase_order_numbers", [])
    po_number_match = po_json["purchase_order_number"] in po_numbers

    seller_similarity = similarity(
        po_json.get("seller_name", ""),
        invoice_json.get("seller_name", "")
    )

    buyer_similarity = similarity(
        invoice_json.get("buyer_name", ""),
        po_json.get("buyer_name", "")
    )

    invoice_total = invoice_json.get("grand_total", 0.0)
    po_total = po_json["financial_totals"].get("grand_total", 0.0)

    total_diff_pct = (
        abs(invoice_total - po_total) / po_total * 100
        if po_total else 0
    )

    results.extend([
        {
            "level": "HEADER",
            "field": "PO Number",
            "invoice_value": normalize_value(po_numbers),
            "po_value": po_json["purchase_order_number"],
            "match": po_number_match,
            "score": 1.0 if po_number_match else 0.0
        },
        {
            "level": "HEADER",
            "field": "Seller Name",
            "invoice_value": invoice_json.get("seller_name"),
            "po_value": po_json.get("seller_name"),
            "match": seller_similarity > 0.9,
            "score": round(seller_similarity, 2)
        },
        {
            "level": "HEADER",
            "field": "Buyer Name",
            "invoice_value": invoice_json.get("buyer_name"),
            "po_value": po_json.get("buyer_name"),
            "match": buyer_similarity > 0.9,
            "score": round(buyer_similarity, 2)
        },
        {
            "level": "HEADER",
            "field": "Grand Total",
            "invoice_value": invoice_total,
            "po_value": po_total,
            "match": total_diff_pct <= 5,
            "score": round(max(0, 1 - total_diff_pct / 100), 2)
        }
    ])

    # -----------------------
    # Line-level checks
    # -----------------------
    for inv_line in invoice_json.get("line_items", []):
        best_match = None
        best_score = 0

        for po_line in po_json.get("line_items", []):
            desc_score = similarity(
                inv_line.get("description", ""),
                po_line.get("description", "")
            )
            if desc_score > best_score:
                best_score = desc_score
                best_match = po_line

        if not best_match:
            continue

        inv_qty = inv_line.get("quantities", {}).get("billed_quantity", 0)
        po_qty = best_match.get("quantities", {}).get("ordered_quantity", 0)

        qty_score = 1 - min(abs(inv_qty - po_qty) / po_qty, 1) if po_qty else 0

        inv_price = inv_line.get("financials", {}).get("unit_price", 0)
        po_price = best_match.get("financials", {}).get("unit_price", 0)

        price_score = 1 - min(abs(inv_price - po_price) / po_price, 1) if po_price else 0

        line_score = (
            best_score * 0.4 +
            qty_score * 0.3 +
            price_score * 0.3
        )

        results.append({
            "level": "LINE",
            "field": f"Line {inv_line.get('line_number')}",
            "invoice_value": inv_line.get("description"),
            "po_value": best_match.get("description"),
            "match": line_score >= 0.8,
            "score": round(line_score, 2)
        })

    # -----------------------
    # DataFrame + UI
    # -----------------------
    df = pd.DataFrame(results)

    overall_score = round(df["score"].mean(), 2)
    status = (
        "MATCH" if overall_score >= 0.9
        else "PARTIAL MATCH" if overall_score >= 0.7
        else "MISMATCH"
    )

    st.title("Invoice ↔ Purchase Order Matching")
    st.metric("Overall Match Score", overall_score)

    if status == "MATCH":
        st.success(f"Match Status: {status}")
    elif status == "PARTIAL MATCH":
        st.warning(f"Match Status: {status}")
    else:
        st.error(f"Match Status: {status}")

    st.subheader("Detailed Match Report")

    st.dataframe(
        df.style.applymap(
            lambda x: "background-color: #c8e6c9" if x is True else
                      "background-color: #ffcdd2" if x is False else "",
            subset=["match"]
        ),
        use_container_width=True
    )
