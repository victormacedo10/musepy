import numpy as np
import pickle
from scipy.signal import firwin, filtfilt, iirnotch, welch


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

    if 'imu' in muse_data:
        for imu_marker in ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ']:
            if imu_marker in muse_data['imu']:
                imu_channel = muse_data['imu'][imu_marker]
                results['imu']['raw_data'][imu_marker] = imu_channel
            else:
                print(f'IMU marker {imu_marker} not found in the data')

    if 'ppg' in muse_data:
        for ppg_marker in ['PPG_1', 'PPG_2']:
            if ppg_marker in muse_data['ppg']:
                ppg_channel = muse_data['ppg'][ppg_marker]
                results['ppg']['raw_data'][ppg_marker] = ppg_channel
            else:
                print(f'PPG channel {ppg_marker} not found in the data')

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
