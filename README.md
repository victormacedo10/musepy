# MusePy - Modern EEG Data Acquisition and Analysis Tool

A comprehensive, user-friendly application for real-time EEG data acquisition and analysis using Muse headbands, developed at LabEsporte in the University of Brasília (UnB).

## 🚀 Features

### Data Acquisition
- **Real-time EEG streaming** from Muse headbands via Bluetooth
- **Live visualization** with customizable channel display and real-time plotting
- **Configurable recording window** (1-60 seconds) with adjustable buffer size
- **Multi-format data export** (CSV, pickle, .data files)
- **Demo mode** for testing without hardware using simulated EEG data
- **Device connection management** with automatic pairing and status monitoring
- **Recover recordings** with the ability to view and analyze previously recordings
- **Data validation** and quality checks during acquisition

### Data Analysis
- **Modular processing pipeline** with custom script support and background processing
- **Flexible experiment framework** for custom analysis workflows
- **Interactive plotting** with matplotlib integration and customizable visualizations
- **Data table visualization** with pandas DataFrame support and export capabilities
- **Session management** for saving/loading analysis states with persistent storage
- **Variable inspector** for real-time data exploration and debugging
- **Input data management** with support for multiple file formats and data sources
- **Processing results visualization** with plots and tables
- **Experiment execution** with configurable parameters and result storage

### Advanced Features
- **Background processing** with worker threads for non-blocking operations
- **Comprehensive error handling** with detailed exception management and user feedback
- **Configuration management** with centralized settings and preferences
- **Modular architecture** with separated concerns and reusable components
- **Modern Qt6 interface** with responsive design and intuitive navigation
- **Data persistence** with automatic session saving and recovery
- **Multi-threaded operations** for smooth user experience during data processing
- **Real-time data monitoring** with live updates and status indicators

### User Interface
- **Dual-panel layout** with navigation sidebar and main content area
- **Tabbed interface** for organized data presentation
- **Responsive design** that adapts to different screen sizes
- **Light theme** with consistent styling and modern aesthetics
- **Interactive controls** with real-time feedback and status updates
- **Data visualization widgets** with zoom, pan, and export capabilities

## 📋 Requirements

- **Python 3.13.7** (recommended)
- **Operating System**: Windows 10/11, macOS, or Linux
- **Hardware**: Muse headband (demo mode available with random data)

### Core Dependencies
- **NumPy 2.3.2** - Numerical computing
- **Pandas 2.3.2** - Data manipulation and analysis
- **SciPy 1.16.1** - Scientific computing
- **PySide6 6.9.2** - Modern Qt6 GUI framework
- **Matplotlib 3.10.5** - Plotting and visualization
- **PyQtGraph 0.13.7** - Real-time plotting
- **BrainFlow 5.18.1** - EEG data acquisition library

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd musepy
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 🚀 Usage

### Basic Usage

1. **Start the application:**
   ```bash
   python app.py
   ```

2. **Demo mode (without hardware):**
   The application runs in demo mode if passed the flag --demo, providing simulated EEG data for testing.

### Data Recording

1. **Connect to Muse headband:**
   - Click "Connect" button in the Data Collection panel
   - Wait for connection confirmation
   - Status indicator will show "🟢 Connected"

2. **Configure recording settings:**
   - Adjust streaming window size (1-60 seconds)
   - Select channels to display (TP9, AF7, AF8, TP10)
   - Set recording parameters

3. **Start recording:**
   - Click "Start Recording" to begin data acquisition
   - Real-time EEG data will appear in the Stream tab
   - Toggle individual channels on/off using checkboxes
   - Monitor signal quality and connection status

4. **Save recording:**
   - Click "Stop Recording" when finished
   - Choose to save or discard the recording
   - Data is automatically saved as CSV and pickle files
   - View recorded data in the View Recording tab

### Data Analysis

1. **Load data:**
   - Use "Input Data" section to load recorded or external data files
   - Support for CSV, pickle, and .data file formats
   - Provide descriptive labels for datasets
   - Monitor loaded data in the variable inspector

2. **Process data:**
   - Select a processing script from the experiments directory
   - Scripts must define a `processing_function(inputs_dict)` function
   - Click "Process Data" to run analysis in background
   - View processing results in dedicated tabs

3. **Run experiments:**
   - Select an experiment script with `experiment_function(inputs_dict, processed_data_dict)`
   - Configure experiment parameters
   - Click "Run Experiment" to generate results
   - View plots and tables in respective visualization tabs

4. **Session management:**
   - Save analysis sessions with all loaded data and results
   - Load previous sessions to continue analysis
   - Export session data for sharing or backup
   - Automatic session recovery on application restart

### Processing Scripts

Create a Python file in the `experiments/` directory with a `processing_function`:

