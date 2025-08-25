import pickle
import numpy as np
from scipy.signal import welch


def processing_function(input_paths):
    if "muse_data" not in input_paths:
        print('Please include the .data muse file and label muse_data')
        return {}
    
    # Read input CSVs
    f = open(input_paths['muse_data'], 'rb')
    muse_data = pickle.load(f)
    eeg_time = muse_data['eeg']['timestamp'] - muse_data['eeg']['timestamp'][0]
    imu_time = muse_data['imu']['timestamp'] - muse_data['imu']['timestamp'][0]
    ppg_time = muse_data['ppg']['timestamp'] - muse_data['ppg']['timestamp'][0]
    results = {'eeg': {'raw_data': {}, 'time': eeg_time}, 
                'imu': {'raw_data': {}, 'time': imu_time},
                'ppg': {'raw_data': {}, 'time': ppg_time}}

    for eeg_marker in ['TP9', 'TP10', 'AF7', 'AF8']:
        eeg_channel = muse_data['eeg'][eeg_marker].to_numpy()
        results['eeg']['raw_data'][eeg_marker] = eeg_channel

        # -------------------------------------------------------------------------
        # 1)  Sampling frequency ---------------------------------------------------
        fs = 1.0 / np.mean(np.diff(eeg_time))      # Hz

        # -------------------------------------------------------------------------
        # 2)  Welch PSD ------------------------------------------------------------
        #     • 2-s windows (nperseg = 2·fs) with 50 % overlap (noverlap = 1·fs)
        #     • detrend='constant' by default
        f, psd = welch(
            eeg_channel,
            fs=fs,
            nperseg=int(2 * fs),
            noverlap=int(1 * fs),
            window='hann',
            scaling='density'          # units: μV²/Hz if input is μV
        )

        # store PSD (first channel creates the freq vector container)
        if 'psd_data' not in results['eeg']:
            results['eeg']['psd_data'] = {}
            results['eeg']['psd_freq'] = f         # shared for all channels
        results['eeg']['psd_data'][eeg_marker] = psd

        # -------------------------------------------------------------------------
        # 3)  Band definitions and integration ------------------------------------
        bands = {
            'delta': (0.5, 4),
            'theta': (4, 8),
            'alpha': (8, 12),
            'beta':  (12, 30),
            'gamma': (30, 100)          # adjust upper limit to your Nyquist
        }

        if 'band_power' not in results['eeg']:
            results['eeg']['band_power'] = {}
        results['eeg']['band_power'][eeg_marker] = {}

        for band, (low, high) in bands.items():
            idx = (f >= low) & (f <= high)
            # integrate PSD → absolute power (μV²)
            band_power = np.trapz(psd[idx], f[idx])
            results['eeg']['band_power'][eeg_marker][band] = band_power
    for imu_marker in ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ']:
        imu_channel = muse_data['imu'][imu_marker]
        results['imu']['raw_data'][imu_marker] = imu_channel
    for ppg_marker in ['PPG_1', 'PPG_2']:
        ppg_channel = muse_data['ppg'][ppg_marker]
        results['ppg']['raw_data'][ppg_marker] = ppg_channel
    return results


# --- Main Execution Block ---
if __name__ == '__main__':
    input_files = {
        'muse_data': r'C:\Users\victo\Local\Projects\Labesporte\Muse\data\resting_layed.data'
    }
    processing_function(input_files)
