import streamlit as st
import pandas as pd
import numpy as np
import io

# ---------------- Utility Functions ---------------- #

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
    return 'Secondary Rev Speed' in df.columns and 'Front Wheel Speed' in df.columns

def get_throttle(df):
    return df.get('Accel. Opening Angle') or df.get('Throttle Opening Angle')

def get_speed(df):
    return df.get('Front Wheel Speed') or df.get('Vehicle Speed')

def is_throttle_stable(throttle, threshold=2, window=1.0, rate=10):
    rolling_std = throttle.rolling(int(window * rate)).std()
    return rolling_std < threshold

def get_peak_index(series):
    if isinstance(series, pd.Series):
        peak = series[series].rolling(10).sum()
        if not peak.empty and peak.max() > 0:
            return int(peak.idxmax())
    return None

# ---------------- TSB Detection Logic ---------------- #

def detect_micro_slip(df, rate=10):
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')
    throttle = get_throttle(df)
    speed = get_speed(df)
    if any(v is None for v in [gear, prim, sec, throttle, speed]) or (speed <= 10).all():
        return False, None

    throttle_stable = is_throttle_stable(throttle, rate)
    throttle_active = throttle > 1.0
    stable = throttle_stable & throttle_active

    gear_ptp = gear.rolling(rate).apply(lambda x: x.max() - x.min()) > 0.02
    prim_ptp = prim.rolling(rate).apply(lambda x: x.max() - x.min()) > 50
    sec_ptp = sec.rolling(rate).apply(lambda x: x.max() - x.min()) > 50
    rpm_fluct = prim_ptp | sec_ptp

    events = gear_ptp & rpm_fluct & stable
    freq = events.rolling(rate).sum()
    peak = get_peak_index(events)
    return (freq >= 3).any(), peak

def detect_short_time_slip(df):
    gear = df.get('Actual Gear Ratio')
    throttle = get_throttle(df)
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')
    speed = get_speed(df)
    if any(v is None for v in [gear, throttle, primary, secondary, speed]) or (speed <= 10).all():
        return False, None

    gear_spike = gear.diff().abs() > 0.1
    rpm_fluct = primary.diff().abs().combine(secondary.diff().abs(), max) > 100
    active = throttle > 1.0
    valid_range = gear > 1.5
    events = gear_spike & rpm_fluct & active & valid_range
    return events.any(), get_peak_index(events)

def simulate_long_time_slip(df):
    duty = df.get('Primary UP Duty')
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')
    throttle = get_throttle(df)
    speed = get_speed(df)
    if any(v is None for v in [duty, gear, prim, sec, throttle, speed]) or (speed <= 10).all():
        return False, None

    gear_drop = gear.rolling(5).mean() < gear.mean()
    rpm_fluct = prim.diff().abs().combine(sec.diff().abs(), max) > 50
    active = (duty > 90) & gear_drop & (throttle > 1.0)
    events = active & rpm_fluct
    return events.any(), get_peak_index(events)

def detect_forward_clutch_slip(df, tr690=True):
    if tr690:
        upstream = df.get('Secondary Rev Speed')
        downstream = df.get('Front Wheel Speed')
    else:
        upstream = df.get('Turbine Revolution Speed')
        downstream = df.get('Primary Rev Speed')
    if upstream is None or downstream is None:
        return False, None

    delta = upstream - downstream
    mismatch = delta.abs().rolling(5).mean() > 75
    return mismatch.any(), get_peak_index(mismatch)

def detect_lockup_judder(df):
    throttle = get_throttle(df)
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')
    if any(v is None for v in [throttle, primary, secondary]):
        return False, None

    rpm_fluct = primary.diff().abs().combine(secondary.diff().abs(), max) > 50
    events = (throttle > 10) & rpm_fluct
    return events.rolling(10).sum().max() > 5, get_peak_index(events)

def detect_torque_converter_judder(df):
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')
    if primary is None or secondary is None:
        return False, None

    fluct = primary.diff().abs().combine(secondary.diff().abs(), max) > 50
    return fluct.rolling(10).sum().max() > 5, get_peak_index(fluct)

def detect_chain_slip(df):
    engine = df.get('Engine Speed')
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')
    gear = df.get('Actual Gear Ratio')
    throttle = get_throttle(df)
    speed = get_speed(df)
    if any(v is None for v in [engine, primary, secondary, gear, throttle, speed]) or (speed <= 10).all():
        return False, None

    rpm_active = (
        engine.diff().abs().rolling(10).mean() > 10
    ) & (
        primary.diff().abs().rolling(10).mean() > 10
    ) & (
        secondary.diff().abs().rolling(10).mean() > 10
    )

    overlap = (engine.diff().abs() < 30) & (primary.diff().abs() < 30) & (secondary.diff().abs() < 30)
    events = overlap & (throttle > 1.0) & (gear > 1.5) & (speed > 10) & rpm_active
    return events.rolling(10).sum().max() > 5, get_peak_index(events)

# ------------------- Streamlit App ------------------- #

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro")
st.markdown("Subaru TR580 & TR690 CVT Diagnostic App — Based on TSB 16-132-20R")

uploaded_file = st.file_uploader("Upload your SSM4/BtSsm CSV file:", type=["csv"])
if uploaded_file:
    df = load_csv(uploaded_file)
    st.success("✅ File loaded successfully.")

    is_tr690 = detect_tr690(df)
    st.markdown(f"**Detected Transmission:** {'TR690' if is_tr690 else 'TR580'}")

    st.subheader("📊 Diagnostic Summary")

    results = {
        "Chain Slip": (detect_chain_slip(df), "Replace CVT & TCM if confirmed via SSM; submit QMR."),
        "Micro Slip": (detect_micro_slip(df), "Replace CVT after confirming persistent fluctuation."),
        "Short-Time Slip": (detect_short_time_slip(df), "Reprogram TCM; replace CVT if slip persists."),
        "Long-Time Slip": (simulate_long_time_slip(df), "Reprogram TCM; monitor for progressive wear. (Simulated — Actual Pulley Ratio not logged)"),
        "Forward Clutch Slip": (detect_forward_clutch_slip(df, tr690=is_tr690), "Reprogram TCM; replace valve body or CVT if needed."),
        "Lock-Up Judder": (detect_lockup_judder(df), "Reprogram TCM; verify ATF condition; replace converter if needed."),
        "Torque Converter Judder": (detect_torque_converter_judder(df), "Replace torque converter; inspect pump & solenoid function."),
    }

    for label, ((detected, peak), recommendation) in results.items():
        if detected:
            peak_str = f" at row {peak}" if peak is not None else ""
            st.markdown(f"- **{label}**: ⚠️ Detected{peak_str} — _{recommendation}_")
        else:
            st.markdown(f"- **{label}**: ✅ Not Detected")

    st.divider()
    st.markdown("🔁 [TSB 16-132-20R Reference](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226904-0001.pdf)")