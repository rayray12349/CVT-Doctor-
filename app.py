# Save as app.py

import streamlit as st
import pandas as pd

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("CVT Doctor Pro – Subaru CVT TSB Diagnostic Tool")

uploaded_file = st.file_uploader("Upload Subaru CVT CSV Log", type=["csv"])
cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

def safe_float(series):
    return pd.to_numeric(series, errors='coerce').fillna(0)

# Chain Slip
def detect_chain_slip(df):
    events = []
    if all(col in df.columns for col in ['Engine Speed', 'Primary Rev Speed', 'Throttle Opening Angle']):
        engine = safe_float(df['Engine Speed'])
        primary = safe_float(df['Primary Rev Speed'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (engine - primary).abs()
        start = None
        for i in range(len(df)):
            if throttle.iloc[i] > 10 and engine.iloc[i] > 1200 and diff.iloc[i] > 300:
                if start is None: start = i
            else:
                if start is not None and i - start >= 10:
                    events.append(f"Chain Slip rows {start}-{i}")
                start = None
        if start is not None and len(df) - start >= 10:
            events.append(f"Chain Slip rows {start}-{len(df)-1}")
    return events

# Micro Slip
def detect_micro_slip(df):
    events = []
    if all(k in df.columns for k in ['Actual Gear Ratio', 'Primary Rev Speed', 'Secondary Rev Speed', 'Throttle Opening Angle']):
        expected = safe_float(df['Primary Rev Speed']) / safe_float(df['Secondary Rev Speed']).replace(0, 1)
        actual = safe_float(df['Actual Gear Ratio'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (expected - actual).abs()
        start = None
        for i in range(len(diff)):
            if throttle.iloc[i] > 10 and diff.iloc[i] > 0.1:
                if start is None: start = i
            else:
                if start is not None and i - start >= 10:
                    events.append(f"Micro Slip rows {start}-{i}")
                start = None
        if start is not None and len(diff) - start >= 10:
            events.append(f"Micro Slip rows {start}-{len(df)-1}")
    return events

# Short Slip
def detect_short_slip(df):
    events = []
    if all(col in df.columns for col in ['Engine Speed', 'Secondary Rev Speed', 'Throttle Opening Angle']):
        engine = safe_float(df['Engine Speed'])
        secondary = safe_float(df['Secondary Rev Speed'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (engine - secondary).abs()
        start = None
        for i in range(len(df)):
            if throttle.iloc[i] > 10 and diff.iloc[i] > 300:
                if start is None: start = i
            else:
                if start is not None and i - start >= 10:
                    events.append(f"Short Slip rows {start}-{i}")
                start = None
        if start is not None and len(df) - start >= 10:
            events.append(f"Short Slip rows {start}-{len(df)-1}")
    return events

# Long Slip
def detect_long_slip(df):
    events = []
    if all(col in df.columns for col in ['Engine Speed', 'Primary Rev Speed', 'Throttle Opening Angle']):
        engine = safe_float(df['Engine Speed'])
        primary = safe_float(df['Primary Rev Speed'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = (engine - primary).abs()
        start = None
        for i in range(len(df)):
            if throttle.iloc[i] > 10 and diff.iloc[i] > 300:
                if start is None: start = i
            else:
                if start is not None and i - start >= 20:
                    events.append(f"Long Slip rows {start}-{i}")
                start = None
        if start is not None and len(df) - start >= 20:
            events.append(f"Long Slip rows {start}-{len(df)-1}")
    return events

# Forward Clutch Slip (TR690 only)
def detect_forward_clutch_slip(df):
    events = []
    if cvt_type == "TR690" and all(col in df.columns for col in ['Engine Speed', 'Front Wheel Speed.1', 'Throttle Opening Angle']):
        engine = safe_float(df['Engine Speed'])
        front = safe_float(df['Front Wheel Speed.1'])
        throttle = safe_float(df['Throttle Opening Angle'])
        diff = engine - front
        start = None
        for i in range(len(df)):
            if throttle.iloc[i] > 10 and diff.iloc[i] > 300:
                if start is None: start = i
            else:
                if start is not None and i - start >= 10:
                    events.append(f"Forward Clutch Slip rows {start}-{i}")
                start = None
        if start is not None and len(df) - start >= 10:
            events.append(f"Forward Clutch Slip rows {start}-{len(df)-1}")
    return events

# Lockup Judder
def detect_lockup_judder(df):
    events = []
    if all(col in df.columns for col in ['Engine Speed', 'Lock Up Duty Ratio']):
        rpm = safe_float(df['Engine Speed'])
        duty = safe_float(df['Lock Up Duty Ratio'])
        for i in range(20, len(rpm)-20):
            if 1000 < rpm.iloc[i] < 2500 and 70 < duty.iloc[i] < 100:
                std = rpm.iloc[i-20:i+20].std()
                if std > 150:
                    events.append(f"Lockup Judder at row {i} (std={std:.2f})")
    return events

# Valve Body Irregularity
def detect_valve_body_irregularity(df):
    events = []
    if all(col in df.columns for col in ['Lin. Sol. Set Current', 'Lin. Sol. Actual Current']):
        set_c = safe_float(df['Lin. Sol. Set Current'])
        act_c = safe_float(df['Lin. Sol. Actual Current'])
        diff = (set_c - act_c).abs()
        for i in range(len(df)):
            if diff.iloc[i] > 0.3:
                events.append(f"Valve Body Irregularity at row {i} (diff={diff.iloc[i]:.2f})")
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
        st.success("✅ CSV loaded")
        st.code(df.columns.tolist())

        events = aggregate_all_tsb(df)
        if events:
            st.warning(f"{len(events)} CVT concern(s) found:")
            for e in events:
                st.text(e)
        else:
            st.success("No TSB conditions detected.")
    except Exception as e:
        st.error(f"File load error: {e}")