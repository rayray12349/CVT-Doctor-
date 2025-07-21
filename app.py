import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

st.set_page_config(page_title="CVT Doctor Pro – TSB Edition", layout="wide")
st.title("🔧 CVT Doctor Pro – Subaru TSB Diagnostic Tool")

column_rename_map = {
    "Engine Speed": "Engine RPM",
    "Primary Rev Speed": "Primary RPM",
    "Secondary Rev Speed": "Secondary RPM",
    "Accel. Opening Angle": "Throttle %",
    "Turbine Revolution Speed": "Turbine RPM",
    "Actual Gear Ratio": "Gear Ratio",
    "Lock Up Duty Ratio": "TCC Lockup %",
    "ATF Temp.": "ATF Temp (°F)"
}

def plot_event(df, ycols, label, idx, window=30):
    fig, ax = plt.subplots()
    window = max(10, window)
    slc = df.iloc[max(idx-window,0):min(idx+window,len(df))]
    for col in ycols:
        if col in slc.columns:
            ax.plot(slc.index, pd.to_numeric(slc[col], errors="coerce"), label=col)
    ax.set_title(f"{label} Around Index {idx}")
    ax.legend()
    return fig

def detect_micro_slip(df):
    events = []
    throttle = pd.to_numeric(df.get("Throttle %"), errors="coerce")
    gear_ratio = pd.to_numeric(df.get("Gear Ratio"), errors="coerce")
    primary_rpm = pd.to_numeric(df.get("Primary RPM"), errors="coerce")
    secondary_rpm = pd.to_numeric(df.get("Secondary RPM"), errors="coerce")
    rolling_throttle_std = throttle.rolling(10, min_periods=1).std()
    primary_fluct = primary_rpm.diff().abs().rolling(5).mean()
    secondary_fluct = secondary_rpm.diff().abs().rolling(5).mean()
    ratio_fluct = gear_ratio.diff().abs().rolling(5).mean()
    for i in range(len(df)):
        if (rolling_throttle_std.iloc[i] < 1.5 and
            ((primary_fluct.iloc[i] > 50) or (secondary_fluct.iloc[i] > 50)) and
            ratio_fluct.iloc[i] > 0.02):
            events.append({
                'Type': 'TSB Micro-Slip',
                'Time': i,
                'Details': 'Fluctuating ratio & RPM under steady throttle',
                'Graph': plot_event(df, ["Gear Ratio", "Throttle %", "Primary RPM", "Secondary RPM"], "TSB Micro-Slip", i)
            })
    return events