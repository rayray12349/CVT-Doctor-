import streamlit as st
import pandas as pd

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro – Subaru TSB Diagnostic Tool")

uploaded_file = st.file_uploader("📤 Upload Subaru CVT CSV Log", type=["csv"])
if uploaded_file is not None:
    # Skip metadata lines and read clean column headers
    try:
        df = pd.read_csv(uploaded_file, skiprows=8)
    except Exception as e:
        st.error(f"❌ CSV read error: {e}")
        st.stop()

    # Show initial column headers for review
    st.success("✅ File loaded. Columns detected:")
    st.code(", ".join(df.columns))

    # Rename known generic columns
    column_map = {
        "rpm": "Engine RPM",
        "rpm.1": "Primary RPM",
        "%": "Throttle Opening Angle",
        "°F": "ATF Temp",
        "%.1": "Lock Up Duty Ratio",
        "Unnamed: 13": "Line Pressure",
        "rpm.2": "Front Wheel Speed.1"
    }
    df.rename(columns={k: v for k, v in column_map.items() if k in df.columns}, inplace=True)

    # TR580/TR690 dropdown
    cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])
    front_wheel_pid = "Front Wheel Speed.1" if cvt_type == "TR690" else None

    def detect_micro_slip(df):
        if "Engine RPM" in df.columns and "Primary RPM" in df.columns:
            slip = (df["Engine RPM"] - df["Primary RPM"]).abs()
            return [f"{i} - Micro Slip: {val} RPM" for i, val in enumerate(slip) if val > 200]
        else:
            return []

    def detect_short_slip(df):
        if "Engine RPM" in df.columns and "Primary RPM" in df.columns:
            slips = []
            for i in range(len(df) - 3):
                window = (df["Engine RPM"].iloc[i:i+3] - df["Primary RPM"].iloc[i:i+3]).abs()
                if window.gt(500).all() and window.lt(800).all():
                    slips.append(f"{i} - Short Slip: 3-frame slip between 500–800 RPM")
            return slips
        else:
            return []

    def detect_long_slip(df):
        if "Engine RPM" in df.columns and "Primary RPM" in df.columns:
            slips = []
            for i in range(len(df) - 6):
                window = (df["Engine RPM"].iloc[i:i+6] - df["Primary RPM"].iloc[i:i+6]).abs()
                if window.gt(500).all():
                    slips.append(f"{i} - Long Slip: 6-frame slip > 500 RPM")
            return slips
        else:
            return []

    def detect_lockup_slip(df):
        if "Engine RPM" in df.columns and "Primary RPM" in df.columns and "Lock Up Duty Ratio" in df.columns:
            slip = df["Lock Up Duty Ratio"].rolling(3).mean() > 80
            rpm_delta = (df["Engine RPM"] - df["Primary RPM"]).abs()
            return [f"{i} - Lockup Slip: {val} RPM with Lockup > 80%" for i, val in enumerate(rpm_delta) if slip.iloc[i] and val > 300]
        else:
            return []

    def detect_forward_clutch_slip(df):
        if "Engine RPM" in df.columns and "Primary RPM" in df.columns:
            throttle = df["Throttle Opening Angle"] if "Throttle Opening Angle" in df.columns else pd.Series([2] * len(df))
            speed = df[front_wheel_pid] if front_wheel_pid and front_wheel_pid in df.columns else pd.Series([3] * len(df))
            rpm_delta = (df["Engine RPM"] - df["Primary RPM"]).abs()
            return [f"{i} - Forward Clutch Slip: Δ={rpm_delta.iloc[i]} | Throttle={throttle.iloc[i]} | Speed={speed.iloc[i]}" for i in range(len(rpm_delta)) if rpm_delta.iloc[i] > 600 and throttle.iloc[i] > 1 and speed.iloc[i] > 2]
        else:
            return []

    def detect_valve_body_behavior(df):
        if "Line Pressure" in df.columns and "Throttle Opening Angle" in df.columns:
            anomalies = df["Line Pressure"].rolling(5).std() > 30
            return [f"{i} - Valve Body Anomaly: Line Pressure variance" for i in anomalies[anomalies].index]
        else:
            return []

    def detect_torque_converter_judder(df):
        if "Engine RPM" in df.columns:
            judder = df["Engine RPM"].diff().abs().rolling(5).std() > 50
            return [f"{i} - Torque Converter Judder: RPM instability" for i in judder[judder].index]
        else:
            return []

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
                st.subheader(f"🔍 {func.__name__.replace('_', ' ').title()}")
                for r in result:
                    st.write(f"✅ {r}")
            else:
                st.info(f"⚠️ {func.__name__.replace('_', ' ').title()}: No issues detected.")
        except Exception as e:
            st.error(f"❌ {func.__name__} failed: {e}")