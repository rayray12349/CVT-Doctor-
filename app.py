# app.py – CVT Doctor Pro (Summary Mode)

import streamlit as st
import pandas as pd

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("CVT Doctor Pro – Subaru CVT TSB Detection Summary")

uploaded_file = st.file_uploader("Upload Subaru CVT CSV Log", type=["csv"])
cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

def safe_float(series):
    return pd.to_numeric(series, errors='coerce').fillna(0)

def detect_chain_slip(df):
    try:
        rpm = safe_float(df['Engine Speed'])
        pri = safe_float(df['Primary Rev Speed'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (rpm - pri).abs()
        count = ((throttle > 10) & (rpm > 1200) & (diff > 300)).sum()
        return count >= 10
    except:
        return False

def detect_micro_slip(df):
    try:
        actual = safe_float(df['Actual Gear Ratio'])
        primary = safe_float(df['Primary Rev Speed'])
        secondary = safe_float(df['Secondary Rev Speed']).replace(0, 1)
        expected = primary / secondary
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (expected - actual).abs()
        count = ((throttle > 10) & (diff > 0.1)).sum()
        return count >= 10
    except:
        return False

def detect_short_slip(df):
    try:
        rpm = safe_float(df['Engine Speed'])
        sec = safe_float(df['Secondary Rev Speed'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (rpm - sec).abs()
        count = ((throttle > 10) & (diff > 300)).sum()
        return count >= 10
    except:
        return False

def detect_long_slip(df):
    try:
        rpm = safe_float(df['Engine Speed'])
        pri = safe_float(df['Primary Rev Speed'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (rpm - pri).abs()
        count = ((throttle > 10) & (diff > 300)).sum()
        return count >= 20
    except:
        return False

def detect_forward_clutch_slip(df):
    try:
        if cvt_type != "TR690":
            return False
        rpm = safe_float(df['Engine Speed'])
        front = safe_float(df['Front Wheel Speed.1'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = rpm - front
        count = ((throttle > 10) & (diff > 300)).sum()
        return count >= 10
    except:
        return False

def detect_lockup_judder(df):
    try:
        rpm = safe_float(df['Engine Speed'])
        duty = safe_float(df['Lock Up Duty Ratio'])
        for i in range(20, len(rpm)-20):
            if 1000 < rpm.iloc[i] < 2500 and 70 < duty.iloc[i] < 100:
                if rpm.iloc[i-20:i+20].std() > 150:
                    return True
        return False
    except:
        return False

def detect_valve_body_irregularity(df):
    try:
        set_current = safe_float(df['Lin. Sol. Set Current'])
        actual_current = safe_float(df['Lin. Sol. Actual Current'])
        diff = (set_current - actual_current).abs()
        return (diff > 0.3).sum() >= 10
    except:
        return False

def run_all_detections(df):
    results = {
        "Chain Slip": detect_chain_slip(df),
        "Micro Slip": detect_micro_slip(df),
        "Short Slip": detect_short_slip(df),
        "Long Slip": detect_long_slip(df),
        "Forward Clutch Slip": detect_forward_clutch_slip(df),
        "Lockup Judder": detect_lockup_judder(df),
        "Valve Body Irregularity": detect_valve_body_irregularity(df)
    }
    return results

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, encoding="ISO-8859-1", skiprows=8)
        st.success("✅ CSV loaded successfully")

        results = run_all_detections(df)
        st.subheader("📋 TSB Detection Summary")

        for key, value in results.items():
            if value:
                st.error(f"{key}: Detected")
            else:
                st.success(f"{key}: Not Detected")

    except Exception as e:
        st.error(f"File load or parse error: {e}")