"""
Utility functions and classes for MusePy
"""

import numpy as np
import csv
from typing import Dict, List, Any, Optional, Union


class ColumnAccessor:
    """Accessor for DataFrame columns that provides pandas-like methods"""
    
    def __init__(self, data: np.ndarray, name: str):
        self._data = data
        self._name = name
    
    def diff(self, periods=1):
        """Calculate the difference between consecutive elements"""
        if len(self._data) <= periods:
            return ColumnAccessor(np.array([]), f"{self._name}_diff")
        else:
            diff_data = np.diff(self._data, n=periods)
            # Pad with NaN values at the beginning
            padded = np.full(len(self._data), np.nan)
            padded[periods:] = diff_data
            return ColumnAccessor(padded, f"{self._name}_diff")
    
    def dropna(self):
        """Remove NaN values"""
        filtered_data = self._data[~np.isnan(self._data)]
        return ColumnAccessor(filtered_data, f"{self._name}_clean")
    
    def mean(self):
        """Calculate mean"""
        return np.mean(self._data)
    
    def max(self):
        """Calculate maximum"""
        return np.max(self._data)
    
    def min(self):
        """Calculate minimum"""
        return np.min(self._data)
    
    def to_numpy(self):
        """Convert to numpy array"""
        return self._data.copy()
    
    def __getitem__(self, index):
        """Support indexing like df['col'][0]"""
        return self._data[index]
    
    def __len__(self):
        """Support len()"""
        return len(self._data)
    
    def __array__(self, dtype=None, copy=False):
        """Support numpy array conversion"""
        if copy:
            return self._data.copy()
        return self._data
    
    def __add__(self, other):
        """Support addition operations"""
        return self._data + other
    
    def __sub__(self, other):
        """Support subtraction operations"""
        return self._data - other
    
    def __mul__(self, other):
        """Support multiplication operations"""
        return self._data * other
    
    def __truediv__(self, other):
        """Support division operations"""
        return self._data / other
    
    def __radd__(self, other):
        """Support reverse addition operations"""
        return other + self._data
    
    def __rsub__(self, other):
        """Support reverse subtraction operations"""
        return other - self._data
    
    def __rmul__(self, other):
        """Support reverse multiplication operations"""
        return other * self._data
    
    def __rtruediv__(self, other):
        """Support reverse division operations"""
        return other / self._data
    
    @property
    def iloc(self):
        """Support iloc-style indexing on columns"""
        return ColumnILocIndexer(self)


class ColumnILocIndexer:
    """Indexer for iloc-style access on columns"""
    
    def __init__(self, column_accessor):
        self._col = column_accessor
    
    def __getitem__(self, index):
        """Get element by integer position"""
        if isinstance(index, int):
            if index < 0:
                index = len(self._col._data) + index
            if index < 0 or index >= len(self._col._data):
                raise IndexError("Index out of range")
            return self._col._data[index]
        else:
            return self._col._data[index]


class ILocIndexer:
    """Indexer for iloc-style access"""
    
    def __init__(self, dataframe):
        self._df = dataframe
    
    def __getitem__(self, indices):
        """Get rows by integer position or 2D indexing [row, col]"""
        if isinstance(indices, tuple) and len(indices) == 2:
            # 2D indexing: [row, col]
            row_idx, col_idx = indices
            
            # Handle negative row indexing
            if row_idx < 0:
                row_idx = len(self._df) + row_idx
            if row_idx < 0 or row_idx >= len(self._df):
                raise IndexError("Row index out of range")
            
            # Handle negative column indexing
            if col_idx < 0:
                col_idx = len(self._df._columns) + col_idx
            if col_idx < 0 or col_idx >= len(self._df._columns):
                raise IndexError("Column index out of range")
            
            # Get the column name
            col_name = self._df._columns[col_idx]
            
            # Return the specific value
            return self._df._data[col_name][row_idx]
        
        elif isinstance(indices, int):
            # Single row access
            if indices < 0:
                indices = len(self._df) + indices
            if indices < 0 or indices >= len(self._df):
                raise IndexError("Index out of range")
            
            result_data = {}
            for col in self._df._columns:
                result_data[col] = np.array([self._df._data[col][indices]])
            return FastDataFrame(result_data)
        else:
            # Multiple row access
            if self._df.empty:
                return FastDataFrame()
            
            result_data = {}
            for col in self._df._columns:
                result_data[col] = self._df._data[col][indices]
            return FastDataFrame(result_data)


