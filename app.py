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
    decoded = file.read().decode('utf-8', errors='ignore')  # Fix: Handle encoding issues
    df = pd.read_csv(io.StringIO(decoded), skiprows=8)      # Skip metadata rows
    df = df.applymap(safe_float)                            # Safely convert all values
    return df.dropna(axis=1, how='all')                     # Drop fully empty columns

def detect_tr690(df):
    return 'Front Wheel Speed (RPM)' in df.columns

def is_throttle_stable(throttle_series, threshold=2, window=1.0, rate=10):
    window_size = int(window * rate)
    rolling_std = throttle_series.rolling(window=window_size).std()
    return (rolling_std < threshold)

# ------------------- Detection Logic ------------------- #

def detect_micro_slip(df, rate=10):
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')
    throttle = df.get('Throttle Opening Angle')

    if any(v is None for v in [gear, prim, sec, throttle]):
        return False

    throttle_stable = is_throttle_stable(throttle, rate=rate)
    gear_diff = gear.diff().abs()
    rpm_diff = prim.diff().abs().combine(sec.diff().abs(), max)

    gear_fluct = (gear_diff > 0.02)
    rpm_fluct = (rpm_diff > 50)

    combined = gear_fluct & rpm_fluct & throttle_stable
    freq = combined.rolling(rate).sum()
    return (freq >= 3).any()

def detect_short_time_slip(df):
    gear = df.get('Actual Gear Ratio')
    if gear is None:
        return False
    spikes = gear.diff(periods=1).abs() > 0.1
    return spikes.any()

def detect_long_time_slip(df):
    duty = df.get('Primary UP Duty')
    pulley = df.get('Actual Pulley Ratio')
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')

    if any(v is None for v in [duty, pulley, gear, prim, sec]):
        return False

    slip_condition = (duty > 90) & (pulley.rolling(5).mean() < pulley.mean())
    rpm_fluct = prim.diff().abs().combine(sec.diff().abs(), max) > 50
    return (slip_condition & rpm_fluct).any()

def detect_forward_clutch_slip(df, tr690=True):
    if tr690:
        upstream = df.get('Secondary Rev Speed')
        downstream = df.get('Front Wheel Speed (RPM)')
    else:
        upstream = df.get('Turbine Revolution Speed')
        downstream = df.get('Primary Rev Speed')

    if upstream is None or downstream is None:
        return False

    delta = upstream - downstream
    flow_mismatch = delta.abs().rolling(10).mean() > 100
    return flow_mismatch.any()

def detect_lockup_judder(df):
    throttle = df.get('Throttle Opening Angle')
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')

    if throttle is None or primary is None or secondary is None:
        return False

    rpm_fluct = primary.diff().abs().combine(secondary.diff().abs(), max) > 50
    active = (throttle > 10) & rpm_fluct
    return active.rolling(10).sum().max() > 5

def detect_torque_converter_judder(df):
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')

    if primary is None or secondary is None:
        return False

    fluctuation = primary.diff().abs().combine(secondary.diff().abs(), max) > 50
    return fluctuation.rolling(10).sum().max() > 5

def detect_chain_slip(df):
    engine = df.get('Engine Speed')
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')
    gear = df.get('Actual Gear Ratio')

    if any(v is None for v in [engine, primary, secondary, gear]):
        return False

    overlap = (engine.diff().abs() < 50) & (primary.diff().abs() < 50) & (secondary.diff().abs() < 50)
    return overlap.rolling(10).sum().max() > 5

# ------------------- Streamlit App ------------------- #

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro")
st.markdown("Subaru TR580 & TR690 CVT Diagnostic App — Based on 16-132-20R")

uploaded_file = st.file_uploader("Upload your SSM4/BtSsm CSV file:", type=["csv"])

if uploaded_file:
    df = load_csv(uploaded_file)
    st.success("✅ File loaded and parsed.")

    is_tr690 = detect_tr690(df)
    st.markdown(f"**Detected Transmission:** {'TR690' if is_tr690 else 'TR580'}")

    st.subheader("📊 Diagnostic Summary")

    results = {
        "Chain Slip": detect_chain_slip(df),
        "Micro Slip": detect_micro_slip(df),
        "Short-Time Slip": detect_short_time_slip(df),
        "Long-Time Slip": detect_long_time_slip(df),
        "Forward Clutch Slip": detect_forward_clutch_slip(df, tr690=is_tr690),
        "Lock-Up Judder": detect_lockup_judder(df),
        "Torque Converter Judder": detect_torque_converter_judder(df),
    }

    for label, detected in results.items():
        st.markdown(f"- **{label}**: {'❌ Not Detected' if not detected else '⚠️ Detected — Review Required'}")

    st.divider()

    st.markdown("🔁 [TSB 16-132-20R Reference](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226904-0001.pdf)")