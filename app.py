import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro – Subaru CVT Diagnostic Analyzer (TSB Compliant)")

# --- Modular Diagnostic Functions ---
def detect_chain_slip(df):
    events = []
    if 'Engine RPM' in df.columns and 'Primary RPM' in df.columns:
        rpm_diff = (df['Engine RPM'] - df['Primary RPM']).abs()
        for i, val in enumerate(rpm_diff):
            if val > 400:
                events.append({'Type': 'Chain Slip', 'Time': df.index[i], 'Severity': 'High', 'Details': f'RPM Δ={val:.0f}'})
    return events

def detect_micro_slip(df):
    events = []
    if 'Throttle %' in df.columns and 'Gear Ratio' in df.columns:
        stable = df['Throttle %'].rolling(10, min_periods=1).std() < 1
        ratio_var = df['Gear Ratio'].rolling(10, min_periods=1).apply(lambda x: x.max() - x.min())
        for i in range(len(df)):
            if stable.iloc[i] and ratio_var.iloc[i] > 0.02:
                events.append({'Type': 'Micro Slip', 'Time': df.index[i], 'Severity': 'Moderate', 'Details': f'Ratio Δ={ratio_var.iloc[i]:.3f}'})
    return events

def detect_short_slip(df):
    events = []
    if 'Gear Ratio' in df.columns:
        jumps = df['Gear Ratio'].diff().abs()
        for i, val in enumerate(jumps):
            if val > 0.1:
                events.append({'Type': 'Short Slip', 'Time': df.index[i], 'Severity': 'Moderate', 'Details': f'Δ={val:.2f}'})
    return events

def detect_long_slip(df):
    events = []
    if 'Primary UP Duty' in df.columns and 'Gear Ratio' in df.columns:
        drop = df['Gear Ratio'].rolling(3).mean().diff()
        high_duty = df['Primary UP Duty'] > 90
        for i in range(2, len(df)):
            if high_duty.iloc[i] and drop.iloc[i] < -0.05:
                events.append({'Type': 'Long Slip', 'Time': df.index[i], 'Severity': 'High', 'Details': f'Drop={drop.iloc[i]:.2f}'})
    return events

def detect_lockup_slip(df):
    events = []
    if 'TCC Lockup %' in df.columns and 'Turbine RPM' in df.columns:
        delta = df['Turbine RPM'].diff().abs()
        for i in range(len(df)):
            if df['TCC Lockup %'].iloc[i] > 80 and delta.iloc[i] > 150:
                events.append({'Type': 'Lockup Slip', 'Time': df.index[i], 'Severity': 'Moderate', 'Details': f'RPM Δ={delta.iloc[i]:.0f}'})
    return events

def detect_pressure_temp(df):
    events = []
    if 'Line Pressure (psi)' in df.columns and (df['Line Pressure (psi)'] < 170).any():
        events.append({'Type': 'Low Line Pressure', 'Time': df[df['Line Pressure (psi)'] < 170].index[0], 'Severity': 'Moderate', 'Details': '<170 psi'})
    if 'ATF Temp (°F)' in df.columns and df['ATF Temp (°F)'].max() > 220:
        events.append({'Type': 'High ATF Temp', 'Time': df[df['ATF Temp (°F)'] > 220].index[0], 'Severity': 'Moderate', 'Details': '>220°F'})
    return events

# --- File Upload & Processing ---
uploaded_file = st.file_uploader("📤 Upload SSM4/BtSsm CSV", type=["csv"])
if uploaded_file:
    lines = uploaded_file.getvalue().decode('ISO-8859-1').splitlines()
    header_row = next((i for i, line in enumerate(lines[:100]) if 'Primary' in line or 'Gear Ratio' in line), 0)
    df = pd.read_csv(uploaded_file, encoding='ISO-8859-1', skiprows=header_row)

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

    if 'Time' in df.columns:
        df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
        df.set_index('Time', inplace=True)
    else:
        df.index = pd.date_range(start='2024-01-01', periods=len(df), freq='1S')

    df = df.dropna(subset=[v for v in pid_map.values() if v in df.columns])
    st.success("✅ Data parsed successfully.")

    # --- Run All Diagnostics ---
    all_events = []
    all_events += detect_chain_slip(df)
    all_events += detect_micro_slip(df)
    all_events += detect_short_slip(df)
    all_events += detect_long_slip(df)
    all_events += detect_lockup_slip(df)
    all_events += detect_pressure_temp(df)

    # --- Show Results ---
    st.markdown("### 🛠 Event Log")
    if all_events:
        events_df = pd.DataFrame(all_events)
        st.dataframe(events_df)
    else:
        st.success("✅ No faults detected")

    st.markdown("### 📊 Diagnostic Graph")
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df['Engine RPM'], label='Engine RPM')
    ax.plot(df['Primary RPM'], label='Primary RPM', linestyle='--')
    if all_events:
        for e in all_events:
            ax.axvline(e['Time'], color='red', linestyle=':', alpha=0.5)
    ax.set_title("Engine vs Primary RPM with Events")
    ax.legend()
    ax.grid()
    st.pyplot(fig)

    # --- PDF Report Generation ---
    def generate_pdf(events):
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "CVT Doctor Pro – Diagnostic Report")
        c.setFont("Helvetica", 12)
        y = 720
        c.drawString(50, y, "Detected Issues:")
        for e in events:
            y -= 18
            c.drawString(70, y, f"[{e['Time']}] {e['Type']} – {e['Severity']} – {e['Details']}")
        if not events:
            y -= 18
            c.drawString(70, y, "No issues detected.")

        y -= 40
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Repair Recommendations (TSB 16-132-20R):")
        c.setFont("Helvetica", 12)
        recommendations = [
            "• Submit QMR with this report and SSM logs before CVT replacement.",
            "• If long slip or short slip confirmed, consider CVT and TCM replacement.",
            "• Ensure ATF temperature and line pressure are within spec.",
            "• Reprogram TCM using appropriate Subaru PAK file if applicable."
        ]
        for tip in recommendations:
            y -= 18
            c.drawString(70, y, tip)

        try:
            tsb_img = ImageReader("subaru_cvt_tsb_flowchart.png")
            c.drawImage(tsb_img, 50, 100, width=500, preserveAspectRatio=True)
        except:
            pass

        c.save()
        buffer.seek(0)
        return buffer

    if st.button("📄 Download PDF Report"):
        pdf = generate_pdf(all_events)
        st.download_button("Download PDF", data=pdf, file_name="CVT_Doctor_Pro_Report.pdf")