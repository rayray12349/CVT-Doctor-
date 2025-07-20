import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# App title
st.set_page_config(page_title="CVT Doctor", layout="wide")
st.title("🔧 CVT Doctor – Automated Subaru CVT Diagnostics")

# File upload
uploaded_file = st.file_uploader("Upload your SSM4/BtSsm CSV file", type=["csv"])

if uploaded_file:
    # Try to detect and skip metadata
    lines = uploaded_file.getvalue().decode('ISO-8859-1').splitlines()
    header_row = next((i for i, line in enumerate(lines[:100]) if 'Primary' in line or 'Gear Ratio' in line), 0)
    df = pd.read_csv(uploaded_file, encoding='ISO-8859-1', skiprows=header_row)

    # Clean relevant PIDs
    required_columns = {
        'Engine Speed': 'Engine Speed',
        'Turbine Revolution Speed': 'Turbine RPM',
        'Primary Rev Speed': 'Primary RPM',
        'Accel. Opening Angle': 'Throttle %',
        'Lock Up Duty Ratio': 'TCC Lockup',
        'Actual line press.': 'Line Pressure',
        'Lin. Sol. Set Current': 'Set Current',
        'Lin. Sol. Actual Current': 'Actual Current',
        'ATF Temp.': 'ATF Temp',
        'System Voltage': 'Voltage'
    }

    for col in required_columns:
        if col in df.columns:
            df[required_columns[col]] = pd.to_numeric(df[col], errors='coerce')

    st.success("✅ Data loaded successfully.")
    
    # Plotting
    fig, axs = plt.subplots(3, 1, figsize=(10, 10))
    df_clean = df.dropna(subset=list(required_columns.values()))

    axs[0].plot(df_clean['Engine Speed'], label='Engine RPM')
    axs[0].plot(df_clean['Primary RPM'], label='Primary RPM', linestyle='--')
    axs[0].plot(df_clean['Turbine RPM'], label='Turbine RPM', linestyle=':')
    axs[0].legend()
    axs[0].set_title("Engine vs Turbine vs Primary RPM")

    axs[1].plot(df_clean['Throttle %'], label='Throttle %')
    axs[1].plot(df_clean['TCC Lockup'], label='TCC Lockup Duty', linestyle='--')
    axs[1].legend()
    axs[1].set_title("Throttle vs Torque Converter Lockup")

    axs[2].plot(df_clean['Line Pressure'], label='Actual Line Pressure')
    axs[2].plot(df_clean['Set Current'], label='Set Current', linestyle='--')
    axs[2].plot(df_clean['Actual Current'], label='Actual Current', linestyle=':')
    axs[2].legend()
    axs[2].set_title("Line Pressure vs Solenoid Currents")

    st.pyplot(fig)

    # Diagnostics Summary
    issues = []
    if df_clean['ATF Temp'].max() > 220:
        issues.append("⚠ High CVT fluid temperature detected (>220°F).")
    if (df_clean['Engine Speed'] - df_clean['Turbine RPM']).abs().mean() > 300:
        issues.append("⚠ Possible torque converter slip.")
    if (df_clean['Line Pressure'] < 170).any():
        issues.append("⚠ Line pressure dropped below 170psi during load.")
    
    if issues:
        st.warning("🛠 Diagnostic Findings:")
        for issue in issues:
            st.write(f"- {issue}")
    else:
        st.success("✅ No critical CVT issues detected in this session.")

    # Optional Repair Section
    st.markdown("### 🔧 Optional Repair Recommendations")
    if st.checkbox("Include recommendations in PDF report?"):
        repair_suggestions = [
            "• Perform CVTF exchange with Subaru High Torque CVTF.",
            "• Reflash TCM with latest firmware (check SOA updates).",
            "• Perform solenoid pressure test on line and secondary regulators.",
            "• Inspect torque converter clutch for judder or wear symptoms."
        ]
        for tip in repair_suggestions:
            st.write(tip)
    else:
        repair_suggestions = []

    # PDF Export
    def generate_pdf():
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "CVT Diagnostic Report")

        c.setFont("Helvetica", 12)
        y = 720
        c.drawString(50, y, "Summary:")
        for issue in issues:
            y -= 20
            c.drawString(70, y, f"- {issue}")
        
        if repair_suggestions:
            y -= 40
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Recommended Actions:")
            c.setFont("Helvetica", 12)
            for tip in repair_suggestions:
                y -= 20
                c.drawString(70, y, tip)

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

    if st.button("📄 Download PDF Report"):
        pdf = generate_pdf()
        st.download_button("Download Report", data=pdf, file_name="CVT_Diagnostic_Report.pdf")