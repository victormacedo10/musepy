import numpy as np
import pickle
from scipy.signal import firwin, filtfilt, iirnotch, welch


def remove_line_noise(eeg_array, fs, line_freq=50.0):
    """
    Remove line noise using zapline or DSS-based method.
    eeg_array: channels × time
    returns cleaned_array
    """
    # notch at line_freq with Q factor
    # Q value: e.g. 30
    b, a = iirnotch(w0=line_freq/(fs/2), Q=30)
    cleaned = filtfilt(b, a, eeg_array, axis=1)
    return cleaned

def design_fir_filter(fs, cutoff, filter_type='lowpass', transition_bw=None):
    """
    Design a FIR filter using windowed sinc, return filter coefficients.
    cutoff: cutoff frequency (Hz; if lowpass, it's high cutoff; if highpass, low cutoff)
    filter_type: 'lowpass' or 'highpass'
    transition_bw: transition bandwidth in Hz
    """
    nyq = fs / 2
    if filter_type == 'lowpass':
        # e.g., cutoff at ~50 Hz, transition_bw ~20 Hz → so passband end at cutoff - (transition_bw/2), stopband start at cutoff + (transition_bw/2)
        # But firwin takes cutoff frequency(s) normalized to Nyquist
        # For a simple lowpass, we specify cutoff as cutoff, but we need filter order to achieve desired transition width
        # Approximate filter order using: N = (fs / transition_bw) * some constant (~3.3 for Hamming, etc.)
        N = int(np.ceil((fs / transition_bw) * 3.3))
        if N % 2 == 0:
            N += 1  # make sure order is odd for symmetric filter
        taps = firwin(N, cutoff / nyq, window='hann', pass_zero=True)
    elif filter_type == 'highpass':
        N = int(np.ceil((fs / transition_bw) * 3.3))
        if N % 2 == 0:
            N += 1
        taps = firwin(N, cutoff / nyq, window='hann', pass_zero=False)
    else:
        raise ValueError("filter_type must be 'lowpass' or 'highpass'")
    return taps

def apply_fir(eeg_array, taps):
    """
    Apply FIR filter with zero-phase (filtfilt).
    eeg_array: channels × time
    taps: filter coefficients
    """
    return filtfilt(taps, [1.0], eeg_array, axis=1)

def re_reference(eeg_raw_dict):
    """
    Given raw channels dict from muse_data['eeg'] for AF7, AF8, TP9, TP10,
    produce re‑referenced channels: AF7‑TP9, AF8‑TP10
    returns array of shape (2 × time) plus maybe names
    """
    af7 = eeg_raw_dict['AF7']
    af8 = eeg_raw_dict['AF8']
    tp9 = eeg_raw_dict['TP9']
    tp10 = eeg_raw_dict['TP10']
    # Ensure equal length etc.
    # Differential
    chan1 = af7 - tp9
    chan2 = af8 - tp10
    return {'AF7_TP9': chan1, 'AF8_TP10': chan2}

def detect_artifacts(eeg_array, fs, thresh_amp=100.0, thresh_std=5.0):
    """
    Simple artifact detection for 2 channels.
    eeg_array: channels × time
    fs: sample rate
    thresh_amp: amplitude threshold in microVolts
    thresh_std: standard deviations for detecting high variance windows
    returns mask array (boolean) of same length as time: True = clean, False = artifact
    """
    # A) amplitude threshold
    # If either channel exceeds ±thresh_amp → artifact
    amp_mask = np.all(np.abs(eeg_array) < thresh_amp, axis=0)

    # B) windowed variance: compute moving window std
    win_s = int(0.5 * fs)  # e.g. 0.5 second windows
    step = win_s  # non-overlapping for simplicity
    std_mask = np.ones(eeg_array.shape[1], dtype=bool)

    for start in range(0, eeg_array.shape[1], step):
        end = min(start + win_s, eeg_array.shape[1])
        seg = eeg_array[:, start:end]
        # compute per–channel std
        seg_std = np.std(seg, axis=1)
        # if either channel has std much higher than baseline
        if np.any(seg_std > thresh_std * np.median(seg_std)):
            std_mask[start:end] = False

    # Combined mask
    clean_mask = amp_mask & std_mask
    return clean_mask

# ---- Main processing function ------------------------------------------------

