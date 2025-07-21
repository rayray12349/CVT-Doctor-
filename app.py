import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

st.set_page_config(page_title="CVT Doctor Pro – 7 Mode TSB", layout="wide")
st.title("🧠 CVT Doctor Pro – Subaru TSB 7 Concern Diagnostic")

column_rename_map = {
    "Engine Speed": "Engine RPM",
    "Primary Rev Speed": "Primary RPM",
    "Secondary Rev Speed": "Secondary RPM",
    "Accel. Opening Angle": "Throttle %",
    "Turbine Revolution Speed": "Turbine RPM",
    "Actual Gear Ratio": "Gear Ratio",
    "Lock Up Duty Ratio": "TCC Lockup %",
    "ATF Temp.": "ATF Temp (°F)",
    "Front Wheel Speed": "Front Wheel Speed (RPM)"
}

cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])
def detect_forward_clutch_slip(df):
    events = []
    eng_rpm = pd.to_numeric(df.get("Engine RPM"), errors="coerce")
    if "Front Wheel Speed (RPM)" not in df.columns:
        st.warning("Missing 'Front Wheel Speed (RPM)' column for TR690.")
        return []
    wheel_rpm = pd.to_numeric(df.get("Front Wheel Speed (RPM)"), errors="coerce")
    for i in range(len(df)):
        if eng_rpm.iloc[i] > 1200 and abs(eng_rpm.iloc[i] - wheel_rpm.iloc[i]) > 600:
            events.append({"Type": "Forward Clutch Slip", "Time": i, "Details": f"RPM Δ > 600 ({eng_rpm.iloc[i]} vs {wheel_rpm.iloc[i]})"})
    return events

def detect_micro_slip(df):
    events = []
    throttle = pd.to_numeric(df.get("Throttle %"), errors="coerce")
    gear_ratio = pd.to_numeric(df.get("Gear Ratio"), errors="coerce")
    primary_rpm = pd.to_numeric(df.get("Primary RPM"), errors="coerce")
    secondary_rpm = pd.to_numeric(df.get("Secondary RPM"), errors="coerce")
    throttle_std = throttle.rolling(10, min_periods=1).std()
    primary_fluct = primary_rpm.diff().abs().rolling(5).mean()
    secondary_fluct = secondary_rpm.diff().abs().rolling(5).mean()
    ratio_fluct = gear_ratio.diff().abs().rolling(5).mean()
    for i in range(len(df)):
        if (throttle_std.iloc[i] < 1.5 and
            ((primary_fluct.iloc[i] > 50) or (secondary_fluct.iloc[i] > 50)) and
            ratio_fluct.iloc[i] > 0.02):
            events.append({"Type": "Micro Slip", "Time": i, "Details": "Fluctuating RPM/ratio under steady throttle"})
    return events
def detect_judder(df):
    events = []
    gear_ratio = pd.to_numeric(df.get("Gear Ratio"), errors="coerce")
    judder_score = gear_ratio.diff().rolling(5).std()
    for i in range(len(df)):
        if judder_score.iloc[i] > 0.05:
            events.append({"Type": "Judder Detected", "Time": i, "Details": f"Gear Ratio variance: {judder_score.iloc[i]:.4f}"})
    return events

def detect_lockup_issue(df):
    events = []
    tcc = pd.to_numeric(df.get("TCC Lockup %"), errors="coerce")
    turbine_rpm = pd.to_numeric(df.get("Turbine RPM"), errors="coerce")
    secondary_rpm = pd.to_numeric(df.get("Secondary RPM"), errors="coerce")
    for i in range(len(df)):
        if tcc.iloc[i] > 85 and abs(turbine_rpm.iloc[i] - secondary_rpm.iloc[i]) > 200:
            events.append({"Type": "Lockup Malfunction", "Time": i, "Details": f"TCC active, RPM Δ > 200"})
    return events

def detect_solenoid_delay(df):
    events = []
    throttle = pd.to_numeric(df.get("Throttle %"), errors="coerce")
    gear_ratio = pd.to_numeric(df.get("Gear Ratio"), errors="coerce")
    for i in range(1, len(df)):
        if throttle.iloc[i] > 10 and gear_ratio.iloc[i-1] == gear_ratio.iloc[i]:
            events.append({"Type": "Solenoid Delay", "Time": i, "Details": "No gear ratio response after throttle"})
    return events
    def detect_long_slip(df):
    events = []
    primary = pd.to_numeric(df.get("Primary RPM"), errors="coerce")
    secondary = pd.to_numeric(df.get("Secondary RPM"), errors="coerce")
    for i in range(len(df)):
        if primary.iloc[i] - secondary.iloc[i] > 800:
            events.append({"Type": "Long Slip", "Time": i, "Details": f"RPM Δ = {primary.iloc[i] - secondary.iloc[i]}"})
    return events

def detect_short_slip(df):
    events = []
    primary = pd.to_numeric(df.get("Primary RPM"), errors="coerce")
    secondary = pd.to_numeric(df.get("Secondary RPM"), errors="coerce")
    slip = primary - secondary
    for i in range(3, len(df)):
        if all((slip.iloc[i-j] > 500 and slip.iloc[i-j] < 800) for j in range(3)):
            events.append({"Type": "Short Slip", "Time": i, "Details": "3-frame slip between 500–800 RPM"})
    return events