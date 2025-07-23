import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io

st.set_page_config(layout="wide")
st.title("🧠 CVT Doctor Pro")
st.markdown("Upload your Subaru CVT data file exported from SSM4 or BtSsm.")

# Utility
def safe_float(x):
    try:
        return float(x)
    except:
        return np.nan

# Load CSV and auto-skip metadata rows
def load_csv(file):
    df = pd.read_csv(file, skiprows=8, encoding='ISO-8859-1')
    df = df.applymap(safe_float)
    return df

# Core PID mappings
def get_column(df, name):
    for col in df.columns:
        if name.lower() in col.lower():
            return col
    return None

# Transmission type detection
def detect_transmission(df):
    if any("Front Wheel Speed (RPM)" in col for col in df.columns):
        return "TR690"
    return "TR580"
# Common PID getters
def get_throttle(df):
    col = get_column(df, "Accel. Opening Angle") or get_column(df, "Throttle Opening Angle")
    return df[col] if col else None

def get_speed(df):
    col = get_column(df, "Front Wheel Speed (RPM)") or get_column(df, "Vehicle Speed")
    return df[col] if col else None

def get_time(df):
    t_col = get_column(df, "TIME")
    return df[t_col] / 1000 if t_col else pd.Series(np.arange(len(df)) / 10)

def is_throttle_stable(throttle, window=10):
    return throttle.rolling(window=window).std() < 2

def get_peak_time(events, time_series):
    if time_series is not None and events.any():
        peak_index = events[events].rolling(10).sum().idxmax()
        return float(time_series.iloc[peak_index]) if peak_index < len(time_series) else None
    return None
def detect_micro_slip(df, time_series):
    gear = df.get(get_column(df, "Actual Gear Ratio"))
    prim = df.get(get_column(df, "Primary Rev Speed"))
    sec = df.get(get_column(df, "Secondary Rev Speed"))
    throttle = get_throttle(df)
    speed = get_speed(df)
    if any(v is None for v in [gear, prim, sec, throttle, speed]) or (speed <= 10).all():
        return False, None, 0

    stable = is_throttle_stable(throttle)
    gear_fluct = gear.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 0.06
    rpm_fluct = (
        prim.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 50
    ) & (
        sec.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 50
    )
    candidate = (gear_fluct & rpm_fluct & stable & (throttle > 10) & (speed > 10))
    score = candidate.rolling(10).sum()
    confidence = min(100, score.max() * 10)
    confirmed = score > 5

    return confirmed.any(), get_peak_time(confirmed, time_series), confidence

def detect_short_time_slip(df, time_series):
    gear = df.get(get_column(df, "Actual Gear Ratio"))
    throttle = get_throttle(df)
    primary = df.get(get_column(df, "Primary Rev Speed"))
    secondary = df.get(get_column(df, "Secondary Rev Speed"))
    speed = get_speed(df)
    if any(v is None for v in [gear, throttle, primary, secondary, speed]) or (speed <= 10).all():
        return False, None, 0

    gear_spike = gear.diff().abs() > 0.1
    rpm_fluct = primary.diff().abs().combine(secondary.diff().abs(), max) > 100
    events = gear_spike & rpm_fluct & (throttle > 10) & (gear > 1.5) & (speed > 10)
    confidence = min(100, events.rolling(10).sum().max() * 10)

    return events.any(), get_peak_time(events, time_series), confidence
def simulate_long_time_slip(df, time_series):
    duty = df.get(get_column(df, "Primary UP Duty"))
    gear = df.get(get_column(df, "Actual Gear Ratio"))
    prim = df.get(get_column(df, "Primary Rev Speed"))
    sec = df.get(get_column(df, "Secondary Rev Speed"))
    throttle = get_throttle(df)
    speed = get_speed(df)
    if any(v is None for v in [duty, gear, prim, sec, throttle, speed]) or (speed <= 10).all():
        return False, None, 0

    gear_drop = gear.rolling(5).mean() < gear.mean()
    rpm_fluct = prim.diff().abs().combine(sec.diff().abs(), max) > 50
    active = (duty > 90) & gear_drop & (throttle > 10)
    events = active & rpm_fluct & (speed > 10)
    confidence = min(100, events.rolling(10).sum().max() * 10)
    return events.any(), get_peak_time(events, time_series), confidence

