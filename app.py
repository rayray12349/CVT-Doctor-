import streamlit as st
import pandas as pd

def safe_float(val):
    try:
        return float(val)
    except:
        return None

def load_csv(file):
    df = pd.read_csv(file, encoding='ISO-8859-1', skiprows=8)
    for col in df.columns:
        df[col] = df[col].apply(safe_float)
    return df

def detect_chain_slip(df):
    if 'Actual Gear Ratio' in df and 'Primary Rev Speed' in df and 'Secondary Rev Speed' in df:
        ratio = df['Primary Rev Speed'] / df['Secondary Rev Speed']
        diff = (ratio - df['Actual Gear Ratio']).abs()
        return diff.gt(0.5).sum() > 10
    return False

def detect_lockup_judder(df):
    if 'Primary Rev Speed' in df and 'Secondary Rev Speed' in df and 'Lock Up Duty Ratio' in df and 'Accel. Opening Angle' in df:
        throttle = df['Accel. Opening Angle'] > 10
        fluct = (df['Primary Rev Speed'] - df['Secondary Rev Speed']).abs() > 100
        lockup = (df['Lock Up Duty Ratio'] > 50) & throttle & fluct
        return lockup.sum() > 10
    return False

def detect_forward_clutch_slip(df, is_tr690):
    if is_tr690:
        if 'Front Wheel Speed.1' in df and 'Secondary Rev Speed' in df:
            slip = (df['Secondary Rev Speed'] < df['Front Wheel Speed.1']) & (df['Accel. Opening Angle'] > 10)
            return slip.sum() > 10
    return False

def detect_short_slip(df):
    if 'Actual Gear Ratio' in df and 'Primary Rev Speed' in df and 'Secondary Rev Speed' in df:
        ratio = df['Primary Rev Speed'] / df['Secondary Rev Speed']
        diff = (ratio - df['Actual Gear Ratio']).abs()
        return (diff.between(0.2, 0.5)).sum() > 10
    return False

def detect_micro_slip(df):
    if 'Actual Gear Ratio' in df and 'Primary Rev Speed' in df and 'Secondary Rev Speed' in df:
        ratio = df['Primary Rev Speed'] / df['Secondary Rev Speed']
        diff = (ratio - df['Actual Gear Ratio']).abs()
        return (diff.between(0.05, 0.2)).sum() > 10
    return False

def detect_valve_body_irregularity(df):
    if 'Secondary Set Current' in df and 'Secondary Actual Current' in df:
        deviation = (df['Secondary Set Current'] - df['Secondary Actual Current']).abs()
        return deviation.gt(0.5).sum() > 10
    return False

def app():
    st.title("CVT Doctor Pro — Subaru TSB Diagnostic Tool")

    is_tr690 = st.selectbox("Select Transmission Type", ["TR690", "TR580"]) == "TR690"
    uploaded_file = st.file_uploader("Upload Subaru SSM4/BtSsm CSV File", type="csv")

    if uploaded_file:
        df = load_csv(uploaded_file)
        st.success("File loaded and processed successfully.")

        results = {
            "Chain Slip": detect_chain_slip(df),
            "Lock-Up Judder": detect_lockup_judder(df),
            "Forward Clutch Slip": detect_forward_clutch_slip(df, is_tr690),
            "Short Slip": detect_short_slip(df),
            "Micro Slip": detect_micro_slip(df),
            "Valve Body Irregularity": detect_valve_body_irregularity(df)
        }

        for issue, detected in results.items():
            if detected:
                st.error(f"{issue} detected. ⚠️")
            else:
                st.success(f"No {issue} detected.")

        st.markdown("---")
        st.subheader("Repair Recommendations")
        for issue, detected in results.items():
            if detected:
                if issue == "Chain Slip":
                    st.write("🔧 Replace CVT chain and inspect pulleys for wear.")
                elif issue == "Lock-Up Judder":
                    st.write("🔧 Replace torque converter and flush CVT fluid.")
                elif issue == "Forward Clutch Slip":
                    st.write("🔧 Inspect forward clutch pack and valve body for pressure issues.")
                elif issue in ["Short Slip", "Micro Slip"]:
                    st.write("🔧 Reflash TCM with latest software and inspect fluid condition.")
                elif issue == "Valve Body Irregularity":
                    st.write("🔧 Replace valve body and retest system calibration.")

if __name__ == "__main__":
    app()