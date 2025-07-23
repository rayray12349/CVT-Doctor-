import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io

def safe_float(x):
    try:
        return float(x)
    except:
        return np.nan

@st.cache_data
def load_csv(file):
    decoded = file.read().decode('utf-8', errors='ignore')
    df = pd.read_csv(io.StringIO(decoded), skiprows=8)
    df = df.applymap(safe_float)
    return df.dropna(axis=1, how='all')

def detect_tr690(df):
    return 'Front Wheel Speed.1' in df.columns
    
def get_throttle(df):
    t1 = df.get('Accel. Opening Angle')
    t2 = df.get('Throttle Opening Angle')
    if t1 is not None and t2 is not None:
        return t1.combine_first(t2)
    return t1 if t1 is not None else t2

def get_speed(df):
    s1 = df.get('Front Wheel Speed (RPM)')
    s2 = df.get('Vehicle Speed')
    if s1 is not None and s2 is not None:
        return s1.combine_first(s2)
    return s1 if s1 is not None else s2

def get_time(df):
    try:
        return df['TIME'].astype(float).reset_index(drop=True) / 1000
    except:
        return None

def get_confidence(events):
    return min(100, events.sum() * 2)

def get_peak_time(events, time_series):
    if time_series is not None and events.any():
        peak_index = events[events].rolling(10).sum().idxmax()
        return float(time_series.iloc[peak_index]) if peak_index < len(time_series) else None
    return None

def detect_micro_slip(df, time_series):
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')
    throttle = get_throttle(df)
    speed = get_speed(df)
    if any(v is None for v in [gear, prim, sec, throttle, speed]) or (speed <= 10).all():
        return False, None, 0
    gear_fluct = gear.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 0.03
    rpm_fluct = prim.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 75
    sec_fluct = sec.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 75
    stable = throttle.rolling(10).std() < 1.5
    events = gear_fluct & rpm_fluct & sec_fluct & (throttle > 1) & stable & (speed > 10)
    confirmed = events.rolling(10).sum() >= 3
    return confirmed.any(), get_peak_time(confirmed, time_series), get_confidence(confirmed)

def detect_short_time_slip(df, time_series):
    gear = df.get('Actual Gear Ratio')
    throttle = get_throttle(df)
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')
    speed = get_speed(df)
    if any(v is None for v in [gear, throttle, primary, secondary, speed]) or (speed <= 10).all():
        return False, None, 0
    gear_spike = gear.diff().abs() > 0.12
    rpm_fluct = (primary.diff().abs() > 100) | (secondary.diff().abs() > 100)
    events = gear_spike & rpm_fluct & (throttle > 1) & (speed > 10)
    return events.any(), get_peak_time(events, time_series), get_confidence(events)

def simulate_long_time_slip(df, time_series):
    duty = df.get('Primary UP Duty')
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')
    throttle = get_throttle(df)
    speed = get_speed(df)
    if any(v is None for v in [duty, gear, prim, sec, throttle, speed]) or (speed <= 10).all():
        return False, None, 0
    gear_drop = gear.rolling(5).mean() < gear.mean()
    rpm_fluct = (prim.diff().abs() > 50) | (sec.diff().abs() > 50)
    active = (duty > 90) & gear_drop & (throttle > 1)
    events = active & rpm_fluct & (speed > 10)
    return events.any(), get_peak_time(events, time_series), get_confidence(events)

def detect_forward_clutch_slip(df, time_series, tr690=True):
    upstream = df.get('Secondary Rev Speed')
    downstream = df.get('Front Wheel Speed.1') if tr690 else df.get('Primary Rev Speed')
    
    if upstream is None or downstream is None:
        return False, None, 0.0

    delta = upstream - downstream
    mismatch = delta.abs().rolling(5).mean() > 75
    confidence = min(100.0, mismatch.rolling(10).sum().max() * 10.0)
    return mismatch.any(), get_peak_time(mismatch, time_series), confidence
    
