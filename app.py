import streamlit as st
import pandas as pd

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro – Subaru TSB Diagnostic Tool")

uploaded_file = st.file_uploader("📤 Upload Subaru CVT CSV Log", type=["csv"])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    # Show columns detected
    st.success("✅ File loaded. Columns detected:")
    st.code(", ".join(df.columns))

    # Rename columns based on known Subaru aliases (from generic CSV header)
    column_map = {
        "rpm": "Engine RPM",
        "rpm.1": "Primary RPM",
        "%": "Throttle Opening Angle",
        "°F": "ATF Temp",
        "%.1": "Lock Up Duty Ratio",
        "Unnamed: 13": "Line Pressure",
        "rpm.2": "Front Wheel Speed.1"  # TR690 only
    }
    df.rename(columns={k: v for k, v in column_map.items() if k in df.columns}, inplace=True)

    # Dropdown to select CVT type
    cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])
    front_wheel_pid = "Front Wheel Speed.1" if cvt_type == "TR690" else None

    events = []

    def detect_micro_slip(df):
        if "Engine RPM" in df.columns and "Primary RPM" in df.columns:
            slip = (df["Engine RPM"] - df["Primary RPM"]).abs()
            return [f"{i} - Micro Slip: {val} RPM" for i, val in enumerate(slip) if val > 200]
        else:
            raise ValueError("Missing required PIDs for Micro Slip")

    def detect_short_slip(df):
        if "Engine RPM" in df.columns and "Primary RPM" in df.columns:
            slips = []
            for i in range(len(df) - 3):
                window = (df["Engine RPM"].iloc[i:i+3] - df["Primary RPM"].iloc[i:i+3]).abs()
                if window.gt(500).all() and window.lt(800).all():
                    slips.append(f"{i} - Short Slip: 3-frame slip between 500–800 RPM")
            return slips
        else:
            raise ValueError("Missing required PIDs for Short Slip")

    def detect_long_slip(df):
        if "Engine RPM" in df.columns and "Primary RPM" in df.columns:
            slips = []
            for i in range(len(df) - 6):
                window = (df["Engine RPM"].iloc[i:i+6] - df["Primary RPM"].iloc[i:i+6]).abs()
                if window.gt(500).all():
                    slips.append(f"{i} - Long Slip: 6-frame slip > 500 RPM")
            return slips
        else:
            raise ValueError("Missing required PIDs for Long Slip")

    def detect_lockup_slip(df):
        if "Primary RPM" in df.columns and "Lock Up Duty Ratio" in df.columns and "Engine RPM" in df.columns:
            slip = df["Lock Up Duty Ratio"].rolling(3).mean() > 80
            rpm_delta = (df["Engine RPM"] - df["Primary RPM"]).abs()
            return [f"{i} - Lockup Slip: {val} RPM with Lockup > 80%" for i, val in enumerate(rpm_delta) if slip.iloc[i] and val > 300]
        else:
            raise ValueError("Missing required PIDs for Lockup Slip")

    def detect_forward_clutch_slip(df):
        if "Engine RPM" in df.columns and "Primary RPM" in df.columns and (front_wheel_pid in df.columns if front_wheel_pid else True):
            throttle = df["Throttle Opening Angle"] if "Throttle Opening Angle" in df.columns else pd.Series([2] * len(df))
            rpm_delta = (df["Engine RPM"] - df["Primary RPM"]).abs()
            speed = df[front_wheel_pid] if front_wheel_pid and front_wheel_pid in df.columns else pd.Series([3] * len(df))
            return [f"{i} - Forward Clutch Slip: RPM delta exceeds 600 ({rpm_delta.iloc[i]} vs throttle {throttle.iloc[i]})" for i in range(len(rpm_delta)) if rpm_delta.iloc[i] > 600 and throttle.iloc[i] > 1 and speed.iloc[i] > 2]
        else:
            raise ValueError("Missing required PIDs for Forward Clutch Slip")

    def detect_valve_body_behavior(df):
        if "Line Pressure" in df.columns and "Throttle Opening Angle" in df.columns:
            anomalies = df["Line Pressure"].rolling(5).std() > 30
            return [f"{i} - Valve Body Anomaly: High pressure variance" for i in anomalies[anomalies].index]
        else:
            raise ValueError("Missing required PIDs for Valve Body Behavior")

    def detect_torque_converter_judder(df):
        if "Engine RPM" in df.columns:
            judder = df["Engine RPM"].diff().abs().rolling(5).std() > 50
            return [f"{i} - Torque Converter Judder: RPM instability" for i in judder[judder].index]
        else:
            raise ValueError("Missing required PIDs for Torque Converter Judder")

    diagnostic_functions = [
        detect_micro_slip,
        detect_short_slip,
        detect_long_slip,
        detect_lockup_slip,
        detect_forward_clutch_slip,
        detect_valve_body_behavior,
        detect_torque_converter_judder
    ]

    st.markdown("## 📋 Diagnostic Results")
    for func in diagnostic_functions:
        try:
            result = func(df)
            if result:
                for r in result:
                    st.write(f"✅ {r}")
        except Exception as e:
            st.write(f"❌ Error in {func.__name__}: {e}")