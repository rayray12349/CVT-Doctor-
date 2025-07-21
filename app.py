import streamlit as st
import pandas as pd

st.title("CVT Doctor Pro – Subaru CVT TSB Diagnostic Tool")

uploaded_file = st.file_uploader("Upload Subaru CVT CSV Log", type=["csv"])
cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

def detect_chain_slip(df):
    events = []
    if 'Engine Speed' in df.columns and 'Primary Rev Speed' in df.columns:
        rpm_diff = (df['Engine Speed'].astype(float) - df['Primary Rev Speed'].astype(float)).abs()
        for i in range(len(rpm_diff)):
            if rpm_diff.iloc[i] > 300:
                events.append(f"Chain Slip Detected at row {i} (RPM diff: {rpm_diff.iloc[i]})")
    return events

def detect_micro_slip(df):
    events = []
    if 'Actual Gear Ratio' in df.columns and 'Primary Rev Speed' in df.columns and 'Secondary Rev Speed' in df.columns:
        expected_ratio = df['Primary Rev Speed'].astype(float) / df['Secondary Rev Speed'].astype(float).replace(0, 1)
        actual_ratio = df['Actual Gear Ratio'].astype(float)
        diff = (expected_ratio - actual_ratio).abs()
        for i in range(len(diff)):
            if diff.iloc[i] > 0.1:
                events.append(f"Micro Slip Detected at row {i} (Gear Ratio diff: {diff.iloc[i]})")
    return events

def detect_short_slip(df):
    events = []
    if 'Engine Speed' in df.columns and 'Secondary Rev Speed' in df.columns:
        diff = (df['Engine Speed'].astype(float) - df['Secondary Rev Speed'].astype(float)).abs()
        for i in range(len(diff)):
            if diff.iloc[i] > 300:
                events.append(f"Short Slip Detected at row {i} (RPM diff: {diff.iloc[i]})")
    return events

def detect_long_slip(df):
    events = []
    if 'Engine Speed' in df.columns and 'Primary Rev Speed' in df.columns:
        diff = (df['Engine Speed'].astype(float) - df['Primary Rev Speed'].astype(float)).abs()
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
        diff = df['Engine Speed'].astype(float) - df['Front Wheel Speed.1'].astype(float)
        for i in range(len(diff)):
            if diff.iloc[i] > 300:
                events.append(f"Forward Clutch Slip Detected at row {i} (RPM diff: {diff.iloc[i]})")
    return events

def detect_lockup_judder(df):
    events = []
    if 'Engine Speed' in df.columns and 'Lock Up Duty Ratio' in df.columns:
        rpm = df['Engine Speed'].astype(float)
        duty = df['Lock Up Duty Ratio'].astype(float)
        for i in range(20, len(rpm) - 20):
            std = rpm.iloc[i-20:i+20].std()
            if 1000 < rpm.iloc[i] < 2500 and std > 150 and 70 < duty.iloc[i] < 100:
                events.append(f"Lockup Judder Detected at row {i} (StdDev: {std})")
    return events

def detect_valve_body_irregularity(df):
    events = []
    if 'Lin. Sol. Set Current' in df.columns and 'Lin. Sol. Actual Current' in df.columns:
        set_current = df['Lin. Sol. Set Current'].astype(float)
        actual_current = df['Lin. Sol. Actual Current'].astype(float)
        diff = (set_current - actual_current).abs()
        for i in range(len(diff)):
            if diff.iloc[i] > 0.3:
                events.append(f"Valve Body Irregularity Detected at row {i} (Current diff: {diff.iloc[i]})")
    return events

def aggregate_all_tsb(df):
    events = []
    events.extend(detect_chain_slip(df))
    events.extend(detect_micro_slip(df))
    events.extend(detect_short_slip(df))
    events.extend(detect_long_slip(df))
    events.extend(detect_forward_clutch_slip(df))
    events.extend(detect_lockup_judder(df))
    events.extend(detect_valve_body_irregularity(df))
    return events

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, encoding='ISO-8859-1', skiprows=8)
        st.success("CSV file loaded successfully.")
        st.write("Preview of data:", df.head())
        issues = aggregate_all_tsb(df)
        if issues:
            st.warning("⚠️ Detected CVT Concerns:")
            for issue in issues:
                st.text(issue)
        else:
            st.success("✅ No TSB-related CVT issues detected.")
    except Exception as e:
        st.error(f"Error loading file: {e}")