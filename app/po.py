import streamlit as st
import json
import pandas as pd
from datetime import datetime

def po_page(raw, image_name_po, token_split_po):
    try:
        parsed = json.loads(raw)

        data_dict = {
            "id": image_name_po,
            **parsed,
            "model_name": st.session_state.model_name,
            "scan_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        st.subheader("PO Data")
        
        rows = []

        for key, value in data_dict.items():
            
            # Format value for display to avoid PyArrow type errors
            display_value = value
            if isinstance(value, (dict, list)):
                display_value = json.dumps(value, indent=2)
            else:
                display_value = str(value)

            rows.append({
                "Key": key,
                "Value": display_value,
            })
        df = pd.DataFrame(rows)

        st.dataframe(df, height=500)
        if st.session_state.model_name.startswith('gemini'):
            st.divider()
            col1, col2 , col3, col4= st.columns(4, border=True)
            with col1:
                st.markdown("##### Input Tokens")
                st.write(token_split_po.get("prompt"))
            with col2:
                st.markdown("##### Reasoning")
                st.write(token_split_po.get("thoughts"))
            with col3:
                st.markdown("##### Output Tokens")
                st.write(token_split_po.get("candidates"))
            with col4:
                st.markdown("##### Total Tokens")
                st.write(token_split_po.get("total"))
    except json.JSONDecodeError:
        st.error("Failed to parse JSON")
        st.code(raw)
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.code(raw)
