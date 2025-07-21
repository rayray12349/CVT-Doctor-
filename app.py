import streamlit as st
import pandas as pd

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro – Subaru TSB Diagnostic Tool")

uploaded_file = st.file_uploader("📤 Upload Subaru CVT CSV Log", type=["csv"])

# CVT type dropdown for correct PID mapping
cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, skiprows=8, encoding='ISO-8859-1')
    except Exception as e:
        st.error(f"CSV read error: {e}")
        st.stop()

    st.success("✅ File loaded. Columns detected:")
    st.code(", ".join(df.columns))

    # Rename common PIDs based on CVT type
    if cvt_type == "TR690":
        front_wheel_speed_col = "Front Wheel Speed.1 (RPM)"
    else:
        front_wheel_speed_col = None  # TR580 does not use it

    # Define key PID mappings (standardized)
    pid_map = {
        "engine_rpm": "Engine RPM",
        "primary_rpm": "Primary Rev",
        "secondary_rpm": "Secondary Rev",
        "line_pressure": "Line Pressure",
        "gear_ratio": "Gear Ratio",
        "lockup_duty": "Lock Up Duty Ratio",
        "mph": "Vehicle Speed (MPH)",
    }

    results = []

    # Helper: get safe column
    def safe_col(df, col):
        return df[col] if col in df.columns else None

    # Judder detection logic (torque converter)
    def detect_torque_converter_judder(df):
        engine_rpm = safe_col(df, pid_map["engine_rpm"])
        mph = safe_col(df, pid_map["mph"])
        if engine_rpm is None or mph is None:
            return "❌ Error: Missing 'Engine RPM' or 'Vehicle Speed (MPH)'"
        judder_events = []
        for i in range(2, len(df)):
            if 5 < mph.iloc[i] < 50:
                delta1 = abs(engine_rpm.iloc[i] - engine_rpm.iloc[i - 1])
                delta2 = abs(engine_rpm.iloc[i - 1] - engine_rpm.iloc[i - 2])
                if delta1 > 200 and delta2 > 200:
                    judder_events.append(i)
        return f"✅ Detected {len(judder_events)} torque converter judder events." if judder_events else "✅ No judder detected."

    # Forward clutch slip detection (TR690 only)
    def detect_forward_clutch_slip(df):
        if cvt_type != "TR690":
            return "ℹ️ Not applicable for TR580."
        rpm_col = safe_col(df, pid_map["engine_rpm"])
        wheels_col = safe_col(df, front_wheel_speed_col)
        if rpm_col is None or wheels_col is None:
            return "❌ Error: Missing RPM or Front Wheel Speed (RPM)"
        slip_events = []
        for i in range(len(df)):
            delta = rpm_col.iloc[i] - wheels_col.iloc[i]
            if delta > 600:
                slip_events.append((i, delta))
        return f"✅ Detected {len(slip_events)} forward clutch slip events." if slip_events else "✅ No forward clutch slip detected."

    # Valve body behavior check (line pressure fluctuation)
    def detect_valve_body_behavior(df):
        pressure = safe_col(df, pid_map["line_pressure"])
        if pressure is None:
            return "❌ Error: Missing 'Line Pressure'"
        abnormal = any(abs(pressure.diff().fillna(0)) > 100)
        return "✅ Abnormal valve body behavior detected." if abnormal else "✅ No valve body issues detected."

    # Lock-up clutch slip detection
    def detect_lockup_clutch(df):
        duty = safe_col(df, pid_map["lockup_duty"])
        if duty is None:
            return "❌ Error: Missing 'Lock Up Duty Ratio'"
        spikes = (duty.diff().fillna(0).abs() > 15).sum()
        return f"✅ {spikes} potential lock-up clutch anomalies." if spikes else "✅ No lock-up clutch anomalies."

    # Run all diagnostics
    st.subheader("📋 Diagnostic Results")
    results.append(detect_torque_converter_judder(df))
    results.append(detect_forward_clutch_slip(df))
    results.append(detect_valve_body_behavior(df))
    results.append(detect_lockup_clutch(df))

    for r in results:
        st.markdown(f"- {r}")