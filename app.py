import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io

def safe_float(x):
    try:
        return float(x)
    except:
        return np.nan

@st.cache_data
def load_csv(file):
    decoded = file.read().decode('utf-8', errors='ignore')
    df = pd.read_csv(io.StringIO(decoded), skiprows=8)
    df = df.applymap(safe_float)
    return df.dropna(axis=1, how='all')

def detect_tr690(df):
    return 'Front Wheel Speed.1' in df.columns

def get_throttle(df):
    t1 = df.get('Accel. Opening Angle')
    t2 = df.get('Throttle Opening Angle')
    if t1 is not None and t2 is not None:
        return t1.combine_first(t2)
    return t1 if t1 is not None else t2

def get_speed(df):
    s1 = df.get('Front Wheel Speed.1')
    s2 = df.get('Vehicle Speed')
    if s1 is not None and s2 is not None:
        return s1.combine_first(s2)
    return s1 if s1 is not None else s2

def get_time(df):
    try:
        return df['TIME'].astype(float).reset_index(drop=True) / 1000
    except:
        return None

def get_peak_time(events, time_series):
    if time_series is not None and events.any():
        peak_index = events[events].rolling(10).sum().idxmax()
        return float(time_series.iloc[peak_index]) if peak_index < len(time_series) else None
    return None

def is_throttle_stable(throttle, window=10):
    return throttle.rolling(window=window).std() < 1

def detect_micro_slip(df, time_series):
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')
    throttle = get_throttle(df)
    speed = get_speed(df)

    if any(v is None for v in [gear, prim, sec, throttle, speed]) or (speed <= 10).all():
        return False, None, 0

    stable = is_throttle_stable(throttle, window=10)
    gear_fluct = gear.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 0.06
    prim_fluct = prim.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 50
    sec_fluct = sec.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 50
    rpm_fluct = prim_fluct & sec_fluct

    event = gear_fluct & rpm_fluct & (throttle > 10) & stable & (speed > 10)
    confirmed = event.rolling(10).sum() >= 5
    score = confirmed.sum()
    return score > 0, get_peak_time(confirmed, time_series), round(min(score * 3, 100), 1)

def detect_forward_clutch_slip(df, time_series, tr690=True):
    if tr690:
        upstream = df.get('Secondary Rev Speed')
        downstream = df.get('Front Wheel Speed.1')
    else:
        upstream = df.get('Turbine Revolution Speed')
        downstream = df.get('Primary Rev Speed')

    if upstream is None or downstream is None:
        return False, None, 0

    delta = (upstream - downstream).abs()
    mismatch = delta.rolling(5).mean() > 75
    score = mismatch.sum()
    return mismatch.any(), get_peak_time(mismatch, time_series), round(min(score * 3, 100), 1)

# Placeholder for other slip detections like short-time, chain, etc.

# ----------------- Streamlit UI ------------------

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
        "Micro Slip": (detect_micro_slip(df, time_series), "Replace CVT after confirming persistent fluctuation."),
        "Forward Clutch Slip": (detect_forward_clutch_slip(df, time_series, tr690=is_tr690), "Reprogram TCM; replace valve body or CVT."),
    }

    for label, ((detected, peak_time, confidence), recommendation) in results.items():
        if detected:
            peak_str = f" at {peak_time:.1f}s" if peak_time is not None else ""
            st.markdown(f"- **{label}**: ⚠️ Detected{peak_str} — _{recommendation}_")
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• Confidence: **{confidence:.1f}%**")

            fig, ax = plt.subplots()
            if label == "Micro Slip":
                ax.plot(time_series, df.get("Actual Gear Ratio"), label="Actual Gear Ratio")
            elif label == "Forward Clutch Slip":
                ax.plot(time_series, df.get("Secondary Rev Speed"), label="Secondary RPM")
                ax.plot(time_series, df.get("Front Wheel Speed.1"), label="Front Wheel Speed (RPM)")
            ax.set_title(f"{label} - Debug Chart")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Sensor Values")
            ax.legend()
            st.pyplot(fig)
        else:
            st.markdown(f"- **{label}**: ✅ Not Detected")

    st.divider()
    st.markdown("🔁 [TSB 16-132-20R Reference](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226904-0001.pdf)")