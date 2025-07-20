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
st.title("🔧 CVT Doctor Pro – Advanced Subaru CVT Analyzer (TSB-Calibrated)")

# --- Modular Diagnostic Functions ---
def detect_chain_slip(df):
    events = []
    if 'Engine RPM' in df.columns and 'Primary RPM' in df.columns:
        rpm_diff = (df['Engine RPM'] - df['Primary RPM']).abs()
        for i, val in enumerate(rpm_diff):
            if val > 350:
                events.append({'Type': 'Chain Slip', 'Time': df.index[i], 'Severity': 'High', 'Details': f'RPM Δ={val:.0f}'})
    return events

def detect_secondary_rpm_slip(df):
    events = []
    if 'Primary RPM' in df.columns and 'Secondary RPM' in df.columns:
        rpm_diff = (df['Primary RPM'] - df['Secondary RPM']).abs()
        for i, val in enumerate(rpm_diff):
            if val > 300:
                events.append({'Type': 'Secondary Pulley Slip', 'Time': df.index[i], 'Severity': 'High', 'Details': f'RPM Δ={val:.0f}'})
    return events

def detect_micro_slip(df):
    events = []
    if 'Throttle %' in df.columns and 'Gear Ratio' in df.columns:
        stable = df['Throttle %'].rolling(10, min_periods=1).std() < 2
        ratio_var = df['Gear Ratio'].rolling(10, min_periods=1).apply(lambda x: x.max() - x.min())
        for i in range(len(df)):
            if stable.iloc[i] and ratio_var.iloc[i] > 0.01:
                events.append({'Type': 'Micro Slip', 'Time': df.index[i], 'Severity': 'Low', 'Details': f'Ratio Δ={ratio_var.iloc[i]:.3f}'})
    return events
def detect_short_slip(df):
    events = []
    if 'Gear Ratio' in df.columns:
        jumps = df['Gear Ratio'].diff().abs()
        for i, val in enumerate(jumps):
            if val > 0.05:
                events.append({'Type': 'Short Slip', 'Time': df.index[i], 'Severity': 'Moderate', 'Details': f'Δ={val:.2f}'})
    return events

def detect_long_slip(df):
    events = []
    if 'Primary UP Duty' in df.columns and 'Gear Ratio' in df.columns:
        drop = df['Gear Ratio'].rolling(3).mean().diff()
        high_duty = df['Primary UP Duty'] > 80
        for i in range(2, len(df)):
            if high_duty.iloc[i] and drop.iloc[i] < -0.03:
                events.append({'Type': 'Long Slip', 'Time': df.index[i], 'Severity': 'High', 'Details': f'Drop={drop.iloc[i]:.2f}'})
    return events

def detect_lockup_slip(df):
    events = []
    if 'TCC Lockup %' in df.columns and 'Turbine RPM' in df.columns:
        delta = df['Turbine RPM'].diff().abs()
        for i in range(len(df)):
            if df['TCC Lockup %'].iloc[i] > 80 and delta.iloc[i] > 100:
                events.append({'Type': 'Lockup Slip', 'Time': df.index[i], 'Severity': 'Moderate', 'Details': f'RPM Δ={delta.iloc[i]:.0f}'})
    return events

def detect_shock_events(df):
    events = []
    if 'TCC Lockup %' in df.columns and 'Engine RPM' in df.columns:
        lockup_delta = df['TCC Lockup %'].diff()
        rpm_delta = df['Engine RPM'].diff()
        for i in range(1, len(df)):
            if lockup_delta.iloc[i] > 20 and rpm_delta.iloc[i] < -200:
                events.append({'Type': 'Clutch Shock', 'Time': df.index[i], 'Severity': 'Moderate', 'Details': f'RPM drop={rpm_delta.iloc[i]:.0f}'})
    return events

def detect_pressure_temp(df):
    events = []
    if 'Line Pressure (psi)' in df.columns and (df['Line Pressure (psi)'] < 170).any():
        events.append({'Type': 'Low Line Pressure', 'Time': df[df['Line Pressure (psi)'] < 170].index[0], 'Severity': 'Moderate', 'Details': '<170 psi'})
    if 'ATF Temp (°F)' in df.columns and df['ATF Temp (°F)'].max() > 160:
        events.append({'Type': 'High ATF Temp', 'Time': df[df['ATF Temp (°F)'] > 160].index[0], 'Severity': 'Moderate', 'Details': '>160°F'})
    return events
# --- Event Aggregation ---
def aggregate_events(df):
    all_events = []
    for func in [detect_chain_slip, detect_secondary_rpm_slip, detect_micro_slip,
                 detect_short_slip, detect_long_slip, detect_lockup_slip,
                 detect_shock_events, detect_pressure_temp]:
        all_events.extend(func(df))
    return sorted(all_events, key=lambda x: x["Time"])

# --- Streamlit Interface ---
uploaded_file = st.file_uploader("📤 Upload Subaru CVT CSV Log", type=["csv"])
if uploaded_file:
    raw = uploaded_file.read().decode("ISO-8859-1").splitlines()
    header_row = 8
    df = pd.read_csv(BytesIO('\n'.join(raw[header_row:]).encode("utf-8")))
    df.index = range(len(df))
    st.success("✅ File loaded successfully.")

    # Plot Engine vs Primary RPM
    if 'Engine RPM' in df.columns and 'Primary RPM' in df.columns:
        fig, ax = plt.subplots()
        ax.plot(df['Engine RPM'], label='Engine RPM')
        ax.plot(df['Primary RPM'], label='Primary RPM', alpha=0.7)
        ax.set_title("RPM Comparison")
        ax.legend()
        st.pyplot(fig)

    # Run diagnostics
    events = aggregate_events(df)
    if events:
        st.subheader("⚠️ Diagnostic Events")
        st.dataframe(pd.DataFrame(events))
    else:
        st.success("✅ No major issues detected based on current thresholds.")

    # Generate PDF summary
    if st.button("📄 Export PDF Report"):
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont("Helvetica", 12)
        c.drawString(30, 750, "CVT Doctor Pro Diagnostic Report")
        c.drawString(30, 735, f"Total Events: {len(events)}")
        y = 710
        for ev in events:
            line = f"{ev['Time']}: {ev['Type']} [{ev['Severity']}] - {ev['Details']}"
            c.drawString(30, y, line)
            y -= 15
            if y < 40:
                c.showPage()
                y = 750
        c.save()
        buffer.seek(0)
        st.download_button("Download PDF", buffer, file_name="cvt_diagnostic_report.pdf")