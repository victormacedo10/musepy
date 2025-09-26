import matplotlib.pyplot as plt
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.utils import pd
import numpy as np
from scipy.signal import spectrogram


def plot_eeg_data(eeg_data):
    fig, ax = plt.subplots(1, 1, figsize=(3, 0.5))
    for eeg_marker in eeg_data['raw_data']:
        ax.plot(eeg_data['time'], eeg_data['raw_data'][eeg_marker], label=eeg_marker)
    ax.legend()
    return fig


def plot_imu_data(imu_data):
    fig, ax = plt.subplots(1, 2, figsize=(4, 3))
    ax[0].set_title('Accelerometer Data')
    ax[1].set_title('Gyroscope Data')
    for axis in ['x', 'y', 'z']:
        ax[0].plot(imu_data['time'], imu_data['raw_data'][f'Acc{axis.upper()}'], label=f'Acc{axis.upper()}')
        ax[1].plot(imu_data['time'], imu_data['raw_data'][f'Gyro{axis.upper()}'], label=f'Gyro{axis.upper()}')
    ax[0].legend()
    ax[1].legend()
    return fig


def plot_eeg_psd_data(eeg_data):
    fig, ax = plt.subplots(1, 1, figsize=(5, 3))
    freqs = eeg_data['psd_freq']
    for marker, psd in eeg_data['psd_data'].items():
        ax.plot(freqs, psd, label=marker)
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('PSD (µV²/Hz)')
    ax.legend()
    return fig


def plot_filtered_array(eeg_array, time, ch_names):
    fig, ax = plt.subplots(1, 1, figsize=(5, 3))
    for i, name in enumerate(ch_names):
        ax.plot(time, eeg_array[i], label=name)
        ax.legend()
    return fig


def plot_rereferenced_signals(reref_dict, time):
    fig, ax = plt.subplots(1, 1, figsize=(5, 3))
    for k, v in reref_dict.items():
        ax.plot(time, v, label=k)
        ax.legend()
    return fig


def plot_clean_mask(time, reref_signals, mask):
    fig, ax = plt.subplots(reref_signals.shape[0], 1, figsize=(8, 4), sharex=True)
    for i in range(reref_signals.shape[0]):
        ax[i].plot(time, reref_signals[i], lw=0.6)
        ax[i].set_ylabel(f"Chan {i+1}")
        for j in range(len(mask)):
            if not mask[j]:
                ax[i].axvspan(time[j], time[min(j+1, len(time)-1)], color='red', alpha=0.2)
    ax[-1].set_xlabel("Time (s)")
    return fig



def plot_spectrogram(data, fs, title):
    fig, ax = plt.subplots(figsize=(5, 3))
    f, t, Sxx = spectrogram(data, fs=fs, nperseg=fs*2, noverlap=fs, window='hann')
    ax.pcolormesh(t, f, 10*np.log10(Sxx), shading='gouraud')
    ax.set_ylabel('Frequency [Hz]')
    ax.set_xlabel('Time [sec]')
    ax.set_title(title)
    return fig



def visualization_function(inputs_dict, processing_dict):
    plt.close('all')
    output = {"plots": {}, "tables": {}}
    output["plots"]['Raw EEG Channels'] = plot_eeg_data(processing_dict['eeg'])
    output["plots"]['Raw IMU Channels'] = plot_imu_data(processing_dict['imu'])
    output["plots"]['EEG PSD Spectrum'] = plot_eeg_psd_data(processing_dict['eeg'])


    # EEG Debugging Pipeline Plots
    if 'after_notch' in processing_dict['eeg']:
        output['plots']['EEG After Notch Filter'] = plot_filtered_array(
            processing_dict['eeg']['after_notch'], processing_dict['eeg']['time'], ['TP9', 'TP10', 'AF7', 'AF8'])


    if 'after_lowpass' in processing_dict['eeg']:
        output['plots']['EEG After Lowpass Filter'] = plot_filtered_array(
            processing_dict['eeg']['after_lowpass'], processing_dict['eeg']['time'], ['TP9', 'TP10', 'AF7', 'AF8'])


    if 'after_highpass' in processing_dict['eeg']:
        output['plots']['EEG After Highpass Filter'] = plot_filtered_array(
            processing_dict['eeg']['after_highpass'], processing_dict['eeg']['time'], ['TP9', 'TP10', 'AF7', 'AF8'])


    if 'rereferenced' in processing_dict['eeg']:
        output['plots']['EEG Re-referenced Channels'] = plot_rereferenced_signals(
            processing_dict['eeg']['rereferenced'], processing_dict['eeg']['time'])


    if 'clean_mask' in processing_dict['eeg'] and 'reref_array' in processing_dict['eeg']:
        output['plots']['EEG Artifact Rejection Mask'] = plot_clean_mask(
            processing_dict['eeg']['time'], processing_dict['eeg']['reref_array'], processing_dict['eeg']['clean_mask'])

    # Spectrograms
    if 'raw_data' in processing_dict['eeg']:
        for ch_name, ch_data in processing_dict['eeg']['raw_data'].items():
            fig = plot_spectrogram(ch_data, fs=256, title=f'Spectrogram (Raw) - {ch_name}')
            output['plots'][f'Spectrogram (Raw) - {ch_name}'] = fig


    if 'rereferenced' in processing_dict['eeg']:
        for ch_name, ch_data in processing_dict['eeg']['rereferenced'].items():
            fig = plot_spectrogram(ch_data, fs=256, title=f'Spectrogram (Filtered) - {ch_name}')
            output['plots'][f'Spectrogram (Filtered) - {ch_name}'] = fig

    # create dataframe for EEG band power (absolute power from PSD)
    eeg_bp = processing_dict['eeg']['band_power']
    
    # Convert the nested dictionary structure to a proper DataFrame
    # eeg_bp structure: {'channel_name': {'delta': value, 'theta': value, ...}}
    # We want: rows = channels, columns = frequency bands
    
    # First, create a list of dictionaries for each channel
    # Define the order of frequency bands (progressive order)
    band_order = ['delta', 'theta', 'alpha', 'beta', 'gamma']
    
    channel_data = []
    for channel, band_powers in eeg_bp.items():
        row_data = {'Channel': channel}
        # Add frequency bands in the correct order
        for band in band_order:
            if band in band_powers:
                row_data[band] = band_powers[band]
        channel_data.append(row_data)
    
    # Create DataFrame from the list of dictionaries
    df_bp = pd.DataFrame(channel_data)
    
    # Set the correct column order: Channel first, then frequency bands in progressive order
    column_order = ['Channel'] + band_order
    df_bp = df_bp[column_order]
    
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
    
    # store table with units
    output["tables"]["EEG Bands Power (µV²)"] = df_bp.round(2)

    return output
