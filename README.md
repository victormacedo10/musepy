# MusePy - Modern EEG Data Acquisition and Analysis Tool

A user-friendly application for real-time EEG data acquisition and analysis using Muse headbands, developed at LabEsporte in the University of Brasília (UnB).

## 🚀 Features

### Data Acquisition
- **Real-time EEG streaming** from Muse 2 headbands
- **Live visualization** with customizable channel display
- **Configurable recording window** (1-60 seconds)
- **Multi-format data export** (CSV, pickle)
- **Demo mode** for testing without hardware

### Data Analysis
- **Modular processing pipeline** with custom script support
- **Flexible experiment framework** for custom analysis workflows
- **Interactive plotting** with matplotlib integration
- **Data table visualization** with pandas DataFrame support
- **Session management** for saving/loading analysis states

### Robust Architecture
- **Background processing** with worker threads for non-blocking operations
- **Error handling** with comprehensive exception management
- **Configuration management** with centralized settings
- **Modular design** with separated concerns and reusable components

## 📋 Requirements

- Python 3.8+
- PySide6
- BrainFlow
- PyQtGraph
- Matplotlib
- Pandas
- NumPy

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd musepy
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
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
   ```bash
   python app.py --demo
   ```

### Data Recording

1. **Connect to Muse headband:**
   - Click "Connect" button
   - Wait for connection confirmation
   - Status bar will show "🟢 Connected"

2. **Start recording:**
   - Click "Start Recording" to begin data acquisition
   - Real-time EEG data will appear in the Stream tab
   - Toggle individual channels on/off using checkboxes

3. **Save recording:**
   - Click "Stop Recording" when finished
   - Choose to save or discard the recording
   - Data is automatically saved as CSV and pickle files

### Data Analysis

1. **Load data:**
   - Use "Input Data" section to load recorded or external data
   - Provide a label for the dataset

2. **Process data:**
   - Select a processing script (must define `processing_function`)
   - Click "Process Data" to run analysis

3. **Run experiments:**
   - Select an experiment script (must define `experiment_function`)
   - Click "Run Experiment" to generate results
   - View plots and tables in respective tabs

4. **Save session:**
   - Use "Session Management" to save/load analysis states
   - Sessions include all loaded data, processing results, and experiment outputs

### Processing Scripts

Create a Python file with a `processing_function`:

```python
def processing_function(inputs_dict):
    """
    Process input data and return processed results.
    
    Args:
        inputs_dict: Dictionary of {label: file_path} pairs
        
    Returns:
        dict: Processed data dictionary
    """
    processed_data = {}
    # Your processing logic here
    return processed_data
```

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
    
    # Create plots
    fig, ax = plt.subplots()
    # Your plotting logic here
    
    # Create tables
    results_table = pd.DataFrame()
    # Your table creation logic here
    
    return {
        'plots': {'My Plot': fig},
        'tables': {'Results': results_table}
    }
```

## 🔍 Troubleshooting

### Connection Issues
- Ensure Muse headband is powered on and in pairing mode
- Check Bluetooth connectivity
- Try restarting the application

### Performance Issues
- Reduce streaming window size for better performance
- Close unnecessary applications to free system resources
- Use demo mode for testing without hardware

### Script Errors
- Ensure scripts define required functions (`processing_function` or `experiment_function`)
- Check script syntax and dependencies
- Review console output for detailed error messages

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **LabEsporte UnB** for research support
- **BrainFlow** for EEG data acquisition
- **PySide6** for the modern Qt interface
- **PyQtGraph** for real-time plotting

**MusePy v2.0.0** - Modern EEG Analysis for Research and Development