def processing_function(input_dict):
    # Read input CSVs
    if "muse_data" in input_dict:
        f = open(input_dict['muse_data'], 'rb')
        muse_data = input_dict['muse_data']
    elif len(input_dict) == 1:
        # Only one file found, assuming it is the muse data
        muse_data = list(input_dict.values())[0]
    else:
        print('Multiple input files, please use the "muse_data" ID to specify the file to process')
        return {"error": "No muse data found"}
    eeg_time = muse_data['eeg']['timestamp'] - muse_data['eeg']['timestamp'][0]
    imu_time = muse_data['imu']['timestamp'] - muse_data['imu']['timestamp'][0]
    results = {'eeg': {'raw_data': {}, 'time': eeg_time}, 
                'imu': {'raw_data': {}, 'time': imu_time}}

    fs = 256.0
    # Use this if you want to compute the sampling frequency from the time array
    # fs = int(round(1.0 / np.mean(np.diff(eeg_time)))) 

    # Step 0: collect raw data into array
    eeg_channels = ['TP9', 'TP10', 'AF7', 'AF8']
    eeg_data = {ch: muse_data['eeg'][ch].to_numpy() for ch in eeg_channels}

    for ch in eeg_channels:
        results['eeg']['raw_data'][ch] = eeg_data[ch]

    # Stack for filtering: shape (4, time)
    eeg_array = np.vstack([eeg_data[ch] for ch in eeg_channels])
    results['eeg']['preprocessed_array'] = eeg_array.copy()

    # 1.1 Notch filter at 50 Hz
    notch_freq = 50.0
    Q = 30.0
    b_notch, a_notch = iirnotch(notch_freq / (fs / 2), Q)
    eeg_array = filtfilt(b_notch, a_notch, eeg_array, axis=1)
    results['eeg']['after_notch'] = eeg_array.copy()

    # 1.2 Low-pass FIR filter (~50 Hz cutoff, 20 Hz transition)
    lp_cutoff = 50.0
    lp_trans_bw = 20.0
    lp_order = int(np.ceil((fs / lp_trans_bw) * 3.3))
    lp_order += 1 - lp_order % 2  # make odd
    lp_taps = firwin(lp_order, lp_cutoff / (fs / 2), window='hann', pass_zero=True)
    eeg_array = filtfilt(lp_taps, [1.0], eeg_array, axis=1)
    results['eeg']['after_lowpass'] = eeg_array.copy()

    # 1.3 High-pass FIR filter (~0.375 Hz cutoff, 0.75 Hz transition)
    hp_cutoff = 0.375
    hp_trans_bw = 0.75
    hp_order = int(np.ceil((fs / hp_trans_bw) * 3.3))
    hp_order += 1 - hp_order % 2
    hp_taps = firwin(hp_order, hp_cutoff / (fs / 2), window='hann', pass_zero=False)
    eeg_array = filtfilt(hp_taps, [1.0], eeg_array, axis=1)
    results['eeg']['after_highpass'] = eeg_array.copy()

    # 1.4 Re-reference: AF7−TP9 and AF8−TP10
    reref = {
        'AF7_RR': eeg_array[2] - eeg_array[0],
        'AF8_RR': eeg_array[3] - eeg_array[1]
    }
    results['eeg']['rereferenced'] = reref.copy()

    # 1.5 Artifact rejection: amplitude + std-based
    thresh_amp = 150.0  # µV
    thresh_std = 5.0
    mask = np.ones(eeg_array.shape[1], dtype=bool)

    reref_array = np.vstack([reref['AF7_RR'], reref['AF8_RR']])
    amp_mask = np.all(np.abs(reref_array) < thresh_amp, axis=0)

    win_s = int(0.5 * fs)
    std_mask = np.ones_like(mask)
    for start in range(0, len(mask), win_s):
        end = min(start + win_s, len(mask))
        segment = reref_array[:, start:end]
        seg_std = np.std(segment, axis=1)
        if np.any(seg_std > thresh_std * np.median(seg_std)):
            std_mask[start:end] = False

    clean_mask = mask & amp_mask & std_mask
    results['eeg']['clean_mask'] = clean_mask

    reref_clean = {
        k: v.copy() for k, v in reref.items()
    }
    for k in reref_clean:
        reref_clean[k][~clean_mask] = np.nan

    results['eeg']['rereferenced_clean'] = reref_clean.copy() 

    # 2) Welch PSD and Band Power
    bands = {
        'delta': (0.5, 4),
        'theta': (4, 8),
        'alpha': (8, 12),
        'beta':  (12, 30),
        'gamma': (30, 100)
    }

    results['eeg']['psd_data'] = {}
    results['eeg']['band_power'] = {}
    results['eeg']['psd_freq'] = None

    for ch_name in reref_clean:
        valid = ~np.isnan(reref_clean[ch_name])
        if np.sum(valid) < fs:
            continue
        f, psd = welch(reref_clean[ch_name][valid], fs=fs, nperseg=2*fs, noverlap=fs, window='hann')
        results['eeg']['psd_data'][ch_name] = psd
        if results['eeg']['psd_freq'] is None:
            results['eeg']['psd_freq'] = f
        results['eeg']['band_power'][ch_name] = {
            band: np.trapezoid(psd[(f >= low) & (f <= high)], f[(f >= low) & (f <= high)])
            for band, (low, high) in bands.items()
        }

    for imu_marker in ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ']:
        imu_channel = muse_data['imu'][imu_marker]
        results['imu']['raw_data'][imu_marker] = imu_channel

    return results

# --- Main Execution Block ---
if __name__ == '__main__':
    from pathlib import Path
    file_path =  Path('C:/Users/victo/Local/repos/musepy/data/Muse_Data/resting_layed.data')
    muse_data = pickle.load(open(file_path, 'rb'))
    input_files = {
        'test_sample': muse_data
    }
    processing_function(input_files)
