import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

st.set_page_config(page_title="CVT Doctor", layout="wide")
st.title("🔧 CVT Doctor – Subaru CVT Diagnostic Analyzer (TSB Enhanced)")

uploaded_file = st.file_uploader("📤 Upload SSM4/BtSsm CSV", type=["csv"])

if uploaded_file:
    # Try to detect header
    lines = uploaded_file.getvalue().decode('ISO-8859-1').splitlines()
    header_row = next((i for i, line in enumerate(lines[:100]) if 'Primary' in line or 'Gear Ratio' in line), 0)
    df = pd.read_csv(uploaded_file, encoding='ISO-8859-1', skiprows=header_row)

    # Key PID mapping
    pid_map = {
        'Engine Speed': 'Engine RPM',
        'Primary Rev Speed': 'Primary RPM',
        'Turbine Revolution Speed': 'Turbine RPM',
        'Accel. Opening Angle': 'Throttle %',
        'Actual Gear Ratio': 'Gear Ratio',
        'Lock Up Duty Ratio': 'TCC Lockup %',
        'ATF Temp.': 'ATF Temp (°F)',
        'Actual line press.': 'Line Pressure (psi)',
        'Lin. Sol. Set Current': 'Set Current (mA)',
        'Lin. Sol. Actual Current': 'Actual Current (mA)',
        'System Voltage': 'Voltage',
        'Primary UP Duty': 'Primary UP Duty'
    }

    for old, new in pid_map.items():
        if old in df.columns:
            df[new] = pd.to_numeric(df[old], errors='coerce')

    df_clean = df.dropna(subset=[v for v in pid_map.values() if v in df.columns])
    st.success("✅ Data parsed successfully.")

    # Begin Diagnostics
    issues = []

    # Chain Slip - Classic
    if (df_clean['Engine RPM'] - df_clean['Primary RPM']).abs().max() > 400:
        issues.append("⚠ Chain slip suspected: Engine vs Primary RPM exceeds 400+ RPM.")

    # Short-Time Slip
    if (df_clean['Gear Ratio'].diff().abs() > 0.1).any():
        issues.append("⚠ Short-time gear ratio spike (>0.1) — may indicate chain slip (TSB).")

    # Long-Time Slip (requires Primary UP Duty)
    if 'Primary UP Duty' in df.columns:
        df['Primary UP Duty'] = pd.to_numeric(df['Primary UP Duty'], errors='coerce')
        long_slip = ((df['Primary UP Duty'] > 90) &
                     (df['Gear Ratio'].rolling(3).mean().diff() < -0.05)).any()
        if long_slip:
            issues.append("⚠ Long-time chain slip under high Primary UP Duty (TSB logic).")

    # Continuous Micro-Slip
    stable_throttle = df_clean['Throttle %'].rolling(10).std() < 1
    ratio_variation = df_clean['Gear Ratio'].rolling(10).apply(lambda x: x.max() - x.min())
    if ((ratio_variation > 0.02) & stable_throttle).any():
        issues.append("⚠ Continuous micro-slip detected during steady throttle (per TSB).")

    # Lockup issues
    if ((df_clean['TCC Lockup %'] > 80) & (df_clean['Turbine RPM'].diff().abs() > 150)).any():
        issues.append("⚠ Possible lock-up clutch slip during cruise/load.")

    # Line Pressure Drop
    if (df_clean['Line Pressure (psi)'] < 170).any():
        issues.append("⚠ Line pressure below safe threshold (<170 psi).")

    # Overheat
    if df_clean['ATF Temp (°F)'].max() > 220:
        issues.append("⚠ ATF temperature exceeded 220°F — check cooler operation.")

    # Visualizations
    st.markdown("### 📊 Diagnostic Graphs")
    fig, axs = plt.subplots(3, 1, figsize=(10, 12))

    axs[0].plot(df_clean['Engine RPM'], label='Engine RPM')
    axs[0].plot(df_clean['Primary RPM'], label='Primary RPM', linestyle='--')
    axs[0].set_title("Engine vs Primary RPM")
    axs[0].legend()
    axs[0].grid()

    axs[1].plot(df_clean['Throttle %'], label='Throttle %')
    axs[1].plot(df_clean['Gear Ratio'], label='Gear Ratio', linestyle='--')
    axs[1].set_title("Throttle vs Gear Ratio")
    axs[1].legend()
    axs[1].grid()

    axs[2].plot(df_clean['TCC Lockup %'], label='TCC Lockup %')
    axs[2].plot(df_clean['Turbine RPM'], label='Turbine RPM', linestyle='--')
    axs[2].set_title("Turbine RPM vs Lock-Up Duty")
    axs[2].legend()
    axs[2].grid()

    st.pyplot(fig)

    # Display Diagnostics
    st.markdown("### 🛠 Diagnostic Summary")
    if issues:
        for item in issues:
            st.warning(item)
    else:
        st.success("✅ No critical CVT issues detected.")

    # Repair Suggestions
    st.markdown("### 🧰 TSB-Based Recommendations")
    repair_tips = []
    if st.checkbox("Include TSB repair suggestions in PDF?"):
        repair_tips = [
            "• Submit QMR to SOA with SSM data if chain slip is confirmed.",
            "• Perform CVTF exchange with Subaru High Torque CVTF.",
            "• Replace CVT assembly and reprogram TCM if TSB criteria are met.",
            "• Review Primary UP Duty and solenoid currents for wear indicators."
        ]
        for tip in repair_tips:
            st.write(tip)

    # PDF Export
    def generate_pdf():
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "CVT Doctor Diagnostic Report (TSB Enhanced)")
        c.setFont("Helvetica", 12)
        y = 720
        c.drawString(50, y, "Findings:")

        for item in issues:
            y -= 20
            c.drawString(70, y, f"- {item}")

        if repair_tips:
            y -= 40
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Recommended Repairs:")
            c.setFont("Helvetica", 12)
            for tip in repair_tips:
                y -= 20
                c.drawString(70, y, tip)

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

    if st.button("📄 Download TSB-Style PDF Report"):
        pdf = generate_pdf()
        st.download_button("Download Report", data=pdf, file_name="CVT_TSB_Report.pdf")