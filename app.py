import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🧠 CVT Doctor Pro")
st.caption("Automated Subaru CVT Diagnostic Assistant")
st.divider()

# Utility Functions
def safe_float(val):
    try:
        return float(val)
    except:
        return np.nan

def load_csv(file):
    df = pd.read_csv(file, skiprows=8)
    df = df.applymap(safe_float)
    df = df.dropna(how='all')
    df = df.ffill()
    return df

def get_time_series(df):
    return df.get('Time[s]', pd.Series(np.arange(len(df)) / 10.0))

def get_throttle(df):
    throttle = df.get('Accel. Opening Angle')
    if throttle is None or throttle.isnull().all():
        throttle = df.get('Throttle Opening Angle')
    return throttle.fillna(0)

def get_speed(df):
    return df.get('Vehicle Speed', pd.Series(0)).fillna(0)

def get_actual_gear_ratio(df):
    return df.get("Actual Gear Ratio", pd.Series(0)).fillna(0)

def is_tr690(df):
    return "Front Wheel Speed (RPM)" in df.columns

def get_front_wheel_speed(df):
    return df.get("Front Wheel Speed (RPM)", pd.Series(0)).fillna(0)

def get_primary_rev(df):
    return df.get("Primary Rev Speed", pd.Series(0)).fillna(0)

def get_secondary_rev(df):
    return df.get("Secondary Rev Speed", pd.Series(0)).fillna(0)
def detect_micro_slip(df, time_series):
    agr = get_actual_gear_ratio(df)
    throttle = get_throttle(df)
    speed = get_speed(df)
    confidence = 0
    peak_time = None
    cycle_count = 0

    if agr.isnull().any():
        return False, None, 0

    for i in range(10, len(agr)-10):
        window = agr[i-10:i+10]
        peak_to_peak = window.max() - window.min()
        throttle_std = np.std(throttle[i-10:i+10])
        if (
            peak_to_peak > 0.06 and
            np.mean(throttle[i-10:i+10]) > 10 and
            throttle_std < 1 and
            np.mean(speed[i-10:i+10]) > 10
        ):
            cycle_count += 1
            if cycle_count >= 5:
                confidence = min(100, peak_to_peak * 100)
                peak_time = time_series.iloc[i]
                return True, peak_time, confidence
        else:
            cycle_count = 0

    return False, None, confidence


def detect_short_time_slip(df, time_series):
    agr = get_actual_gear_ratio(df)
    expected = df.get("Target Gear Ratio", pd.Series(0)).fillna(0)
    throttle = get_throttle(df)
    speed = get_speed(df)
    confidence = 0

    diff = np.abs(agr - expected)
    for i in range(10, len(diff)):
        if (
            diff.iloc[i] > 0.15 and
            throttle.iloc[i] > 10 and
            speed.iloc[i] > 10
        ):
            peak_time = time_series.iloc[i]
            confidence = min(100, diff.iloc[i] * 300)
            return True, peak_time, confidence

    return False, None, confidence


def detect_long_time_slip(df, time_series):
    return False, None, 0  # Simulated — no logic


def detect_forward_clutch_slip(df, time_series):
    if not is_tr690(df):
        return False, None, 0
    secondary = get_secondary_rev(df)
    front_wheel_rpm = get_front_wheel_speed(df)
    throttle = get_throttle(df)
    speed = get_speed(df)

    for i in range(10, len(secondary)):
        delta = abs(secondary.iloc[i] - front_wheel_rpm.iloc[i])
        if (
            delta > 400 and
            throttle.iloc[i] > 10 and
            speed.iloc[i] > 10
        ):
            confidence = min(100, delta / 5)
            peak_time = time_series.iloc[i]
            return True, peak_time, confidence

    return False, None, 0
def detect_torque_converter_judder(df, time_series):
    primary = get_primary_rev(df)
    secondary = get_secondary_rev(df)
    throttle = get_throttle(df)
    speed = get_speed(df)
    confidence = 0
    peak_time = None
    cycle_count = 0

    for i in range(10, len(primary)-10):
        p_window = primary[i-10:i+10]
        s_window = secondary[i-10:i+10]
        p_fluct = p_window.max() - p_window.min()
        s_fluct = s_window.max() - s_window.min()
        if (
            p_fluct > 50 and
            s_fluct > 50 and
            throttle.iloc[i] > 10 and
            speed.iloc[i] > 10
        ):
            cycle_count += 1
            if cycle_count >= 5:
                confidence = min(100, (p_fluct + s_fluct) / 2)
                peak_time = time_series.iloc[i]
                return True, peak_time, confidence
        else:
            cycle_count = 0

    return False, None, confidence


