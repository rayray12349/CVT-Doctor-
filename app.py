# app.py – CVT Doctor Pro (TSB Edition)

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
        front = safe_float(df['Front Wheel Speed.1'])  # RPM version
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
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (set_current - actual_current).abs()
        flags = (diff >= 0.36) & (throttle > 10)
        return flags.sum() >= 5
    except:
        return False

def run_all_detections(df):
    return {
        "Chain Slip": detect_chain_slip(df),
        "Micro Slip": detect_micro_slip(df),
        "Short Slip": detect_short_slip(df),
        "Long Slip": detect_long_slip(df),
        "Forward Clutch Slip": detect_forward_clutch_slip(df),
        "Lockup Judder": detect_lockup_judder(df),
        "Valve Body Irregularity": detect_valve_body_irregularity(df)
    }

def get_recommendation(issue):
    recs = {
        "Chain Slip": "Check CVT belt condition and primary pulley wear. Inspect transmission case and replace CVT if confirmed.",
        "Micro Slip": "Update TCM software. If concern persists, inspect primary and secondary pulley surfaces.",
        "Short Slip": "Inspect pressure control solenoids and valve body. Replace valve body if no debris is found.",
        "Long Slip": "Check for clutch dragging or low line pressure. Valve body overhaul may be required.",
        "Forward Clutch Slip": "Check forward clutch pressure. TR690 may require drum, plate, or piston inspection.",
        "Lockup Judder": "Flush CVT fluid. If judder returns, inspect torque converter and lock-up control valve.",
        "Valve Body Irregularity": "Inspect solenoid function and electrical connections. Replace valve body if set/actual current mismatch is verified."
    }
    return recs.get(issue, "")

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, encoding="ISO-8859-1", skiprows=8)
        st.success("✅ CSV loaded successfully")

        results = run_all_detections(df)
        st.subheader("📋 TSB Detection Summary")

        for issue, detected in results.items():
            if detected:
                st.error(f"{issue}: Detected")
                st.info(f"🛠 Recommendation: {get_recommendation(issue)}")
            else:
                st.success(f"{issue}: Not Detected")

    except Exception as e:
        st.error(f"File load or parse error: {e}")