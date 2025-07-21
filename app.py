import streamlit as st
import pandas as pd

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
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
                events.append(f"Chain Slip at row {i} (diff: {rpm_diff.iloc[i]:.2f})")
    return events

def detect_micro_slip(df):
    events = []
    if all(k in df.columns for k in ['Actual Gear Ratio', 'Primary Rev Speed', 'Secondary Rev Speed']):
        expected = safe_float(df['Primary Rev Speed']) / safe_float(df['Secondary Rev Speed']).replace(0, 1)
        actual = safe_float(df['Actual Gear Ratio'])
        diff = (expected - actual).abs()
        for i in range(len(diff)):
            if diff.iloc[i] > 0.1:
                events.append(f"Micro Slip at row {i} (ratio diff: {diff.iloc[i]:.2f})")
    return events

def detect_short_slip(df):
    events = []
    if 'Engine Speed' in df.columns and 'Secondary Rev Speed' in df.columns:
        diff = (safe_float(df['Engine Speed']) - safe_float(df['Secondary Rev Speed'])).abs()
        for i in range(len(diff)):
            if diff.iloc[i] > 300:
                events.append(f"Short Slip at row {i} (RPM diff: {diff.iloc[i]:.2f})")
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
                events.append(f"Long Slip from row {i-20} to {i}")
                count = 0
    return events

def detect_forward_clutch_slip(df):
    events = []
    if cvt_type == "TR690" and 'Engine Speed' in df.columns and 'Front Wheel Speed.1' in df.columns:
        diff = safe_float(df['Engine Speed']) - safe_float(df['Front Wheel Speed.1'])
        for i in range(len(diff)):
            if diff.iloc[i] > 300:
                events.append(f"Forward Clutch Slip at row {i} (diff: {diff.iloc[i]:.2f})")
    return events

def detect_lockup_judder(df):
    events = []
    if 'Engine Speed' in df.columns and 'Lock Up Duty Ratio' in df.columns:
        rpm = safe_float(df['Engine Speed'])
        duty = safe_float(df['Lock Up Duty Ratio'])
        for i in range(20, len(rpm)-20):
            std = rpm.iloc[i-20:i+20].std()
            if 1000 < rpm.iloc[i] < 2500 and std > 150 and 70 < duty.iloc[i] < 100:
                events.append(f"Lockup Judder at row {i} (std dev: {std:.2f})")
    return events

def detect_valve_body_irregularity(df):
    events = []
    if 'Lin. Sol. Set Current' in df.columns and 'Lin. Sol. Actual Current' in df.columns:
        diff = (safe_float(df['Lin. Sol. Set Current']) - safe_float(df['Lin. Sol. Actual Current'])).abs()
        for i in range(len(diff)):
            if diff.iloc[i] > 0.3:
                events.append(f"Valve Body Current Irregularity at row {i} (diff: {diff.iloc[i]:.2f})")
    return events

def aggregate_all_tsb(df):
    return (
        detect_chain_slip(df)
        + detect_micro_slip(df)
        + detect_short_slip(df)
        + detect_long_slip(df)
        + detect_forward_clutch_slip(df)
        + detect_lockup_judder(df)
        + detect_valve_body_irregularity(df)
    )

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, encoding="ISO-8859-1", skiprows=8)
        st.success("CSV loaded. Columns found:")
        st.code(df.columns.tolist())

        all_events = aggregate_all_tsb(df)
        if all_events:
            st.warning(f"{len(all_events)} TSB issue(s) detected:")
            for e in all_events:
                st.text(e)
        else:
            st.success("✅ No CVT TSB concerns detected.")
    except Exception as e:
        st.error(f"File load error: {e}")