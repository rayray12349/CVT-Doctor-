# CVT Doctor Pro – TSB-Aligned Edition
import streamlit as st
import pandas as pd

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("CVT Doctor Pro – Subaru CVT TSB Analyzer")

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
        return ((throttle > 10) & (rpm > 1200) & (diff > 300)).sum() >= 10
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
        return ((throttle > 10) & (diff > 0.1)).sum() >= 10
    except:
        return False

def detect_short_slip(df):
    try:
        rpm = safe_float(df['Engine Speed'])
        sec = safe_float(df['Secondary Rev Speed'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (rpm - sec).abs()
        return ((throttle > 10) & (diff > 300)).sum() >= 10
    except:
        return False

def detect_long_slip(df):
    try:
        rpm = safe_float(df['Engine Speed'])
        pri = safe_float(df['Primary Rev Speed'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (rpm - pri).abs()
        return ((throttle > 10) & (diff > 300)).sum() >= 20
    except:
        return False

def detect_forward_clutch_slip(df):
    try:
        if cvt_type != "TR690":
            return False
        rpm = safe_float(df['Engine Speed'])
        front = safe_float(df['Front Wheel Speed.1'])  # TR690 front wheel speed in RPM
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = rpm - front
        return ((throttle > 10) & (diff > 300)).sum() >= 10
    except:
        return False

def detect_lockup_judder(df):
    try:
        primary = safe_float(df['Primary Rev Speed'])
        secondary = safe_float(df['Secondary Rev Speed'])
        throttle = safe_float(df['Throttle Opening Angle'])

        for i in range(30, len(df) - 30):
            if 1000 < primary.iloc[i] < 2500 and throttle.iloc[i] > 10:
                segment_std = (primary.iloc[i-15:i+15] - secondary.iloc[i-15:i+15]).std()
                if segment_std > 100:
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
        return ((diff >= 0.36) & (throttle > 10)).sum() >= 5
    except:
        return False

def get_recommendation(issue):
    recs = {
        "Chain Slip": "Inspect CVT belt and pulleys. Replace CVT if slipping confirmed.",
        "Micro Slip": "Update TCM. Inspect gear ratio sensors if symptoms persist.",
        "Short Slip": "Check pressure solenoids and fluid condition. Consider valve body.",
        "Long Slip": "Check for low pressure or damaged clutches. Overhaul may be needed.",
        "Forward Clutch Slip": "Inspect forward clutch pressure (TR690). Internal clutch wear possible.",
        "Lockup Judder": "Flush fluid. If persistent, inspect torque converter and lock-up system.",
        "Valve Body Irregularity": "Check solenoid response and control signals. Replace valve body if confirmed."
    }
    return recs.get(issue, "No recommendation available.")

def run_all_detections(df):
    return {
        "Chain Slip": detect_chain_slip(df),
        "Micro Slip": detect_micro_slip(df),
        "Short Slip": detect_short_slip(df),
        "Long Slip": detect_long_slip(df),
        "Forward Clutch Slip": detect_forward_clutch_slip(df),
        "Lockup Judder": detect_lockup_judder(df),
        "Valve Body Irregularity": detect_valve_body_irregularity(df),
    }

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, encoding="ISO-8859-1", skiprows=8)
        st.success("✅ CSV loaded successfully.")

        results = run_all_detections(df)
        st.subheader("📋 TSB Condition Summary")

        for issue, detected in results.items():
            if detected:
                st.error(f"{issue}: Detected")
                st.info(f"🛠 Recommendation: {get_recommendation(issue)}")
            else:
                st.success(f"{issue}: Not Detected")

    except Exception as e:
        st.error(f"❌ Error loading file: {e}")