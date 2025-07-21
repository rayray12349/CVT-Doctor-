import streamlit as st
import pandas as pd
import numpy as np
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
    "ATF Temp.": "ATF Temp (°F)",
    "Front Wheel Speed": "Front Wheel Speed (RPM)"
}

cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

def detect_forward_clutch_slip(df, cvt_type):
    events = []
    eng_rpm = pd.to_numeric(df.get("Engine RPM"), errors="coerce")
    if cvt_type == "TR690":
        wheel_rpm = pd.to_numeric(df.get("Front Wheel Speed (RPM)"), errors="coerce")
    else:
        wheel_rpm = pd.to_numeric(df.get("Primary RPM"), errors="coerce")

    for i in range(len(df)):
        if eng_rpm.iloc[i] > 1200 and abs(eng_rpm.iloc[i] - wheel_rpm.iloc[i]) > 600:
            events.append({
                'Type': 'Forward Clutch Slip',
                'Time': i,
                'Details': f'RPM delta exceeds 600 ({eng_rpm.iloc[i]} vs {wheel_rpm.iloc[i]})'
            })
    return events

def detect_micro_slip(df):
    events = []
    throttle = pd.to_numeric(df.get("Throttle %"), errors="coerce")
    gear_ratio = pd.to_numeric(df.get("Gear Ratio"), errors="coerce")
    primary_rpm = pd.to_numeric(df.get("Primary RPM"), errors="coerce")
    secondary_rpm = pd.to_numeric(df.get("Secondary RPM"), errors="coerce")
    throttle_std = throttle.rolling(10, min_periods=1).std()
    primary_fluct = primary_rpm.diff().abs().rolling(5).mean()
    secondary_fluct = secondary_rpm.diff().abs().rolling(5).mean()
    ratio_fluct = gear_ratio.diff().abs().rolling(5).mean()

    for i in range(len(df)):
        if (throttle_std.iloc[i] < 1.5 and
            ((primary_fluct.iloc[i] > 50) or (secondary_fluct.iloc[i] > 50)) and
            ratio_fluct.iloc[i] > 0.02):
            events.append({
                'Type': 'TSB Micro-Slip',
                'Time': i,
                'Details': 'Fluctuating ratio & RPM under steady throttle'
            })
    return events

def aggregate_all_tsb(df, cvt_type):
    all_events = []
    all_events += detect_forward_clutch_slip(df, cvt_type)
    all_events += detect_micro_slip(df)
    return sorted(all_events, key=lambda x: x["Time"])[:100]

uploaded_file = st.file_uploader("📤 Upload Subaru CVT CSV Log", type=["csv"])
if uploaded_file:
    raw = uploaded_file.read().decode("ISO-8859-1").splitlines()
    df = pd.read_csv(BytesIO('\n'.join(raw[8:]).encode("utf-8")))
    df.rename(columns=column_rename_map, inplace=True)
    df.index = range(len(df))
    st.success("✅ File loaded and columns mapped.")

    events = aggregate_all_tsb(df, cvt_type)

    if events:
        st.subheader("⚠️ TSB-Based Diagnostic Events")
        for ev in events:
            st.markdown(f"**{ev['Time']} - {ev['Type']}**: {ev['Details']}")

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
        st.success("✅ No TSB faults detected.")
else:
    st.info("Please upload a valid Subaru CVT CSV export.")