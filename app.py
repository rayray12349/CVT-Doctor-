import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="CVT Doctor Pro", layout="wide")
st.title("🩺 CVT Doctor Pro - Subaru TSB Diagnostic Tool")

# --- Helper Functions ---

def safe_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return np.nan

def load_csv(file):
    df = pd.read_csv(file, skiprows=8, encoding="ISO-8859-1", on_bad_lines='skip')
    df = df.applymap(safe_float)
    return df

# --- Detection Functions ---

def detect_chain_slip(df):
    if 'Engine RPM' in df.columns and 'Primary RPM' in df.columns:
        rpm_diff = (df['Engine RPM'] - df['Primary RPM']).abs()
        return rpm_diff.gt(250).sum() > 50
    return False

def detect_micro_slip(df):
    if 'Actual Gear Ratio' in df.columns and 'Primary RPM' in df.columns and 'Secondary RPM' in df.columns:
        gear_ratio_calc = df['Primary RPM'] / df['Secondary RPM'].replace(0, np.nan)
        ratio_diff = (df['Actual Gear Ratio'] - gear_ratio_calc).abs()
        return ratio_diff.between(0.1, 0.2).sum() > 100
    return False

def detect_short_slip(df):
    if 'Actual Gear Ratio' in df.columns and 'Primary RPM' in df.columns and 'Secondary RPM' in df.columns:
        gear_ratio_calc = df['Primary RPM'] / df['Secondary RPM'].replace(0, np.nan)
        ratio_diff = (df['Actual Gear Ratio'] - gear_ratio_calc).abs()
        return ratio_diff.between(0.2, 0.4).sum() > 75
    return False

def detect_long_slip(df):
    if 'Actual Gear Ratio' in df.columns and 'Primary RPM' in df.columns and 'Secondary RPM' in df.columns:
        gear_ratio_calc = df['Primary RPM'] / df['Secondary RPM'].replace(0, np.nan)
        ratio_diff = (df['Actual Gear Ratio'] - gear_ratio_calc).abs()
        return ratio_diff.gt(0.4).sum() > 50
    return False

def detect_lockup_judder(df):
    if 'Primary RPM' in df.columns and 'Secondary RPM' in df.columns and 'Throttle Position (%)' in df.columns and 'Lock Up Duty Ratio' in df.columns:
        filtered = df[df['Throttle Position (%)'] > 10]
        fluctuation = (filtered['Primary RPM'] - filtered['Secondary RPM']).diff().abs()
        return fluctuation.gt(50).sum() > 30
    return False

def detect_torque_converter_judder(df):
    if 'Primary RPM' in df.columns and 'Secondary RPM' in df.columns:
        delta = (df['Primary RPM'] - df['Secondary RPM']).diff().abs()
        return delta.gt(80).sum() > 30
    return False

def detect_forward_clutch_slip(df, cvt_type):
    if cvt_type == 'TR690':
        fw_col = 'Front Wheel Speed.1 (RPM)'
        if fw_col in df.columns and 'Secondary Rev Speed' in df.columns and 'Throttle Position (%)' in df.columns:
            flow_sec = np.sign(df['Secondary Rev Speed'].diff())
            flow_fw = np.sign(df[fw_col].diff())
            flow_mismatch = flow_sec != flow_fw
            mismatch_count = flow_mismatch & (df['Throttle Position (%)'] > 10)
            return mismatch_count.sum() > 50
    return False

# --- TSB Aggregator and Recommendations ---

def analyze_tsb(df, cvt_type):
    results = {
        "Chain Slip": detect_chain_slip(df),
        "Micro Slip": detect_micro_slip(df),
        "Short Slip": detect_short_slip(df),
        "Long Slip": detect_long_slip(df),
        "Lock-Up Judder": detect_lockup_judder(df),
        "Torque Converter Judder": detect_torque_converter_judder(df),
        "Forward Clutch Slip": detect_forward_clutch_slip(df, cvt_type)
    }
    return results

def repair_recommendations(results):
    recs = []
    if results["Chain Slip"]: recs.append("Check belt chain stretch and replace CVT if excessive.")
    if results["Micro Slip"]: recs.append("Monitor for degradation, may require valve body rework.")
    if results["Short Slip"]: recs.append("Inspect pulley surfaces and pressure solenoids.")
    if results["Long Slip"]: recs.append("Likely internal damage, overhaul recommended.")
    if results["Lock-Up Judder"]: recs.append("Flush ATF and reprogram TCM.")
    if results["Torque Converter Judder"]: recs.append("Replace torque converter and inspect lock-up clutch.")
    if results["Forward Clutch Slip"]: recs.append("Check for front clutch wear or solenoid control issues.")
    return recs

# --- Streamlit App UI ---

uploaded_file = st.file_uploader("Upload your Subaru SSM/BtSsm CSV file", type="csv")
cvt_type = st.selectbox("Select CVT Type", ["TR580", "TR690"])

if uploaded_file:
    df = load_csv(uploaded_file)
    results = analyze_tsb(df, cvt_type)
    
    st.subheader("📊 TSB Diagnosis Summary")
    for problem, detected in results.items():
        st.write(f"**{problem}**: {'✅ Detected' if detected else '❌ Not Detected'}")
    
    recs = repair_recommendations(results)
    if recs:
        st.subheader("🔧 Recommended Repairs")
        for rec in recs:
            st.write(f"- {rec}")
    else:
        st.success("No major issues detected. CVT operating within normal parameters.")