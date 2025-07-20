import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import tempfile
import os
import io

st.set_page_config(page_title="CVT Doctor", layout="wide")
st.title("CVT Doctor - Automated Subaru CVT Diagnostics")

uploaded_file = st.file_uploader("Upload your SSM4/BtSsm CSV file", type="csv")

if uploaded_file is not None:
    try:
        # Try to read the file with common encodings
        content = uploaded_file.read()
        for encoding in ['utf-8', 'ISO-8859-1', 'utf-16']:
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise UnicodeDecodeError("Unable to decode the file.")

        lines = text.splitlines()
        header_idx = None
        for i, line in enumerate(lines[:100]):
            if "Primary" in line and "Secondary" in line:
                header_idx = i
                break

        if header_idx is None:
            st.error("Could not detect a valid data header in the file.")
            st.stop()

        df = pd.read_csv(io.StringIO(text), skiprows=header_idx)
        st.success("File loaded and parsed successfully!")
        st.dataframe(df.head())

        # Convert to numeric
        numeric_columns = ['Engine Speed', 'Primary Rev Speed', 'Actual Gear Ratio']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df.dropna(subset=numeric_columns, inplace=True)

        # Diagnostic check
        issues = []
        if (df['Actual Gear Ratio'] < 0.5).any():
            issues.append("⚠️ Gear ratio dropped below 0.5 — Possible belt slippage or low line pressure.")
        if (df['Primary Rev Speed'] > 6000).any():
            issues.append("⚠️ Primary pulley speed exceeded 6000 RPM — Possible pulley wear.")
        if (df['Engine Speed'].max() < 1500):
            issues.append("⚠️ Engine speed too low throughout recording — Possible idle-only log.")

        if not issues:
            issues.append("✅ No major issues detected. CVT appears to operate within normal parameters.")

        # Display issues
        for issue in issues:
            st.info(issue)

        # Plot
        st.subheader("Graph - CVT Performance")
        st.line_chart(df[numeric_columns])

        # Generate PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf_path = tmp.name
            c = canvas.Canvas(pdf_path, pagesize=letter)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, 750, "CVT Diagnostic Report")
            c.setFont("Helvetica", 10)
            c.drawString(50, 735, "This report was generated automatically based on uploaded SSM4/BtSsm data.")
            c.drawString(50, 715, "Diagnostic Findings:")

            y = 700
            for issue in issues:
                c.drawString(60, y, f"- {issue}")
                y -= 15

            # Save a plot to image buffer
            fig, ax = plt.subplots()
            df[numeric_columns].plot(ax=ax)
            ax.set_title("CVT Performance Graph")
            img_buf = io.BytesIO()
            fig.savefig(img_buf, format='PNG')
            img_buf.seek(0)

            # Embed image into PDF
            c.drawImage(ImageReader(img_buf), 50, y - 220, width=500, height=200)
            c.save()

        with open(pdf_path, "rb") as f:
            st.download_button("Download PDF Report", f, file_name="CVT_Report.pdf")

    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        st.stop()
else:
    st.warning("Please upload a file to begin.")