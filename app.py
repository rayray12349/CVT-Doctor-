import streamlit as st
import pandas as pd
import numpy as np

st.title("CVT Doctor Pro - Subaru TSB Diagnostic")

uploaded_file = st.file_uploader("Upload Subaru SSM4/BtSsm CSV file", type=["csv"])
cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

def safe_float(val):
    try:
        return float(val)
    except:
        return np.nan

def load_csv(file):
    df = pd.read_csv(file, skiprows=8)
    df = df.applymap(safe_float)
    return df

def is_steady_throttle(throttle, threshold=3):
    return throttle.diff().abs().fillna(0) < threshold

def detect_forward_clutch_slip(df):
    if cvt_type != "TR690" or 'Front Wheel Speed.1 (RPM)' not in df.columns:
        return False
    fws = df['Front Wheel Speed.1 (RPM)'].diff().apply(np.sign)
    sec = df['Secondary Rev Speed'].diff().apply(np.sign)
    throttle = df['Throttle Position (%)']
    mismatch = (fws != sec) & is_steady_throttle(throttle) & (throttle > 10)
    return mismatch.any()

def detect_torque_converter_judder(df):
    p = df['Primary Rev Speed'].diff()
    s = df['Secondary Rev Speed'].diff()
    fluct = ((p - s).abs() > 50) & is_steady_throttle(df['Throttle Position (%)']) & (df['Throttle Position (%)'] > 10)
    return fluct.any()

def detect_micro_slip(df):
    agr = df['Actual Gear Ratio']
    s = df['Secondary Rev Speed']
    p = df['Primary Rev Speed']
    slip = (agr - s / p).abs() > 0.02
    return slip.any()

def detect_short_slip(df):
    agr = df['Actual Gear Ratio']
    s = df['Secondary Rev Speed']
    p = df['Primary Rev Speed']
    slip = (agr - s / p).abs() > 0.05
    return slip.any()

def detect_long_slip(df):
    agr = df['Actual Gear Ratio']
    s = df['Secondary Rev Speed']
    p = df['Primary Rev Speed']
    slip = (agr - s / p).abs() > 0.1
    return slip.any()

def detect_chain_slip(df):
    if 'Engine RPM' not in df.columns or 'Primary RPM' not in df.columns:
        return False
    diff = (df['Engine RPM'] - df['Primary RPM']).abs()
    return (diff > 100).any()

def detect_lockup_judder(df):
    lockup = df['Lock Up Duty Ratio']
    p = df['Primary Rev Speed'].diff()
    s = df['Secondary Rev Speed'].diff()
    rpm_range = (df['Engine RPM'] > 1200) & (df['Engine RPM'] < 2500)
    judder = (p - s).abs() > 50
    return (lockup.between(0.7, 0.95)) & is_steady_throttle(df['Throttle Position (%)']) & rpm_range & judder.any()

def generate_report(df):
    report = {}
    report["Forward Clutch Slip"] = detect_forward_clutch_slip(df)
    report["Torque Converter Judder"] = detect_torque_converter_judder(df)
    report["Micro Slip"] = detect_micro_slip(df)
    report["Short Slip"] = detect_short_slip(df)
    report["Long Slip"] = detect_long_slip(df)
    report["Chain Slip"] = detect_chain_slip(df)
    report["Lock Up Judder"] = detect_lockup_judder(df)
    return report

def repair_recommendations(report):
    recs = []
    if report["Forward Clutch Slip"]:
        recs.append("🔧 Check secondary pulley and valve body. Consider valve body replacement.")
    if report["Torque Converter Judder"]:
        recs.append("🔧 Inspect torque converter. Possible internal judder — replace converter if confirmed.")
    if report["Micro Slip"] or report["Short Slip"] or report["Long Slip"]:
        recs.append("🔧 Check belt/chain condition, pressure solenoids, and fluid degradation.")
    if report["Chain Slip"]:
        recs.append("🔧 Inspect engine/primary pulley relationship. Possible chain stretch.")
    if report["Lock Up Judder"]:
        recs.append("🔧 Verify lockup control circuit. Possible torque converter or solenoid irregularity.")
    return recs

if uploaded_file:
    df = load_csv(uploaded_file)
    report = generate_report(df)
    st.subheader("TSB Diagnostic Summary")
    for key, val in report.items():
        st.write(f"**{key}**: {'✅ Detected' if val else '❌ Not Detected'}")

    recommendations = repair_recommendations(report)
    if recommendations:
        st.subheader("Repair Recommendations")
        for r in recommendations:
            st.write(r)