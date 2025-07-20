import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro – Subaru CVT Analyzer (Safe Version)")

column_rename_map = {
    "Engine Speed": "Engine RPM",
    "Primary Rev Speed": "Primary RPM",
    "Secondary Rev Speed": "Secondary RPM",
    "Accel. Opening Angle": "Throttle %",
    "Turbine Revolution Speed": "Turbine RPM",
    "Actual Gear Ratio": "Gear Ratio",
    "Lock Up Duty Ratio": "TCC Lockup %",
    "ATF Temp.": "ATF Temp (°F)"
}

def detect_chain_slip(df):
    events = []
    rpm1 = pd.to_numeric(df.get("Engine RPM"), errors="coerce")
    rpm2 = pd.to_numeric(df.get("Primary RPM"), errors="coerce")
    rpm_diff = (rpm1 - rpm2).abs()
    for i, val in enumerate(rpm_diff):
        if val > 350:
            events.append({'Type': 'Chain Slip', 'Time': i, 'Severity': 'High', 'Details': f'RPM Δ={val:.0f}'})
    return events

def detect_secondary_rpm_slip(df):
    events = []
    p1 = pd.to_numeric(df.get("Primary RPM"), errors="coerce")
    s2 = pd.to_numeric(df.get("Secondary RPM"), errors="coerce")
    rpm_diff = (p1 - s2).abs()
    for i, val in enumerate(rpm_diff):
        if val > 300:
            events.append({'Type': 'Secondary Pulley Slip', 'Time': i, 'Severity': 'High', 'Details': f'RPM Δ={val:.0f}'})
    return events

def detect_micro_slip(df):
    events = []
    throttle = pd.to_numeric(df.get("Throttle %"), errors="coerce")
    ratio = pd.to_numeric(df.get("Gear Ratio"), errors="coerce")
    stable = throttle.rolling(10, min_periods=1).std() < 2
    ratio_var = ratio.rolling(10, min_periods=1).apply(lambda x: x.max() - x.min())
    for i in range(len(df)):
        if stable.iloc[i] and ratio_var.iloc[i] > 0.01:
            events.append({'Type': 'Micro Slip', 'Time': i, 'Severity': 'Low', 'Details': f'Ratio Δ={ratio_var.iloc[i]:.3f}'})
    return events

def detect_short_slip(df):
    events = []
    ratio = pd.to_numeric(df.get("Gear Ratio"), errors="coerce")
    jumps = ratio.diff().abs()
    for i, val in enumerate(jumps):
        if val > 0.05:
            events.append({'Type': 'Short Slip', 'Time': i, 'Severity': 'Moderate', 'Details': f'Δ={val:.2f}'})
    return events

def detect_long_slip(df):
    events = []
    up_duty = pd.to_numeric(df.get("Primary UP Duty"), errors="coerce")
    ratio = pd.to_numeric(df.get("Gear Ratio"), errors="coerce")
    drop = ratio.rolling(3).mean().diff()
    high_duty = up_duty > 80
    for i in range(2, len(df)):
        if high_duty.iloc[i] and drop.iloc[i] < -0.03:
            events.append({'Type': 'Long Slip', 'Time': i, 'Severity': 'High', 'Details': f'Drop={drop.iloc[i]:.2f}'})
    return events

def detect_lockup_slip(df):
    events = []
    lock = pd.to_numeric(df.get("TCC Lockup %"), errors="coerce")
    turb = pd.to_numeric(df.get("Turbine RPM"), errors="coerce")
    delta = turb.diff().abs()
    for i in range(len(df)):
        if lock.iloc[i] > 80 and delta.iloc[i] > 100:
            events.append({'Type': 'Lockup Slip', 'Time': i, 'Severity': 'Moderate', 'Details': f'RPM Δ={delta.iloc[i]:.0f}'})
    return events

def detect_shock_events(df):
    events = []
    lock = pd.to_numeric(df.get("TCC Lockup %"), errors="coerce")
    rpm = pd.to_numeric(df.get("Engine RPM"), errors="coerce")
    lock_delta = lock.diff()
    rpm_delta = rpm.diff()
    for i in range(1, len(df)):
        if lock_delta.iloc[i] > 20 and rpm_delta.iloc[i] < -200:
            events.append({'Type': 'Clutch Shock', 'Time': i, 'Severity': 'Moderate', 'Details': f'RPM drop={rpm_delta.iloc[i]:.0f}'})
    return events

def detect_pressure_temp(df):
    events = []
    pressure = pd.to_numeric(df.get("Line Pressure (psi)"), errors="coerce")
    temp = pd.to_numeric(df.get("ATF Temp (°F)"), errors="coerce")
    if pressure is not None and (pressure < 170).any():
        events.append({'Type': 'Low Line Pressure', 'Time': pressure[pressure < 170].index[0], 'Severity': 'Moderate', 'Details': '<170 psi'})
    if temp is not None and temp.max() > 160:
        events.append({'Type': 'High ATF Temp', 'Time': temp[temp > 160].index[0], 'Severity': 'Moderate', 'Details': '>160°F'})
    return events

def aggregate_events(df):
    all_events = []
    for func in [detect_chain_slip, detect_secondary_rpm_slip, detect_micro_slip,
                 detect_short_slip, detect_long_slip, detect_lockup_slip,
                 detect_shock_events, detect_pressure_temp]:
        all_events.extend(func(df))
    return sorted(all_events, key=lambda x: x["Time"])

# Streamlit UI
uploaded_file = st.file_uploader("📤 Upload Subaru CVT CSV Log", type=["csv"])
if uploaded_file:
    raw = uploaded_file.read().decode("ISO-8859-1").splitlines()
    df = pd.read_csv(BytesIO('\n'.join(raw[8:]).encode("utf-8")))
    df.rename(columns=column_rename_map, inplace=True)
    df.index = range(len(df))
    st.success("✅ File loaded and columns mapped.")

    # Plot RPMs
    if 'Engine RPM' in df.columns and 'Primary RPM' in df.columns:
        fig, ax = plt.subplots()
        x_vals = df.index.astype(int)
        ax.plot(x_vals, pd.to_numeric(df['Engine RPM'], errors='coerce'), label='Engine RPM')
        ax.plot(x_vals, pd.to_numeric(df['Primary RPM'], errors='coerce'), label='Primary RPM', alpha=0.7)
        ax.set_title("RPM Comparison")
        ax.set_xlabel("Sample")
        ax.set_ylabel("RPM")
        ax.legend()
        st.pyplot(fig)

    events = aggregate_events(df)
    if events:
        st.subheader("⚠️ Diagnostic Events")
        st.dataframe(pd.DataFrame(events))
    else:
        st.success("✅ No major faults detected based on thresholds.")

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