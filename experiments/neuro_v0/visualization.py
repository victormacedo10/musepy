import matplotlib.pyplot as plt
import pandas as pd


def plot_eeg_data(eeg_data):
    fig, ax = plt.subplots(1, 1, figsize=(5, 4))
    for eeg_marker in eeg_data['raw_data']:
        ax.plot(eeg_data['time'], eeg_data['raw_data'][eeg_marker], label=eeg_marker)
    ax.legend()
    return fig


def plot_imu_data(imu_data):
    fig, ax = plt.subplots(1, 2, figsize=(5, 4))
    ax[0].set_title('Accelerometer Data')
    ax[1].set_title('Gyroscope Data')
    for axis in ['x', 'y', 'z']:
        ax[0].plot(imu_data['time'], imu_data['raw_data'][f'Acc{axis.upper()}'], label=f'Acc{axis.upper()}')
        ax[1].plot(imu_data['time'], imu_data['raw_data'][f'Gyro{axis.upper()}'], label=f'Gyro{axis.upper()}')
    ax[0].legend()
    ax[1].legend()
    return fig


def plot_ppg_data(ppg_data):
    fig, ax = plt.subplots(1, 1, figsize=(5, 4))
    for ppg_marker in ppg_data['raw_data']:
        ax.plot(ppg_data['time'], ppg_data['raw_data'][ppg_marker], label=ppg_marker)
    ax.legend()
    return fig


def plot_eeg_psd_data(eeg_data):
    fig, ax = plt.subplots(1, 1, figsize=(6, 4))
    freqs = eeg_data['psd_freq']
    for marker, psd in eeg_data['psd_data'].items():
        ax.plot(freqs, psd, label=marker)
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('PSD (µV²/Hz)')
    ax.legend()
    return fig


def visualization_function(inputs_dict, processing_dict):
    plt.close('all')
    output = {"plots": {}, "tables": {}}
    output["plots"]['Raw EEG Channels'] = plot_eeg_data(processing_dict['eeg'])
    output["plots"]['Raw IMU Channels'] = plot_imu_data(processing_dict['imu'])
    output["plots"]['Raw PPG Channels'] = plot_ppg_data(processing_dict['ppg'])
    output["plots"]['EEG PSD Spectrum'] = plot_eeg_psd_data(processing_dict['eeg'])
    # create dataframe for EEG band power (absolute power from PSD)
    eeg_bp = processing_dict['eeg']['band_power']
    df_bp = pd.DataFrame(eeg_bp).T
    # rename columns to include frequency band ranges
    band_ranges = {
        'delta': (0.5, 4),
        'theta': (4, 8),
        'alpha': (8, 12),
        'beta':  (12, 30),
        'gamma': (30, 100)
    }
    rename_dict = {band: f"{band} ({low} - {high} Hz)" for band, (low, high) in band_ranges.items()}
    df_bp.rename(columns=rename_dict, inplace=True)
    # move channel names from index into a column and drop index
    df_bp.reset_index(inplace=True)
    df_bp.rename(columns={'index': 'Channel'}, inplace=True)
    # store table with units
    output["tables"]["EEG Bands Power (µV²)"] = df_bp.round(2)

    return output