def detect_lockup_judder(df, time_series):
    return detect_torque_converter_judder(df, time_series)  # Same base logic


def detect_chain_slip(df, time_series):
    primary = get_primary_rev(df)
    secondary = get_secondary_rev(df)
    engine = get_engine_rpm(df)
    throttle = get_throttle(df)
    speed = get_speed(df)
    confidence = 0
    peak_time = None
    cycle_count = 0

    for i in range(10, len(primary)-10):
        if (
            primary.iloc[i] > 1000 and
            secondary.iloc[i] > 1000 and
            engine.iloc[i] > 1000 and
            throttle.iloc[i] > 10 and
            speed.iloc[i] > 10
        ):
            rpm_diff = max(
                abs(primary.iloc[i] - secondary.iloc[i]),
                abs(primary.iloc[i] - engine.iloc[i]),
                abs(secondary.iloc[i] - engine.iloc[i])
            )
            if rpm_diff < 100:
                cycle_count += 1
                if cycle_count >= 5:
                    confidence = 50 + (100 - rpm_diff) / 2
                    peak_time = time_series.iloc[i]
                    return True, peak_time, min(confidence, 100)
            else:
                cycle_count = 0

    return False, None, confidence
# ---------- Streamlit App UI ----------

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🔧 CVT Doctor Pro")
st.markdown("Subaru TR580 & TR690 CVT Diagnostic App — Based on TSB 16-132-20R")

uploaded_file = st.file_uploader("Upload your SSM4/BtSsm CSV file:", type=["csv"])
if uploaded_file:
    df = load_csv(uploaded_file)
    st.success("✅ File loaded successfully.")

    is_tr690 = detect_tr690(df)
    time_series = get_time(df)
    st.markdown(f"**Detected Transmission:** {'TR690' if is_tr690 else 'TR580'}")

    st.subheader("📊 Diagnostic Summary")

    results = {
        "Chain Slip": (detect_chain_slip(df, time_series), "Replace CVT & TCM if confirmed via SSM; submit QMR."),
        "Micro Slip": (detect_micro_slip(df, time_series), "Replace CVT after confirming persistent fluctuation."),
        "Short-Time Slip": (detect_short_time_slip(df, time_series), "Reprogram TCM; replace CVT if slip persists."),
        "Long-Time Slip": (simulate_long_time_slip(df, time_series), "Reprogram TCM; monitor for progressive wear. (Simulated)"),
        "Forward Clutch Slip": (
            detect_forward_clutch_slip(df, time_series, tr690=is_tr690) if is_tr690 else (False, None, 0),
            "Reprogram TCM; replace valve body or CVT."
        ),
        "Lock-Up Judder": (detect_lockup_judder(df, time_series), "Reprogram TCM; check ATF; replace converter if needed."),
        "Torque Converter Judder": (detect_torque_converter_judder(df, time_series), "Replace torque converter; inspect pump & solenoids."),
    }

    for label, ((detected, peak_time, confidence), recommendation) in results.items():
        if detected:
            peak_str = f" at {peak_time:.1f}s" if peak_time else ""
            st.markdown(f"- **{label}**: ⚠️ Detected{peak_str} — _{recommendation}_")
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• Confidence: **{confidence:.1f}%**")

            # Debug Chart
            st.markdown(f"#### 🔍 {label} Debug Chart")
            fig, ax = plt.subplots()
            if label in ["Chain Slip", "Micro Slip", "Short-Time Slip", "Long-Time Slip"]:
                ax.plot(time_series, df.get("Actual Gear Ratio"), label="Actual Gear Ratio")
            if label == "Forward Clutch Slip":
                ax.plot(time_series, df.get("Secondary Rev Speed"), label="Secondary RPM")
                ax.plot(time_series, df.get("Front Wheel Speed (RPM)"), label="Front Wheel Speed (RPM)")
            if label in ["Lock-Up Judder", "Torque Converter Judder"]:
                ax.plot(time_series, df.get("Primary Rev Speed"), label="Primary RPM")
                ax.plot(time_series, df.get("Secondary Rev Speed"), label="Secondary RPM")
            ax.set_title(f"{label} - Related Data")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Sensor Value")
            ax.legend()
            st.pyplot(fig)
        else:
            st.markdown(f"- **{label}**: ✅ Not Detected")

    st.divider()
    st.markdown("🔁 [TSB 16-132-20R Reference](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226904-0001.pdf)")