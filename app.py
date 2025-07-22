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
    has_secondary = 'Secondary Rev Speed' in df.columns
    has_front_wheel_speed = 'Front Wheel Speed' in df.columns
    return has_secondary and has_front_wheel_speed

def get_throttle(df):
    throttle = df.get('Accel. Opening Angle')
    if throttle is None:
        throttle = df.get('Throttle Opening Angle')
    return throttle

def get_speed(df):
    speed = df.get('Front Wheel Speed')
    if speed is None:
        speed = df.get('Vehicle Speed')
    return speed

def is_throttle_stable(throttle_series, threshold=2, window=1.0, rate=10):
    window_size = int(window * rate)
    rolling_std = throttle_series.rolling(window=window_size).std()
    return (rolling_std < threshold)

# ------------------- Detection Logic ------------------- #

def detect_micro_slip(df, rate=10):
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')
    throttle = get_throttle(df)
    speed = get_speed(df)

    if any(v is None for v in [gear, prim, sec, throttle, speed]):
        return False
    if (speed <= 10).all():
        return False

    throttle_mask = throttle > 1.0
    throttle_stable = is_throttle_stable(throttle, rate=rate)

    gear_ptp = gear.rolling(rate).apply(lambda x: x.max() - x.min()) > 0.02
    rpm_ptp = prim.rolling(rate).apply(lambda x: x.max() - x.min()) > 50
    sec_ptp = sec.rolling(rate).apply(lambda x: x.max() - x.min()) > 50

    rpm_fluct = rpm_ptp | sec_ptp
    return (gear_ptp & rpm_fluct & throttle_mask & throttle_stable).any()

def detect_short_time_slip(df):
    gear = df.get('Actual Gear Ratio')
    throttle = get_throttle(df)
    primary = df.get('Primary Rev Speed')
    secondary = df.get('Secondary Rev Speed')
    speed = get_speed(df)

    if any(v is None for v in [gear, throttle, primary, secondary, speed]):
        return False
    if (speed <= 10).all():
        return False

    active = throttle > 1.0
    gear_spike = gear.diff().abs() > 0.1
    rpm_fluct = primary.diff().abs().combine(secondary.diff().abs(), max) > 100
    valid_range = gear > 1.5
    return (gear_spike & rpm_fluct & active & valid_range).any()

def simulate_long_time_slip(df):
    duty = df.get('Primary UP Duty')
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')
    throttle = get_throttle(df)
    speed = get_speed(df)

    if any(v is None for v in [duty, gear, prim, sec, throttle, speed]):
        return False
    if (speed <= 10).all():
        return False

    gear_drop = gear.rolling(5).mean() < gear.mean()
    rpm_fluct = prim.diff().abs().combine(sec.diff().abs(), max) > 50
    slip_condition = (duty > 90) & gear_drop & (throttle > 1.0)
    return (slip_condition & rpm_fluct).any()

def detect_forward_clutch_slip(df, tr690=True):
    if tr690:
        upstream = df.get('Secondary Rev Speed')
        downstream = df.get('Front Wheel Speed')
    else:
        upstream = df.get('Turbine Revolution Speed')
        downstream = df.get('Primary Rev Speed')

    if upstream is None or downstream is None:
        return False

    delta = upstream - downstream
    flow_mismatch = delta.abs().rolling(5).mean() > 75
    return flow_mismatch.any()

def detect_lockup_judder(df):
    throttle = get_throttle(df)
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
    throttle = get_throttle(df)
    speed = get_speed(df)

    if any(v is None for v in [engine, primary, secondary, gear, throttle, speed]):
        return False

    throttle_active = throttle > 1.0
    gear_valid = gear > 1.5
    speed_valid = speed > 10

    rpm_activity = (
        engine.diff().abs().rolling(10).mean() > 10
    ) & (
        primary.diff().abs().rolling(10).mean() > 10
    ) & (
        secondary.diff().abs().rolling(10).mean() > 10
    )

    overlap = (engine.diff().abs() < 30) & (primary.diff().abs() < 30) & (secondary.diff().abs() < 30)
    valid_conditions = throttle_active & gear_valid & speed_valid & rpm_activity

    return (overlap & valid_conditions).rolling(10).sum().max() > 5

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
        "Chain Slip": (detect_chain_slip(df), "Replace CVT & TCM if confirmed via SSM; submit QMR."),
        "Micro Slip": (detect_micro_slip(df), "Replace CVT after confirming persistent fluctuation."),
        "Short-Time Slip": (detect_short_time_slip(df), "Reprogram TCM; replace CVT if slip persists."),
        "Long-Time Slip": (simulate_long_time_slip(df), "Reprogram TCM; monitor for progressive wear. (Simulated — Actual Pulley Ratio not logged)"),
        "Forward Clutch Slip": (detect_forward_clutch_slip(df, tr690=is_tr690), "Reprogram TCM; replace valve body or CVT if needed."),
        "Lock-Up Judder": (detect_lockup_judder(df), "Reprogram TCM; verify ATF condition; replace converter if needed."),
        "Torque Converter Judder": (detect_torque_converter_judder(df), "Replace torque converter; inspect pump & solenoid function."),
    }

    for label, (detected, recommendation) in results.items():
        if detected:
            st.markdown(f"- **{label}**: ⚠️ Detected — **Review Required**  \n  _Recommendation: {recommendation}_")
        else:
            st.markdown(f"- **{label}**: ❌ Not Detected")

    st.divider()
    st.markdown("🔁 [TSB 16-132-20R Reference](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226904-0001.pdf)")