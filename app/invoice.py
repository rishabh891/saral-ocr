import streamlit as st
import pandas as pd
from datetime import datetime
from validator import validator
import json

def invoice_page(raw, image_name, token_split):
    try:
     
        parsed = json.loads(raw)
        data_dict = {
            "id": image_name,
            **parsed,
            "model_name": st.session_state.model_name,
            "scan_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        st.subheader("Invoice Data")
        # col1, col2 = st.columns(2, width='stretch')
        # with col1:
        #     st.subheader("Invoice Data")
        # with col2:
        #     if st.button("Save to Google Sheets"):
        #         with st.spinner("Saving to Google Sheets..."):
        #             try:
        #                 update_gsheet(data_dict)
        #                 st.session_state.refresh_gsheet = True
        #                 st.rerun()
        #                 st.success("✅ Data successfully saved to Google Sheets!")
        #             except Exception as e:
        #                 st.error(f"Error saving to Google Sheets: {e}")
        validator_json = validator(data_dict)
        rows = []

        for key, value in data_dict.items():
            validation = validator_json.get(key, {})
            
            # Format value for display to avoid PyArrow type errors
            display_value = value
            if isinstance(value, (dict, list)):
                display_value = json.dumps(value, indent=2)
            else:
                display_value = str(value)

            rows.append({
                "Key": key,
                "Value": display_value,
                "Status": validation.get("status", "not_validated"),
                "Message": validation.get("message", "")
            })
        df = pd.DataFrame(rows)

        st.dataframe(df, height=500)
        if st.session_state.model_name.startswith('gemini'):
            st.divider()
            col1, col2 , col3, col4= st.columns(4, border=True)
            with col1:
                st.markdown("##### Input Tokens")
                st.write(token_split.get("prompt"))
            with col2:
                st.markdown("##### Reasoning")
                st.write(token_split.get("thoughts"))
            with col3:
                st.markdown("##### Output Tokens")
                st.write(token_split.get("candidates"))
            with col4:
                st.markdown("##### Total Tokens")
                st.write(token_split.get("total"))
    except json.JSONDecodeError:
        st.error("Failed to parse JSON")
        st.code(raw)
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.code(raw)
            
       