def detect_lockup_judder(df, time_series):
    throttle = get_throttle(df)
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')
    if any(v is None for v in [throttle, primary, secondary]):
        return False, None, 0
    fluct = primary.diff().abs().combine(secondary.diff().abs(), max) > 50
    events = (throttle > 10) & fluct
    confirmed = events.rolling(10).sum() > 5
    return confirmed.any(), get_peak_time(confirmed, time_series), get_confidence(confirmed)

def detect_torque_converter_judder(df, time_series):
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')
    if primary is None or secondary is None:
        return False, None, 0
    fluct = primary.rolling(10).std() > 40
    sec_fluct = secondary.rolling(10).std() > 40
    events = fluct & sec_fluct
    return events.any(), get_peak_time(events, time_series), get_confidence(events)

# ---------- Streamlit UI ----------

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro")
st.markdown("Subaru TR580 & TR690 CVT Diagnostic App — Based on TSB 16-132-20R")

uploaded_file = st.file_uploader("Upload your SSM4/BtSsm CSV file:", type=["csv"])
if uploaded_file:
    df = load_csv(uploaded_file)
    st.success("✅ File loaded successfully.")
    is_tr690 = detect_tr690(df)
    time_series = get_time(df)
    st.markdown(f"**Detected Transmission:** {'TR690' if is_tr690 else 'TR580'}")

    st.subheader("📊 Diagnostic Summary")

    results = {
        "Chain Slip": (False, None, 0),
        "Micro Slip": detect_micro_slip(df, time_series),
        "Short-Time Slip": detect_short_time_slip(df, time_series),
        "Long-Time Slip": simulate_long_time_slip(df, time_series),
        "Forward Clutch Slip": detect_forward_clutch_slip(df, time_series, tr690=is_tr690),
        "Lock-Up Judder": detect_lockup_judder(df, time_series),
        "Torque Converter Judder": detect_torque_converter_judder(df, time_series),
    }

    recommendations = {
        "Chain Slip": "Replace CVT & TCM if confirmed via SSM; submit QMR.",
        "Micro Slip": "Replace CVT after confirming persistent fluctuation.",
        "Short-Time Slip": "Reprogram TCM; replace CVT if slip persists.",
        "Long-Time Slip": "Reprogram TCM; monitor for progressive wear. (Simulated)",
        "Forward Clutch Slip": "Reprogram TCM; replace valve body or CVT.",
        "Lock-Up Judder": "Reprogram TCM; check ATF; replace converter if needed.",
        "Torque Converter Judder": "Replace torque converter; inspect pump & solenoids.",
    }

    for label, (detected, peak_time, confidence) in results.items():
        if detected:
            peak_str = f"{peak_time:.1f}s" if peak_time is not None else "unknown time"
            st.markdown(f"### ⚠️ {label} Detected at {peak_str} — _{recommendations[label]}_")
            st.markdown(f"Confidence Score: **{confidence:.1f}%**")
            fig, ax = plt.subplots()
            if label in ["Chain Slip", "Micro Slip", "Short-Time Slip", "Long-Time Slip"]:
                ax.plot(time_series, df.get("Actual Gear Ratio"), label="Actual Gear Ratio")
            elif label == "Forward Clutch Slip":
                ax.plot(time_series, df.get("Secondary Rev Speed"), label="Secondary RPM")
                ax.plot(time_series, df.get("Front Wheel Speed.1"), label="Front Wheel Speed (RPM)")
            elif label in ["Lock-Up Judder", "Torque Converter Judder"]:
                ax.plot(time_series, df.get("Primary Rev Speed"), label="Primary RPM")
                ax.plot(time_series, df.get("Secondary Rev Speed"), label="Secondary RPM")
            ax.set_title(f"{label} - Sensor Debug")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Sensor Value")
            ax.legend()
            st.pyplot(fig)
        else:
            st.markdown(f"✅ **{label}**: Not Detected")

    st.divider()
    st.markdown("🔁 [TSB 16-132-20R Reference](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226904-0001.pdf)")