class FastDataFrame:
    """
    Lightweight DataFrame replacement using numpy arrays and dictionaries.
    Much faster than pandas for basic operations and smaller memory footprint.
    """
    
    def __init__(self, data: Optional[Union[Dict, List, np.ndarray]] = None, 
                 columns: Optional[List[str]] = None, **kwargs):
        """
        Initialize FastDataFrame
        
        Args:
            data: Dictionary of column data, list of lists, or numpy array
            columns: Column names (required if data is array or list)
        """
        self._data = {}
        self._columns = []
        
        if data is not None:
            if isinstance(data, dict):
                # Dictionary input
                self._columns = list(data.keys())
                for col in self._columns:
                    # Handle ColumnAccessor objects
                    if isinstance(data[col], ColumnAccessor):
                        self._data[col] = data[col]._data
                    else:
                        self._data[col] = np.array(data[col])
            elif isinstance(data, (list, tuple)):
                # Check if it's a list of dictionaries (like pandas DataFrame([dict]))
                if len(data) > 0 and isinstance(data[0], dict):
                    # List of dictionaries - convert to DataFrame format
                    all_keys = set()
                    for item in data:
                        all_keys.update(item.keys())
                    
                    self._columns = list(all_keys)
                    for col in self._columns:
                        values = [item.get(col, None) for item in data]
                        # Handle ColumnAccessor objects in the list
                        processed_values = []
                        for val in values:
                            if isinstance(val, ColumnAccessor):
                                processed_values.append(val._data)
                            else:
                                processed_values.append(val)
                        self._data[col] = np.array(processed_values)
                else:
                    # Regular list/tuple input
                    # Check if columns is provided as keyword argument
                    if columns is None and 'columns' in kwargs:
                        columns = kwargs['columns']
                    
                    if columns is None:
                        raise ValueError("columns must be provided when data is array-like")
                    data_array = np.array(data)
                    if data_array.ndim == 1:
                        data_array = data_array.reshape(-1, 1)
                    elif data_array.ndim == 2 and data_array.shape[0] == len(columns):
                        # Transpose if needed (rows=columns)
                        data_array = data_array.T
                    
                    self._columns = columns
                    for i, col in enumerate(columns):
                        if i < data_array.shape[1]:
                            self._data[col] = data_array[:, i]
                        else:
                            self._data[col] = np.array([])
            elif isinstance(data, np.ndarray):
                # Numpy array input
                # Check if columns is provided as keyword argument
                if columns is None and 'columns' in kwargs:
                    columns = kwargs['columns']
                
                if columns is None:
                    raise ValueError("columns must be provided when data is array-like")
                data_array = data
                if data_array.ndim == 1:
                    data_array = data_array.reshape(-1, 1)
                elif data_array.ndim == 2 and data_array.shape[0] == len(columns):
                    # Transpose if needed (rows=columns)
                    data_array = data_array.T
                
                self._columns = columns
                for i, col in enumerate(columns):
                    if i < data_array.shape[1]:
                        self._data[col] = data_array[:, i]
                    else:
                        self._data[col] = np.array([])
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")
    
    @property
    def columns(self):
        """Get column names"""
        return self._columns.copy()
    
    @property
    def shape(self):
        """Get shape (rows, columns)"""
        if not self._columns:
            return (0, 0)
        
        # Get the first column to determine row count
        first_col = self._data[self._columns[0]]
        try:
            # Try to get length of the first column
            row_count = len(first_col)
        except TypeError:
            # If it's a scalar or unsized object, treat as single row
            row_count = 1
        
        return (row_count, len(self._columns))
    
    @property
    def empty(self):
        """Check if DataFrame is empty"""
        return len(self._columns) == 0 or self.shape[0] == 0
    
    def __len__(self):
        """Get number of rows"""
        return self.shape[0]
    
    def __getitem__(self, key):
        """Get column or slice of DataFrame"""
        if isinstance(key, str):
            # Single column - return ColumnAccessor for pandas-like methods
            return ColumnAccessor(self._data[key], key)
        elif isinstance(key, list):
            # Multiple columns
            return FastDataFrame({col: self._data[col] for col in key})
        elif isinstance(key, np.ndarray) and key.dtype == bool:
            # Boolean indexing - return new FastDataFrame with selected rows
            if len(key) != self.shape[0]:
                raise ValueError(f"Boolean index length ({len(key)}) does not match DataFrame length ({self.shape[0]})")
            
            # Create new FastDataFrame with filtered data
            filtered_data = {}
            for col in self._columns:
                filtered_data[col] = self._data[col][key]
            return FastDataFrame(filtered_data)
        else:
            raise KeyError(f"Unsupported key type: {type(key)}")
    
    def __setitem__(self, key, value):
        """Set column data"""
        if isinstance(key, str):
            # Handle ColumnAccessor objects
            if isinstance(value, ColumnAccessor):
                self._data[key] = value._data
            else:
                self._data[key] = np.array(value)
            if key not in self._columns:
                self._columns.append(key)
        else:
            raise KeyError(f"Unsupported key type: {type(key)}")
    
    def __contains__(self, key):
        """Check if column exists"""
        return key in self._columns
    
    def get(self, key, default=None):
        """Get column with default value"""
        return self._data.get(key, default)
    
    def to_dict(self, orient='dict'):
        """Convert to dictionary"""
        if orient == 'dict':
            return {col: self._data[col].tolist() for col in self._columns}
        elif orient == 'records':
            return [dict(zip(self._columns, row)) for row in zip(*[self._data[col] for col in self._columns])]
        else:
            raise ValueError(f"Unsupported orient: {orient}")
    
    def to_csv(self, filepath, index=False, **kwargs):
        """Save to CSV file"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow(self._columns)
            # Write data
            if self._columns:
                for row in zip(*[self._data[col] for col in self._columns]):
                    writer.writerow(row)
    
    def head(self, n=5):
        """Get first n rows"""
        if self.empty:
            return FastDataFrame()
        
        result_data = {}
        for col in self._columns:
            result_data[col] = self._data[col][:n]
        return FastDataFrame(result_data)
    
    def tail(self, n=5):
        """Get last n rows"""
        if self.empty:
            return FastDataFrame()
        
        result_data = {}
        for col in self._columns:
            result_data[col] = self._data[col][-n:]
        return FastDataFrame(result_data)
    
    def max(self):
        """Get maximum value for each column"""
        if self.empty:
            return {}
        return {col: np.max(self._data[col]) for col in self._columns}
    
    def min(self):
        """Get minimum value for each column"""
        if self.empty:
            return {}
        return {col: np.min(self._data[col]) for col in self._columns}
    
    def mean(self):
        """Get mean value for each column"""
        if self.empty:
            return {}
        return {col: np.mean(self._data[col]) for col in self._columns}
    
    def iloc(self, row_indices):
        """Get rows by integer position"""
        if self.empty:
            return FastDataFrame()
        
        result_data = {}
        for col in self._columns:
            result_data[col] = self._data[col][row_indices]
        return FastDataFrame(result_data)
    
    def copy(self):
        """Create a copy of the DataFrame"""
        result_data = {}
        for col in self._columns:
            result_data[col] = self._data[col].copy()
        return FastDataFrame(result_data)
    
    def diff(self, periods=1):
        """Calculate the difference between consecutive elements"""
        result_data = {}
        for col in self._columns:
            data = self._data[col]
            if len(data) <= periods:
                result_data[col] = np.array([])
            else:
                diff_data = np.diff(data, n=periods)
                # Pad with NaN values at the beginning
                padded = np.full(len(data), np.nan)
                padded[periods:] = diff_data
                result_data[col] = padded
        return FastDataFrame(result_data)
    
    def dropna(self):
        """Remove rows with NaN values"""
        if self.empty:
            return FastDataFrame()
        
        # Find rows without NaN values
        valid_rows = np.ones(len(self), dtype=bool)
        for col in self._columns:
            valid_rows &= ~np.isnan(self._data[col])
        
        result_data = {}
        for col in self._columns:
            result_data[col] = self._data[col][valid_rows]
        return FastDataFrame(result_data)
    
    @property
    def iloc(self):
        """Get rows by integer position (pandas-style iloc)"""
        return ILocIndexer(self)
    
    def sort_values(self, by, ascending=True):
        """Sort DataFrame by one or more columns"""
        if self.empty:
            return self.copy()
        
        if isinstance(by, str):
            by = [by]
        
        # Get sort keys
        sort_keys = []
        for col in by:
            if col not in self._columns:
                raise KeyError(f"Column '{col}' not found")
            sort_keys.append(self._data[col])
        
        # Create indices for sorting
        if len(sort_keys) == 1:
            sort_indices = np.argsort(sort_keys[0], kind='mergesort')
        else:
            # Multi-column sort
            sort_indices = np.lexsort([sort_keys[i] for i in range(len(sort_keys)-1, -1, -1)])
        
        if not ascending:
            sort_indices = sort_indices[::-1]
        
        # Create sorted result
        result_data = {}
        for col in self._columns:
            result_data[col] = self._data[col][sort_indices]
        
        return FastDataFrame(result_data)
    
    def to_numpy(self):
        """Convert DataFrame to numpy array"""
        if self.empty:
            return np.array([])
        
        # Stack all columns into a 2D array
        arrays = [self._data[col] for col in self._columns]
        return np.column_stack(arrays)
    
    @property
    def T(self):
        """Transpose the DataFrame"""
        if self.empty:
            return FastDataFrame()
        
        # Get all data as arrays
        arrays = []
        column_names = []
        for col in self._columns:
            arrays.append(self._data[col])
            column_names.append(col)
        
        # Stack arrays and transpose
        stacked = np.column_stack(arrays)
        transposed = stacked.T
        
        # Create new DataFrame with transposed data
        # Use row indices as column names
        new_data = {}
        for i, row in enumerate(transposed):
            new_data[i] = row
        
        return FastDataFrame(new_data)
    
    def rename(self, columns=None, inplace=False):
        """Rename columns"""
        if columns is None:
            return self if inplace else self.copy()
        
        if inplace:
            # Rename columns in place
            new_data = {}
            new_columns = []
            for old_col in self._columns:
                new_col = columns.get(old_col, old_col)
                new_data[new_col] = self._data[old_col]
                new_columns.append(new_col)
            self._data = new_data
            self._columns = new_columns
            return self
        else:
            # Return new DataFrame with renamed columns
            new_data = {}
            new_columns = []
            for old_col in self._columns:
                new_col = columns.get(old_col, old_col)
                new_data[new_col] = self._data[old_col].copy()
                new_columns.append(new_col)
            return FastDataFrame(new_data)
    
    def reset_index(self, inplace=False, drop=False):
        """Reset index by moving index to a column or dropping it"""
        if drop:
            # If drop=True, just return a copy of the current DataFrame (no index column added)
            if inplace:
                return self
            else:
                # Return new DataFrame with same data but no index column
                new_data = {}
                for col in self._columns:
                    new_data[col] = self._data[col].copy()
                return FastDataFrame(new_data)
        else:
            # Original behavior - add index as first column
            if inplace:
                # Add index as first column
                index_data = np.arange(len(self))
                new_data = {'index': index_data}
                new_columns = ['index']
                
                # Add existing columns
                for col in self._columns:
                    new_data[col] = self._data[col]
                    new_columns.append(col)
                
                self._data = new_data
                self._columns = new_columns
                return self
            else:
                # Return new DataFrame with reset index
                index_data = np.arange(len(self))
                new_data = {'index': index_data}
                new_columns = ['index']
                
                # Add existing columns
                for col in self._columns:
                    new_data[col] = self._data[col].copy()
                    new_columns.append(col)
                
                return FastDataFrame(new_data)
    
    def round(self, decimals=0):
        """Round values to specified number of decimal places"""
        if self.empty:
            return FastDataFrame()
        
        new_data = {}
        for col in self._columns:
            col_data = self._data[col]
            
            # Check if column contains arrays of dictionaries
            if (len(col_data) > 0 and 
                isinstance(col_data[0], dict) and 
                col_data.dtype == object):
                # Handle arrays of dictionaries
                rounded_dicts = []
                for item in col_data:
                    if isinstance(item, dict):
                        rounded_dict = {}
                        for key, value in item.items():
                            if isinstance(value, (int, float, np.number)):
                                rounded_dict[key] = round(float(value), decimals)
                            else:
                                rounded_dict[key] = value
                        rounded_dicts.append(rounded_dict)
                    else:
                        rounded_dicts.append(item)
                new_data[col] = np.array(rounded_dicts, dtype=object)
            else:
                # Handle regular numeric arrays
                try:
                    new_data[col] = np.round(col_data, decimals=decimals)
                except (TypeError, ValueError):
                    # If rounding fails, keep original data
                    new_data[col] = col_data
        
        return FastDataFrame(new_data)
    
    def __str__(self):
        """String representation"""
        if self.empty:
            return "Empty FastDataFrame"
        
        # Get first few rows for display
        display_rows = min(5, len(self))
        lines = []
        
        # Header
        header = "  ".join(f"{col:>12}" for col in self._columns)
        lines.append(header)
        lines.append("-" * len(header))
        
        # Data rows
        for i in range(display_rows):
            row_data = []
            for col in self._columns:
                value = self._data[col][i]
                if isinstance(value, float):
                    row_data.append(f"{value:>12.3f}")
                else:
                    row_data.append(f"{str(value):>12}")
            lines.append("  ".join(row_data))
        
        if len(self) > display_rows:
            lines.append(f"... ({len(self) - display_rows} more rows)")
        
        return "\n".join(lines)
    
    def __repr__(self):
        return f"FastDataFrame(shape={self.shape}, columns={self._columns})"


def read_csv(filepath: str, **kwargs) -> FastDataFrame:
    """
    Read CSV file into FastDataFrame
    
    Args:
        filepath: Path to CSV file
        **kwargs: Additional arguments (ignored for compatibility)
    
    Returns:
        FastDataFrame object
    """
    data = {}
    columns = []
    
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        # Read header
        header = next(reader, None)
        if header is None:
            return FastDataFrame()
        
        columns = header
        for col in columns:
            data[col] = []
        
        # Read data rows
        for row in reader:
            for i, value in enumerate(row):
                if i < len(columns):
                    # Try to convert to float, fallback to string
                    try:
                        data[columns[i]].append(float(value))
                    except ValueError:
                        data[columns[i]].append(value)
    
    # Convert lists to numpy arrays
    for col in columns:
        data[col] = np.array(data[col])
    
    return FastDataFrame(data)


def merge_asof(left: FastDataFrame, right: FastDataFrame, on: str, 
               direction: str = 'backward', suffixes: tuple = ('', '_right')) -> FastDataFrame:
    """
    Perform an asof merge (forward-fill merge) between two FastDataFrames
    
    Args:
        left: Left FastDataFrame (should be sorted by 'on' column)
        right: Right FastDataFrame (should be sorted by 'on' column)
        on: Column name to merge on (must exist in both DataFrames)
        direction: 'backward', 'forward', or 'nearest' (default: 'backward')
        suffixes: Tuple of suffixes for overlapping columns (default: ('', '_right'))
    
    Returns:
        Merged FastDataFrame
    """
    if left.empty:
        return FastDataFrame()
    if right.empty:
        return left.copy()
    
    if on not in left.columns or on not in right.columns:
        raise ValueError(f"Column '{on}' not found in both DataFrames")
    
    # Get the key columns as numpy arrays
    left_keys = np.array(left._data[on])
    right_keys = np.array(right._data[on])
    
    # Find matching indices for each left key
    result_data = {}
    
    # Copy all columns from left DataFrame
    for col in left.columns:
        result_data[col] = left._data[col].copy()
    
    # Find matches and merge right DataFrame columns
    for col in right.columns:
        if col == on:
            # Skip the key column (already in result)
            continue
        
        # Determine the result column name (handle suffixes)
        if col in left.columns:
            result_col = f"{col}{suffixes[1]}" if suffixes[1] else f"{col}_right"
        else:
            result_col = col
        
        # Get the right column data
        right_col_data = right._data[col]
        right_dtype = right_col_data.dtype
        
        # Initialize result column with appropriate dtype and NaN values
        if np.issubdtype(right_dtype, np.number):
            result_values = np.full(len(left_keys), np.nan, dtype=right_dtype)
        else:
            # For non-numeric types, use object dtype
            result_values = np.full(len(left_keys), None, dtype=object)
        
        # For each left key, find the matching right value
        for i, left_key in enumerate(left_keys):
            if direction == 'nearest':
                # Find the nearest match
                diffs = np.abs(right_keys - left_key)
                nearest_idx = np.argmin(diffs)
                result_values[i] = right_col_data[nearest_idx]
            elif direction == 'backward':
                # Find the last right key <= left key
                mask = right_keys <= left_key
                if np.any(mask):
                    # Get the last matching index
                    matching_indices = np.where(mask)[0]
                    nearest_idx = matching_indices[-1]
                    result_values[i] = right_col_data[nearest_idx]
            elif direction == 'forward':
                # Find the first right key >= left key
                mask = right_keys >= left_key
                if np.any(mask):
                    # Get the first matching index
                    matching_indices = np.where(mask)[0]
                    nearest_idx = matching_indices[0]
                    result_values[i] = right_col_data[nearest_idx]
            else:
                raise ValueError(f"Unsupported direction: {direction}")
        
        result_data[result_col] = result_values
    
    return FastDataFrame(result_data)


def concat(dataframes: List[FastDataFrame], ignore_index: bool = False) -> FastDataFrame:
    """
    Concatenate multiple FastDataFrames
    
    Args:
        dataframes: List of FastDataFrame objects
        ignore_index: Whether to ignore index (always True for FastDataFrame)
    
    Returns:
        Concatenated FastDataFrame
    """
    if not dataframes:
        return FastDataFrame()
    
    # Filter out empty DataFrames
    non_empty_dfs = [df for df in dataframes if not df.empty]
    
    if not non_empty_dfs:
        return FastDataFrame()
    
    if len(non_empty_dfs) == 1:
        return non_empty_dfs[0].copy()
    
    # Check that all non-empty DataFrames have the same columns
    first_columns = non_empty_dfs[0].columns
    for df in non_empty_dfs[1:]:
        if df.columns != first_columns:
            raise ValueError("All DataFrames must have the same columns")
    
    # Concatenate data
    result_data = {}
    for col in first_columns:
        arrays = [df._data[col] for df in non_empty_dfs]
        if arrays:
            result_data[col] = np.concatenate(arrays)
        else:
            result_data[col] = np.array([])
    
    return FastDataFrame(result_data)


# Create aliases for compatibility
DataFrame = FastDataFrame

class PandasCompat:
    """Compatibility class to mimic pandas interface"""
    DataFrame = FastDataFrame
    
    @staticmethod
    def read_csv(filepath, **kwargs):
        return read_csv(filepath, **kwargs)
    
    @staticmethod
    def concat(dataframes, ignore_index=False):
        return concat(dataframes, ignore_index)
    
    @staticmethod
    def merge_asof(left, right, on, direction='backward', suffixes=('', '_right')):
        return merge_asof(left, right, on, direction, suffixes)

pd = PandasCompat()