```python
def processing_function(inputs_dict):
    """
    Process input data and return processed results.
    
    Args:
        inputs_dict: Dictionary of {label: file_path} pairs
        
    Returns:
        dict: Processed data dictionary with any structure
    """
    import pandas as pd
    import numpy as np
    import pickle
    
    processed_data = {}
    
    for label, file_path in inputs_dict.items():
        # Load data from .data file (pickle format)
        with open(file_path, 'rb') as f:
            data_dict = pickle.load(f)
        
        # Access different data types from the dictionary
        eeg_data = data_dict.get('eeg', None)
        imu_data = data_dict.get('imu', None)
        ppg_data = data_dict.get('ppg', None)
        
        # Apply processing (example: bandpass filtering)
        # Your processing logic here
        
        processed_data[label] = {
            'filtered_data': filtered_data,
            'features': extracted_features,
            'metadata': processing_info
        }
    
    return processed_data
```

**Note**: The `.data` files use a simple pickle structure to facilitate dictionary-based variable storage. This format allows storing multiple data types (EEG, IMU, PPG) and metadata in a single file, making it easy to access different components of the recorded data through dictionary keys.

### Experiment Scripts

Create a Python file with an `experiment_function`:

```python
def experiment_function(inputs_dict, processed_data_dict):
    """
    Run experiments on processed data and return results.
    
    Args:
        inputs_dict: Dictionary of {label: file_path} pairs
        processed_data_dict: Dictionary of processed data
        
    Returns:
        dict: Results with 'plots' and 'tables' keys
    """
    import matplotlib.pyplot as plt
    import pandas as pd
    
    results = {'plots': {}, 'tables': {}}
    
    # Create plots
    fig, ax = plt.subplots(figsize=(10, 6))
    # Your plotting logic here
    results['plots']['Analysis Plot'] = fig
    
    # Create tables
    results_table = pd.DataFrame({
        'Metric': ['Value1', 'Value2'],
        'Result': [result1, result2]
    })
    results['tables']['Results Summary'] = results_table
    
    return results
```

## 📁 Project Structure

```
musepy/
├── app.py                          # Main application entry point
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── data/                           # Data storage directory
│   ├── Muse_Data/                  # Sample data files
│   └── Victor/                     # User-specific data
├── experiments/                    # Analysis scripts
│   └── neuro_v0/                   # Example experiment
│       ├── processing.py           # Data processing functions
│       └── visualization.py        # Visualization functions
├── sessions/                       # Session files
└── src/                           # Source code
    ├── data_collection/            # Data acquisition modules
    │   ├── acquisition_plot_widget.py
    │   ├── connect_device_widget.py
    │   ├── data_collection_widget.py
    │   ├── record_data_widget.py
    │   └── view_recording_widget.py
    ├── data_analysis/              # Data analysis modules
    │   └── data_analysis_widget.py
    └── utils.py                    # Utility functions
```

## 🔍 Troubleshooting

### Connection Issues
- Ensure Muse headband is powered on and in pairing mode
- Check Bluetooth connectivity and device visibility
- Try restarting the application and re-pairing the device
- Verify BrainFlow installation and compatibility

### Performance Issues
- Reduce streaming window size for better performance
- Close unnecessary applications to free system resources
- Use demo mode for testing without hardware
- Monitor system memory usage during long recording sessions

### Script Errors
- Ensure scripts define required functions (`processing_function` or `experiment_function`)
- Check script syntax and dependencies
- Review console output for detailed error messages
- Verify data file formats and paths

### GUI Issues
- Update graphics drivers for better Qt6 compatibility
- Check display scaling settings on high-DPI displays
- Restart application if interface becomes unresponsive

## 🧪 Testing

The application includes comprehensive testing capabilities:

- **Demo mode** for testing without hardware
- **Sample data** in the `data/Muse_Data/` directory
- **Example scripts** in the `experiments/neuro_v0/` directory
- **Session management** for saving and loading test states

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with proper documentation
4. Add tests if applicable
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add docstrings to all functions and classes
- Include type hints for better code documentation
- Test new features thoroughly before submitting

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **LabEsporte UnB** for research support and development environment
- **BrainFlow** for robust EEG data acquisition capabilities
- **PySide6** for the modern Qt6 interface framework
- **PyQtGraph** for high-performance real-time plotting
- **Matplotlib** for comprehensive data visualization
- **Pandas & NumPy** for efficient data processing

## 📊 Version Information

**MusePy v2.1.0** - Modern EEG Analysis for Research and Development
- **Python Version**: 3.13.7
- **Qt Version**: 6.9.2
- **Last Updated**: January 2025

---

*Developed with ❤️ at LabEsporte, University of Brasília*
