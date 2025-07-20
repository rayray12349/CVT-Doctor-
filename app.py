import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import tempfile
import os
from io import BytesIO

st.title("CVT Doctor - Automated Subaru CVT Diagnostics")

uploaded_file = st.file_uploader("Upload your SSM4/BtSsm CSV file", type="csv")

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode('ISO-8859-1')
        lines = content.splitlines()

        header_idx = None
        for i, line in enumerate(lines[:100]):
            if "Primary" in line or "Secondary" in line or "Gear Ratio" in line:
                header_idx = i
                break

        if header_idx is None:
            st.error("Could not detect header row.")
            st.stop()

        df = pd.read_csv(BytesIO(content.encode('ISO-8859-1')), skiprows=header_idx)
        st.success("File loaded successfully.")
        st.dataframe(df.head())

        findings = []
        plots = []

        # Gear Ratio Analysis
        if 'Actual Gear Ratio' in df.columns:
            df['Actual Gear Ratio'] = pd.to_numeric(df['Actual Gear Ratio'], errors='coerce')
            if (df['Actual Gear Ratio'] < 0.5).any():
                findings.append("- ⚠️ Gear ratio dropped below 0.5 — Possible belt slippage or low line pressure.")

            fig, ax = plt.subplots()
            df['Actual Gear Ratio'].plot(ax=ax, title='Actual Gear Ratio')
            ax.set_ylabel('Ratio')
            plots.append(fig)

        # Line Pressure Analysis
        if 'Line Pressure' in df.columns:
            df['Line Pressure'] = pd.to_numeric(df['Line Pressure'], errors='coerce')
            if (df['Line Pressure'] < 400).any():
                findings.append("- ⚠️ Line pressure dropped below 400 — Possible leaking valve body or weak pressure control solenoid.")

            fig, ax = plt.subplots()
            df['Line Pressure'].plot(ax=ax, title='Line Pressure (psi)')
            ax.set_ylabel('Pressure')
            plots.append(fig)

        # Torque Converter Judder
        if 'Engine Speed' in df.columns and 'Turbine Revolution' in df.columns:
            df['Engine Speed'] = pd.to_numeric(df['Engine Speed'], errors='coerce')
            df['Turbine Revolution'] = pd.to_numeric(df['Turbine Revolution'], errors='coerce')
            rpm_diff = abs(df['Engine Speed'] - df['Turbine Revolution'])
            if (rpm_diff > 300).sum() > 50:
                findings.append("- ⚠️ High Engine vs. Turbine RPM difference — Possible torque converter judder.")

            fig, ax = plt.subplots()
            df['Engine Speed'].plot(ax=ax, label='Engine RPM')
            df['Turbine Revolution'].plot(ax=ax, label='Turbine RPM')
            ax.set_title('RPM Comparison')
            ax.legend()
            ax.set_ylabel('RPM')
            plots.append(fig)

        # Throttle vs RPM
        if 'Throttle Opening Angle' in df.columns and 'Engine Speed' in df.columns:
            df['Throttle Opening Angle'] = pd.to_numeric(df['Throttle Opening Angle'], errors='coerce')
            correlation = df['Throttle Opening Angle'].corr(df['Engine Speed'])
            if correlation < 0.3:
                findings.append("- ⚠️ Weak throttle vs. RPM correlation — Possible throttle delay or intake issue.")

            fig, ax = plt.subplots()
            df['Throttle Opening Angle'].plot(ax=ax, title='Throttle Opening Angle')
            ax.set_ylabel('Degrees')
            plots.append(fig)

        # Display Results
        if findings:
            st.subheader("Diagnostic Findings:")
            for item in findings:
                st.markdown(item)
        else:
            st.success("No major issues detected.")

        st.subheader("Performance Graphs:")
        for fig in plots:
            st.pyplot(fig)

        # PDF Export
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf_path = tmp.name
            c = canvas.Canvas(pdf_path, pagesize=letter)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, 750, "CVT Diagnostic Report")
            c.setFont("Helvetica", 10)
            c.drawString(50, 735, "This report was generated automatically based on uploaded SSM4/BtSsm data.")
            y = 715
            if findings:
                c.drawString(50, y, "Diagnostic Findings:")
                y -= 15
                for item in findings:
                    c.drawString(60, y, item)
                    y -= 15
            else:
                c.drawString(50, y, "No major issues detected.")
            c.save()

        with open(pdf_path, "rb") as f:
            st.download_button("Download Diagnostic PDF", f, file_name="CVT_Report.pdf")

    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.warning("Please upload a file to begin.")