import streamlit as st
import pandas as pd

st.title("CVT Doctor Pro – Subaru CVT TSB Diagnostic Tool")

uploaded_file = st.file_uploader("Upload Subaru CVT CSV Log", type=["csv"])
cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

def safe_float(series):
    return pd.to_numeric(series, errors='coerce').fillna(0)

def detect_chain_slip(df):
    events = []
    if 'Engine Speed' in df.columns and 'Primary Rev Speed' in df.columns:
        rpm_diff = (safe_float(df['Engine Speed']) - safe_float(df['Primary Rev Speed'])).abs()
        for i in range(len(rpm_diff)):
            if rpm_diff.iloc[i] > 300:
                events.append(f"Chain Slip Detected at row {i} (RPM diff: {rpm_diff.iloc[i]:.2f})")
    return events

def detect_micro_slip(df):
    events = []
    if all(col in df.columns for col in ['Actual Gear Ratio', 'Primary Rev Speed', 'Secondary Rev Speed']):
        expected_ratio = safe_float(df['Primary Rev Speed']) / safe_float(df['Secondary Rev Speed']).replace(0, 1)
        actual_ratio = safe_float(df['Actual Gear Ratio'])
        diff = (expected_ratio - actual_ratio).abs()
        for i in range(len(diff)):
            if diff.iloc[i] > 0.1:
                events.append(f"Micro Slip Detected at row {i} (Gear Ratio diff: {diff.iloc[i]:.2f})")
    return events

def detect_short_slip(df):
    events = []
    if 'Engine Speed' in df.columns and 'Secondary Rev Speed' in df.columns:
        diff = (safe_float(df['Engine Speed']) - safe_float(df['Secondary Rev Speed'])).abs()
        for i in range(len(diff)):
            if diff.iloc[i] > 300:
                events.append(f"Short Slip Detected at row {i} (RPM diff: {diff.iloc[i]:.2f})")
    return events

def detect_long_slip(df):
    events = []
    if 'Engine Speed' in df.columns and 'Primary Rev Speed' in df.columns:
        diff = (safe_float(df['Engine Speed']) - safe_float(df['Primary Rev Speed'])).abs()
        count = 0
        for i in range(len(diff)):
            if diff.iloc[i] > 300:
                count += 1
            else:
                count = 0
            if count > 20:
                events.append(f"Long Slip Detected starting at row {i-20}")
                count = 0
    return events

def detect_forward_clutch_slip(df):
    events = []
    if cvt_type == "TR690" and 'Engine Speed' in df.columns and 'Front Wheel Speed.1' in df.columns:
        diff = safe_float(df['Engine Speed']) - safe_float(df['Front Wheel Speed.1'])
        for i in range(len(diff)):
            if diff.iloc[i] > 300:
                events.append(f"Forward Clutch Slip Detected at row {i} (RPM diff: {diff.iloc[i]:.2f})")
    return events

def detect_lockup_judder(df):
    events = []
    if 'Engine Speed' in df.columns and 'Lock Up Duty Ratio' in df.columns:
        rpm = safe_float(df['Engine Speed'])
        duty = safe_float(df['Lock Up Duty Ratio'])
        for i in range(20, len(rpm) - 20):
            std = rpm.iloc[i-20:i+20].std()
            if 1000 < rpm.iloc[i] < 2500 and std > 150 and 70 < duty.iloc[i] < 100:
                events.append(f"Lockup Judder Detected at row {i} (StdDev: {std:.2f})")
    return events

def detect_valve_body_irregularity(df):
    events = []
    if 'Lin. Sol. Set Current' in df.columns and 'Lin. Sol. Actual Current' in df.columns:
        diff = (safe_float(df['Lin. Sol. Set Current']) - safe_float(df['Lin. Sol. Actual Current'])).abs()
        for i in range(len(diff)):
            if diff.iloc[i] > 0.3:
                events.append(f"Valve Body Irregularity Detected at row {i} (Current diff: {diff.iloc[i]:.2f})")
    return events

def aggregate_all_tsb(df):
    return (
        detect_chain_slip(df) +
        detect_micro_slip(df) +
        detect_short_slip(df) +
        detect_long_slip(df) +
        detect_forward_clutch_slip(df) +
        detect_lockup_judder(df) +
        detect_valve_body_irregularity(df)
    )

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, encoding='ISO-8859-1', skiprows=8)
        st.success("CSV file loaded successfully.")
        st.write("Detected Columns:", df.columns.tolist())
        st.write(df.head())

        issues = aggregate_all_tsb(df)
        if issues:
            st.warning(f"⚠️ {len(issues)} CVT Issue(s) Detected:")
            for issue in issues:
                st.text(issue)
        else:
            st.success("✅ No TSB-related CVT issues detected.")
    except Exception as e:
        st.error(f"Error loading file: {e}")