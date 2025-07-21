import streamlit as st
import pandas as pd

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro – Subaru CVT TSB Diagnostic Tool")
st.subheader("Upload a Subaru CVT CSV log file")

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

TSB_THRESHOLDS = {
    "micro": 200,
    "short": (3, 500, 800),
    "long": (10, 500, 800),
    "lockup": 3,
    "forward_clutch_slip": 600,
    "valve_body": 20,
    "tc_judder": 3
}

def clean_csv(file):
    df = pd.read_csv(file, skiprows=9, encoding='ISO-8859-1')
    df = df.dropna(axis=1, how='all')
    return df

def detect_micro_slip(df):
    return [(i, f"Micro Slip: ΔRPM {abs(df['Engine RPM'].iloc[i] - df['Primary RPM'].iloc[i]):.1f} > 200")
            for i in range(len(df))
            if abs(df['Engine RPM'].iloc[i] - df['Primary RPM'].iloc[i]) > TSB_THRESHOLDS["micro"]]

def detect_short_slip(df):
    slips = []
    for i in range(len(df) - 3):
        window = df.iloc[i:i + 3]
        diffs = (window["Engine RPM"] - window["Primary RPM"]).abs()
        if diffs.gt(500).all() and diffs.lt(800).all():
            slips.append((i, "Short Slip: 3-frame slip between 500–800 RPM"))
    return slips

def detect_long_slip(df):
    slips = []
    for i in range(len(df) - 10):
        window = df.iloc[i:i + 10]
        diffs = (window["Engine RPM"] - window["Primary RPM"]).abs()
        if diffs.gt(500).all() and diffs.lt(800).all():
            slips.append((i, "Long Slip: 10-frame slip between 500–800 RPM"))
    return slips

def detect_lockup_slip(df):
    slips = []
    for i in range(len(df) - 3):
        window = df.iloc[i:i + 3]
        if (window["Lock Up Duty Ratio"] > 90).all():
            if (window["Engine RPM"] - window["Primary RPM"]).abs().gt(200).any():
                slips.append((i, "Lockup Slip: RPM slip > 200 with Lock Up Duty > 90%"))
    return slips

def detect_forward_clutch_slip(df, cvt_type):
    if cvt_type != "TR690":
        return []
    if "Front Wheel Speed.1" not in df.columns:
        return [(-1, "❌ Missing PID: Front Wheel Speed.1 (RPM)")]
    slips = []
    for i in range(len(df)):
        try:
            throttle = df["Throttle Opening Angle"].iloc[i]
            gear = df["Actual Gear Ratio"].iloc[i]
            engine_rpm = df["Engine RPM"].iloc[i]
            wheel_rpm = df["Front Wheel Speed.1"].iloc[i]
            if throttle > 1 and gear > 1.5:
                diff = abs(engine_rpm - wheel_rpm)
                if diff > TSB_THRESHOLDS["forward_clutch_slip"]:
                    slips.append((i, f"Forward Clutch Slip: ΔRPM {diff:.1f} > 600"))
        except:
            continue
    return slips

def detect_valve_body_behavior(df):
    diffs = df["Line Pressure"].diff().abs()
    return [(i, f"Valve Body Behavior: Line Pressure jump {diff:.1f} > 20")
            for i, diff in diffs.items() if diff > TSB_THRESHOLDS["valve_body"]]

def detect_torque_converter_judder(df):
    slips = []
    for i in range(len(df) - 3):
        rpm_series = df["Engine RPM"].iloc[i:i+3]
        if rpm_series.diff().abs().gt(100).all():
            slips.append((i, "Torque Converter Judder: RPM fluctuation > 100 over 3 frames"))
    return slips

def aggregate_events(df, cvt_type):
    all_events = []
    detectors = [
        detect_micro_slip,
        detect_short_slip,
        detect_long_slip,
        detect_lockup_slip,
        lambda d: detect_forward_clutch_slip(d, cvt_type),
        detect_valve_body_behavior,
        detect_torque_converter_judder
    ]
    for func in detectors:
        try:
            all_events.extend(func(df))
        except Exception as e:
            all_events.append((-1, f"❌ Error in {func.__name__}: {str(e)}"))
    return sorted(all_events, key=lambda x: x[0])

if uploaded_file:
    df = clean_csv(uploaded_file)
    st.success("✅ File loaded. Columns detected:")
    st.code(", ".join(df.columns.tolist()))

    with st.spinner("Running diagnostics..."):
        results = aggregate_events(df, cvt_type)

    st.subheader("📋 Diagnostic Results")
    if results:
        for i, msg in results:
            st.markdown(f"- **Row {i}**: {msg}")
    else:
        st.success("✅ No abnormal TSB-related behaviors detected.")