def detect_forward_clutch_slip(df, time_series, tr690=True):
    upstream = df.get(get_column(df, "Secondary Rev Speed") if tr690 else get_column(df, "Turbine Revolution Speed"))
    downstream = df.get(get_column(df, "Front Wheel Speed (RPM)") if tr690 else get_column(df, "Primary Rev Speed"))
    if upstream is None or downstream is None:
        return False, None, 0
    delta = upstream - downstream
    mismatch = delta.abs().rolling(5).mean() > 75
    confidence = min(100, mismatch.rolling(10).sum().max() * 10)
    return mismatch.any(), get_peak_time(mismatch, time_series), confidence

def detect_lockup_judder(df, time_series):
    throttle = get_throttle(df)
    primary = df.get(get_column(df, "Primary Rev Speed"))
    secondary = df.get(get_column(df, "Secondary Rev Speed"))
    speed = get_speed(df)
    if any(v is None for v in [throttle, primary, secondary, speed]) or (speed <= 10).all():
        return False, None, 0
    rpm_fluct = primary.diff().abs().combine(secondary.diff().abs(), max) > 50
    events = (throttle > 10) & rpm_fluct & (speed > 10)
    score = events.rolling(10).sum()
    confidence = min(100, score.max() * 10)
    return score.max() > 5, get_peak_time(events, time_series), confidence

def detect_torque_converter_judder(df, time_series):
    primary = df.get(get_column(df, "Primary Rev Speed"))
    secondary = df.get(get_column(df, "Secondary Rev Speed"))
    throttle = get_throttle(df)
    speed = get_speed(df)
    if any(v is None for v in [primary, secondary, throttle, speed]) or (speed <= 10).all():
        return False, None, 0
    fluct = (primary.diff().abs() > 50) & (secondary.diff().abs() > 50)
    load = (throttle > 10) & (speed > 10)
    sustained = fluct.rolling(10).sum() > 5
    events = sustained & load
    confidence = min(100, events.rolling(10).sum().max() * 10)
    return events.any(), get_peak_time(events, time_series), confidence
# --- Streamlit UI ---
uploaded_file = st.file_uploader("Upload SSM4/BtSsm CSV:", type=["csv"])
if uploaded_file:
    df = load_csv(uploaded_file)
    time_series = get_time(df)
    tr_type = detect_transmission(df)
    st.success(f"Transmission Detected: **{tr_type}**")

    st.subheader("📋 Diagnostic Results")
    results = {
        "Chain Slip": (detect_chain_slip(df, time_series), "Replace CVT & TCM if confirmed via SSM; submit QMR."),
        "Micro Slip": (detect_micro_slip(df, time_series), "Replace CVT after confirming persistent fluctuation."),
        "Short-Time Slip": (detect_short_time_slip(df, time_series), "Reprogram TCM; replace CVT if slip persists."),
        "Long-Time Slip": (simulate_long_time_slip(df, time_series), "Reprogram TCM; monitor for progressive wear."),
        "Forward Clutch Slip": (detect_forward_clutch_slip(df, time_series, tr690=(tr_type == "TR690")), "Reprogram TCM; replace valve body or CVT."),
        "Lock-Up Judder": (detect_lockup_judder(df, time_series), "Reprogram TCM; check ATF; replace converter if needed."),
        "Torque Converter Judder": (detect_torque_converter_judder(df, time_series), "Replace converter; inspect pump & solenoids.")
    }

    for label, ((detected, peak_time, confidence), recommendation) in results.items():
        if detected:
            peak = f" at {peak_time:.1f}s" if peak_time is not None else ""
            st.markdown(f"- **{label}**: ⚠️ Detected{peak} — _{recommendation}_")
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• Confidence: **{confidence:.1f}%**")

            # Debug chart
            st.markdown(f"#### 📈 {label} Debug Chart")
            fig, ax = plt.subplots()
            if "Gear" in label:
                ax.plot(time_series, df.get(get_column(df, "Actual Gear Ratio")), label="Actual Gear Ratio")
            if label in ["Forward Clutch Slip"]:
                ax.plot(time_series, df.get(get_column(df, "Secondary Rev Speed")), label="Secondary RPM")
                ax.plot(time_series, df.get(get_column(df, "Front Wheel Speed (RPM)")), label="Front Wheel RPM")
            if "Judder" in label:
                ax.plot(time_series, df.get(get_column(df, "Primary Rev Speed")), label="Primary RPM")
                ax.plot(time_series, df.get(get_column(df, "Secondary Rev Speed")), label="Secondary RPM")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Sensor Value")
            ax.set_title(label)
            ax.legend()
            st.pyplot(fig)
        else:
            st.markdown(f"- **{label}**: ✅ Not Detected")

    st.divider()
    st.markdown("[📎 View Subaru TSB 16-132-20R](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226904-0001.pdf)")