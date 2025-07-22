import streamlit as st
import pandas as pd

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("CVT Doctor Pro")
st.markdown("Automated Subaru CVT TSB Diagnostics")

# --- File uploader ---
uploaded_file = st.file_uploader("Upload Subaru SSM4/BtSsm CSV file", type=["csv"])
cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

# --- Safe float conversion ---
def safe_float(val):
    try:
        return float(str(val).replace(',', '').strip())
    except:
        return None

# --- CSV loader ---
def load_csv(file):
    try:
        return pd.read_csv(file, skiprows=8, encoding="utf-8", on_bad_lines="skip")
    except:
        return pd.read_csv(file, skiprows=8, encoding="ISO-8859-1", on_bad_lines="skip")

# --- Detection helpers ---
def has_flow_mismatch(series1, series2, window=5, threshold=0.9):
    corr = series1.rolling(window).corr(series2)
    mismatch = (corr < threshold).sum()
    return mismatch > 5

def has_fluctuations(series, window=5, threshold=50):
    diff = series.diff().rolling(window).std()
    return (diff > threshold).sum() > 5

def stable_throttle(throttle, min_angle=10):
    return throttle > min_angle

# --- TSB Diagnostic Functions ---

def detect_chain_slip(df):
    try:
        ratio = df["Actual Gear Ratio"].apply(safe_float)
        primary = df["Primary Rev Speed"].apply(safe_float)
        secondary = df["Secondary Rev Speed"].apply(safe_float)
        throttle = df["Throttle Opening Angle"].apply(safe_float)
        cond = (ratio.notnull()) & (primary.notnull()) & (secondary.notnull()) & (throttle > 10)
        if cond.sum() < 30:
            return False
        deviation = (primary / secondary - ratio).abs()
        return (deviation > 0.2).sum() > 10
    except:
        return False

def detect_micro_slip(df):
    return detect_chain_slip(df)

def detect_short_slip(df):
    return detect_chain_slip(df)

def detect_long_slip(df):
    return detect_chain_slip(df)

def detect_forward_clutch_slip(df):
    if cvt_type != "TR690":
        return False
    try:
        sec = df["Secondary Rev Speed"].apply(safe_float)
        front = df["Front Wheel Speed (RPM)"].apply(safe_float)
        throttle = df["Throttle Opening Angle"].apply(safe_float)
        if sec.notnull().sum() < 30 or front.notnull().sum() < 30:
            return False
        cond = (throttle > 10) & sec.notnull() & front.notnull()
        return has_flow_mismatch(sec[cond], front[cond])
    except:
        return False

def detect_torque_converter_judder(df):
    try:
        primary = df["Primary Rev Speed"].apply(safe_float)
        secondary = df["Secondary Rev Speed"].apply(safe_float)
        throttle = df["Throttle Opening Angle"].apply(safe_float)
        cond = (throttle > 10) & primary.notnull() & secondary.notnull()
        return has_fluctuations(primary[cond] - secondary[cond])
    except:
        return False

def detect_lockup_judder(df):
    try:
        primary = df["Primary Rev Speed"].apply(safe_float)
        secondary = df["Secondary Rev Speed"].apply(safe_float)
        duty = df["Lock Up Duty Ratio"].apply(safe_float)
        throttle = df["Throttle Opening Angle"].apply(safe_float)
        cond = (duty > 70) & (throttle > 10) & primary.notnull() & secondary.notnull()
        return has_fluctuations(primary[cond] - secondary[cond])
    except:
        return False

# --- Aggregator ---
def analyze_all(df):
    return {
        "Chain Slip": detect_chain_slip(df),
        "Micro Slip": detect_micro_slip(df),
        "Short Slip": detect_short_slip(df),
        "Long Slip": detect_long_slip(df),
        "Forward Clutch Slip": detect_forward_clutch_slip(df),
        "Torque Converter Judder": detect_torque_converter_judder(df),
        "Lock-Up Judder": detect_lockup_judder(df)
    }

# --- Repair Recommendations ---
def get_recommendations(detections):
    recs = []
    if detections["Chain Slip"]:
        recs.append("⚠️ Check belt/pulley wear. May require CVT overhaul.")
    if detections["Micro Slip"] or detections["Short Slip"] or detections["Long Slip"]:
        recs.append("⚠️ Inspect line pressure solenoids and clutch packs.")
    if detections["Forward Clutch Slip"]:
        recs.append("⚠️ Verify TR690 forward clutch operation. Check valve body.")
    if detections["Torque Converter Judder"]:
        recs.append("⚠️ Replace torque converter. Flush fluid.")
    if detections["Lock-Up Judder"]:
        recs.append("⚠️ Inspect lock-up control solenoid. Update CVT firmware.")
    return recs

# --- Main logic ---
if uploaded_file:
    df = load_csv(uploaded_file)
    if df is not None and not df.empty:
        st.success("CSV loaded successfully.")
        detections = analyze_all(df)

        st.header("📊 Diagnostic Summary")
        for issue, found in detections.items():
            st.write(f"**{issue}:** {'✅ Not Detected' if not found else '❌ Detected'}")

        recommendations = get_recommendations(detections)
        if recommendations:
            st.header("🔧 Repair Recommendations")
            for r in recommendations:
                st.write(r)
    else:
        st.error("Failed to parse CSV file. Check format.")