import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import tempfile
import os
import io

st.set_page_config(page_title="CVT Doctor", layout="centered")
st.title("CVT Doctor - Automated Subaru CVT Diagnostics")

uploaded_file = st.file_uploader("Upload your SSM4/BtSsm CSV file", type="csv")

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode('ISO-8859-1')
        lines = content.splitlines()

        # Detect header row
        header_idx = None
        for i, line in enumerate(lines[:100]):
            if "Primary" in line and "Engine Speed" in line:
                header_idx = i
                break

        if header_idx is None:
            st.error("Header row not found. Please ensure the file is a valid SSM4/BtSsm CSV.")
            st.stop()

        # Parse the CSV using StringIO
        csv_data = "\n".join(lines[header_idx:])
        df = pd.read_csv(io.StringIO(csv_data))
        st.success("File loaded successfully.")
        st.dataframe(df.head())

        # Normalize data types
        numeric_columns = ['Engine Speed', 'Primary Rev Speed', 'Actual Gear Ratio', 'Line Pressure', 'Throttle Opening Angle', 'Secondary Rev Speed']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=numeric_columns, inplace=True)

        # Diagnostic logic
        findings = []
        if 'Actual Gear Ratio' in df.columns:
            if (df['Actual Gear Ratio'] < 0.5).any():
                findings.append("⚠️ Gear ratio dropped below 0.5 — Possible belt slippage or low line pressure.")
        
        if 'Line Pressure' in df.columns:
            if df['Line Pressure'].max() < 500:
                findings.append("⚠️ Line Pressure never exceeded 500 kPa — Possible weak pressure control or failing pump.")
        
        if 'Throttle Opening Angle' in df.columns and 'Primary Rev Speed' in df.columns:
            lag = df[df['Throttle Opening Angle'] > 30].copy()
            if (lag['Primary Rev Speed'].diff() > 1000).any():
                findings.append("⚠️ Primary speed delay with high throttle — Possible valve body delay.")
        
        if 'Secondary Rev Speed' in df.columns and 'Engine Speed' in df.columns:
            slip = abs(df['Engine Speed'] - df['Secondary Rev Speed'])
            if (slip > 500).sum() > 10:
                findings.append("⚠️ High slip between engine and secondary speed — Possible torque converter judder.")

        if not findings:
            findings.append("✅ No major anomalies detected based on current diagnostics rules.")

        # Show chart
        st.subheader("CVT Performance Graph")
        fig, ax = plt.subplots()
        for col in ['Engine Speed', 'Primary Rev Speed', 'Actual Gear Ratio']:
            if col in df.columns:
                ax.plot(df.index, df[col], label=col)
        ax.legend()
        st.pyplot(fig)

        # Save to PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf_path = tmp.name
            c = canvas.Canvas(pdf_path, pagesize=letter)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, 750, "CVT Diagnostic Report")
            c.setFont("Helvetica", 10)
            c.drawString(50, 735, "This report was generated automatically based on uploaded SSM4/BtSsm data.")

            y = 710
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Diagnostic Findings:")
            y -= 15
            c.setFont("Helvetica", 10)
            for finding in findings:
                c.drawString(60, y, f"- {finding}")
                y -= 15

            # Save plot
            plot_path = tmp.name.replace(".pdf", ".png")
            fig.savefig(plot_path)
            c.drawImage(plot_path, 50, y - 300, width=500, height=300)
            c.save()

        with open(pdf_path, "rb") as f:
            st.download_button("📄 Download Full Diagnostic PDF", f, file_name="CVT_Report.pdf")

    except Exception as e:
        st.error(f"File parsing error: {e}")
else:
    st.warning("Please upload a CSV file to begin analysis.")