import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import tempfile
import os

st.title("CVT Doctor - Automated Subaru CVT Diagnostics")

uploaded_file = st.file_uploader("Upload your SSM4/BtSsm CSV file", type="csv")

if uploaded_file is not None:
    # Read uploaded CSV
    content = uploaded_file.read().decode('ISO-8859-1')
    lines = content.splitlines()

    # Detect header row
    header_idx = None
    for i, line in enumerate(lines[:100]):
        if "Primary" in line or "Secondary" in line or "Gear Ratio" in line:
            header_idx = i
            
            if header_idx is not None:
    try:
        uploaded_file.seek(0)  # Reset file pointer after .read()
        df = pd.read_csv(uploaded_file, skiprows=header_idx)
            st.success("File loaded and parsed successfully!")
            st.dataframe(df.head())

            # Plot sample graph
            numeric_columns = ['Engine Speed', 'Primary Rev Speed', 'Actual Gear Ratio']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df.dropna(subset=numeric_columns, inplace=True)
            st.line_chart(df[numeric_columns])

            # Save PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                pdf_path = tmp.name
                c = canvas.Canvas(pdf_path, pagesize=letter)
                c.setFont("Helvetica-Bold", 14)
                c.drawString(100, 750, "CVT Diagnostic Report")
                c.setFont("Helvetica", 10)
                c.drawString(100, 730, "This report was generated automatically based on uploaded SSM4 data.")
                c.save()

            with open(pdf_path, "rb") as f:
                st.download_button("Download Diagnostic PDF", f, file_name="CVT_Report.pdf")

        except Exception as e:
            st.error(f"Error reading CSV: {e}")
            st.stop()
    else:
        st.error("Could not detect header row. Please check the file format.")
        st.stop()
else:
    st.warning("Please upload a file to begin.")
    st.stop()