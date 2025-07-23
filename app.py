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
    return 'Secondary Rev Speed' in df.columns and 'Front Wheel Speed' in df.columns

def get_throttle(df):
    t1 = df.get('Accel. Opening Angle')
    t2 = df.get('Throttle Opening Angle')
    if t1 is not None and t2 is not None:
        return t1.combine_first(t2)
    return t1 if t1 is not None else t2

def get_speed(df):
    s1 = df.get('Front Wheel Speed')
    s2 = df.get('Vehicle Speed')
    if s1 is not None and s2 is not None:
        return s1.combine_first(s2)
    return s1 if s1 is not None else s2

def get_time(df):
    try:
        return df['TIME'].astype(float).reset_index(drop=True) / 1000
    except:
        return None

def is_throttle_stable(throttle, window=10):
    return throttle.rolling(window=window).std() < 2

def get_peak_time(events, time_series):
    if time_series is not None and events.any():
        peak_index = events[events].rolling(10).sum().idxmax()
        return float(time_series.iloc[peak_index]) if peak_index < len(time_series) else None
    return None

def plot_detection(df, pid, events, title):
    fig, ax = plt.subplots()
    ax.plot(df.index, df[pid], label=pid, alpha=0.7)
    ax.scatter(df.index[events], df[pid][events], color='red', label='Detected')
    ax.set_title(title)
    ax.set_xlabel("Index")
    ax.set_ylabel(pid)
    ax.legend()
    st.pyplot(fig)

def detect_micro_slip(df, time_series):
    gear = df.get('Actual Gear Ratio')
    prim = df.get('Primary Rev Speed')
    sec = df.get('Secondary Rev Speed')
    throttle = get_throttle(df)
    speed = get_speed(df)
    if any(v is None for v in [gear, prim, sec, throttle, speed]) or (speed <= 10).all():
        return False, 0.0, None

    stable = is_throttle_stable(throttle, window=10)
    gear_fluct = gear.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 0.03
    prim_fluct = prim.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 60
    sec_fluct = sec.rolling(5).apply(lambda x: x.max() - x.min(), raw=True) > 60
    rpm_fluct = prim_fluct | sec_fluct

    event = (gear_fluct & rpm_fluct & (throttle > 1) & stable & (speed > 10))
    event_confirmed = event.rolling(10).sum() >= 5
    score = 100.0 * event_confirmed.sum() / len(event_confirmed)
    confidence = min(score, 100.0)
    peak_time = get_peak_time(event_confirmed, time_series)

    if event_confirmed.any():
        st.subheader("🔍 Micro Slip Debug")
        plot_detection(df, 'Actual Gear Ratio', event_confirmed, "Micro Slip Detection")

    return event_confirmed.any(), round(confidence, 1), peak_time

# ---------- Streamlit App ----------
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

    detected, confidence, peak = detect_micro_slip(df, time_series)
    if detected:
        st.markdown(f"- **Micro Slip**: ⚠️ Detected at {peak:.1f}s — {confidence}% confidence — _Replace CVT after confirming persistent fluctuation._")
    else:
        st.markdown(f"- **Micro Slip**: ✅ Not Detected — {confidence}% confidence")

    st.markdown("---")
    st.markdown("🔁 [TSB 16-132-20R Reference](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226904-0001.pdf)")