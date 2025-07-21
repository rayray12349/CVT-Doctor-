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
        for i in range(1, len(df)):
        if lock.iloc[i] > 85 and abs(turb.iloc[i] - eng.iloc[i]) > 300:
            events.append({
                'Type': 'Lock-Up Engagement Shock',
                'Time': i,
                'Details': 'High Lockup with Turbine vs Engine RPM mismatch',
                'Graph': plot_event(df, ["TCC Lockup %", "Turbine RPM", "Engine RPM"], "Lock-Up Shock", i)
            })
    return events

def detect_shift_up_shock(df):
    events = []
    throttle = pd.to_numeric(df.get("Throttle %"), errors="coerce")
    sec_rpm = pd.to_numeric(df.get("Secondary RPM"), errors="coerce")
    ratio = pd.to_numeric(df.get("Gear Ratio"), errors="coerce")
    for i in range(1, len(df)):
        if throttle.iloc[i] > 30 and ratio.diff().iloc[i] > 0.05 and sec_rpm.diff().iloc[i] < -150:
            events.append({
                'Type': 'Shift-Up Shock',
                'Time': i,
                'Details': 'Abrupt change during throttle and gear change',
                'Graph': plot_event(df, ["Throttle %", "Secondary RPM", "Gear Ratio"], "Shift-Up Shock", i)
            })
    return events

def detect_up_duty_fault(df):
    events = []
    up_duty = pd.to_numeric(df.get("Primary UP Duty"), errors="coerce")
    eng_rpm = pd.to_numeric(df.get("Engine RPM"), errors="coerce")
    for i in range(3, len(df)):
        window = up_duty.iloc[i-3:i+1]
        if window.std() > 15 and eng_rpm.iloc[i] > 2000:
            events.append({
                'Type': 'Primary UP Duty Control Fault',
                'Time': i,
                'Details': 'Irregular waveform in Primary UP Duty',
                'Graph': plot_event(df, ["Primary UP Duty", "Gear Ratio", "Engine RPM"], "UP Duty Fault", i)
            })
    return events

def aggregate_all_tsb(df):
    all_events = []
    for func in [
        detect_micro_slip,
        detect_short_slip,
        detect_long_slip,
        detect_forward_clutch_shock,
        detect_lockup_shock,
        detect_shift_up_shock,
        detect_up_duty_fault
    ]:
        all_events.extend(func(df))
    return sorted(all_events, key=lambda x: x["Time"])

uploaded_file = st.file_uploader("📤 Upload Subaru CVT CSV Log", type=["csv"])
if uploaded_file:
    raw = uploaded_file.read().decode("ISO-8859-1").splitlines()
    df = pd.read_csv(BytesIO('\n'.join(raw[8:]).encode("utf-8")))
    df.rename(columns=column_rename_map, inplace=True)
    df.index = range(len(df))
    st.success("✅ File loaded and columns mapped.")

    events = aggregate_all_tsb(df)

    if events:
        st.subheader("⚠️ TSB-Based Diagnostic Events")
        for ev in events:
            st.markdown(f"**{ev['Time']} - {ev['Type']}**: {ev['Details']}")
            st.pyplot(ev['Graph'])

        if st.button("📄 Export TSB PDF Report"):
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            c.setFont("Helvetica", 12)
            c.drawString(30, 750, "CVT Doctor Pro – Subaru TSB Diagnostic Report")
            c.drawString(30, 735, f"Detected Issues: {len(events)}")
            y = 715
            for ev in events:
                c.drawString(30, y, f"{ev['Time']}: {ev['Type']} – {ev['Details']}")
                y -= 15
                if y < 40:
                    c.showPage()
                    y = 750
            c.save()
            buffer.seek(0)
            st.download_button("📥 Download Report PDF", buffer, file_name="tsb_cvt_report.pdf")
    else:
        st.success("✅ No Subaru-defined TSB faults detected.")
else:
    st.info("Please upload a valid Subaru CVT CSV export.")