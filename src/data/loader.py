"""
F1 Data Loader
Manages FastF1 session downloads, caching, and telemetry extraction.
Resamples telemetry to 100ms intervals for consistent simulation timing.
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import fastf1 as ff1
import numpy as np
import pandas as pd
from scipy import interpolate


class F1DataLoader:
    """
    Handles all FastF1 data loading with intelligent caching.
    Provides resampled telemetry at 100ms intervals for simulation.
    """
    
    # Available years for the simulator
    AVAILABLE_YEARS = [2022, 2023, 2024, 2025]
    
    def __init__(self, cache_dir: str = "./cache"):
        """
        Initialize the data loader with cache directory.
        
        Args:
            cache_dir: Directory for FastF1 cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Enable FastF1 cache
        ff1.Cache.enable_cache(str(self.cache_dir))
        
        self._current_session: Optional[ff1.core.Session] = None
    
    def load_session(self, year: int, gp: str, session_type: str = 'R') -> ff1.core.Session:
        """
        Load a race session from FastF1.
        
        Args:
            year: Season year (2022-2025)
            gp: Grand Prix name or round number
            session_type: Session identifier ('R' for Race, 'Q' for Quali, etc.)
            
        Returns:
            Loaded FastF1 Session object
        """
        print(f"Loading session: {year} {gp} - {session_type}...")
        session = ff1.get_session(year, gp, session_type)
        session.load()
        self._current_session = session
        print(f"Session loaded: {session.event['EventName']}")
        return session
    
    def get_driver_telemetry(
        self, 
        session: ff1.core.Session, 
        driver: str,
        resample_interval_ms: int = 100
    ) -> pd.DataFrame:
        """
        Extract driver telemetry and resample to consistent intervals.
        
        Args:
            session: Loaded FastF1 session
            driver: Driver code (e.g., 'VER', 'HAM', 'LEC')
            resample_interval_ms: Resample interval in milliseconds (default 100ms)
            
        Returns:
            DataFrame with columns: Time, X, Y, Speed, nGear, Throttle, Brake
            Resampled to uniform time intervals
        """
        # Get driver laps
        driver_laps = session.laps.pick_driver(driver)
        
        if driver_laps.empty:
            raise ValueError(f"No lap data found for driver {driver}")
        
        # Get fastest lap for clean telemetry (or first complete lap)
        try:
            reference_lap = driver_laps.pick_fastest()
        except Exception:
            # Fall back to first lap if no fastest available
            reference_lap = driver_laps.iloc[0]
        
        # Get telemetry for this lap
        telemetry = reference_lap.get_telemetry()
        
        if telemetry.empty:
            raise ValueError(f"No telemetry data for driver {driver}")
        
        # Resample to consistent 100ms intervals using scipy interpolation
        resampled = self._resample_telemetry(telemetry, resample_interval_ms)
        
        return resampled
    
    def get_all_drivers_telemetry(
        self,
        session: ff1.core.Session,
        resample_interval_ms: int = 100,
        progress_callback=None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load telemetry for ALL drivers in the session.
        
        Args:
            session: Loaded FastF1 session
            resample_interval_ms: Resample interval in milliseconds
            progress_callback: Optional callback(driver_code, current, total) for progress
            
        Returns:
            Dictionary mapping driver_code -> telemetry DataFrame
        """
        all_telemetry = {}
        drivers = self.get_drivers(session)
        total = len(drivers)
        
        for i, (driver_code, driver_name) in enumerate(drivers):
            if progress_callback:
                progress_callback(driver_code, i + 1, total)
            
            try:
                telemetry = self.get_driver_telemetry(session, driver_code, resample_interval_ms)
                if not telemetry.empty and len(telemetry) > 100:
                    all_telemetry[driver_code] = telemetry
                    print(f"  Loaded {driver_code}: {len(telemetry)} points")
            except Exception as e:
                print(f"  Skipping {driver_code}: {e}")
                continue
        
        return all_telemetry
    
    def _resample_telemetry(
        self, 
        telemetry: pd.DataFrame, 
        interval_ms: int
    ) -> pd.DataFrame:
        """
        Resample telemetry to uniform time intervals using scipy interpolation.
        
        Args:
            telemetry: Raw telemetry DataFrame
            interval_ms: Target interval in milliseconds
            
        Returns:
            Resampled DataFrame with uniform time spacing
        """
        # Convert Time to milliseconds for easier processing
        if 'Time' in telemetry.columns:
            time_ms = telemetry['Time'].dt.total_seconds() * 1000
        elif 'SessionTime' in telemetry.columns:
            time_ms = telemetry['SessionTime'].dt.total_seconds() * 1000
        else:
            # Create synthetic time from index
            time_ms = np.arange(len(telemetry)) * 50  # Assume 50ms default
        
        time_ms = time_ms.values
        
        # Create new uniform time array
        new_time_ms = np.arange(time_ms[0], time_ms[-1], interval_ms)
        
        # Columns to interpolate
        numeric_cols = ['X', 'Y', 'Speed', 'nGear', 'Throttle', 'Brake', 'RPM', 'DRS']
        available_cols = [c for c in numeric_cols if c in telemetry.columns]
        
        resampled_data = {'Time_ms': new_time_ms}
        
        for col in available_cols:
            values = telemetry[col].values
            
            # Handle NaN values
            valid_mask = ~np.isnan(values)
            if not np.any(valid_mask):
                resampled_data[col] = np.zeros(len(new_time_ms))
                continue
            
            # Create interpolation function
            # Use linear for continuous values, nearest for discrete (like Gear)
            if col in ['nGear', 'DRS']:
                interp_func = interpolate.interp1d(
                    time_ms[valid_mask], 
                    values[valid_mask], 
                    kind='nearest',
                    bounds_error=False,
                    fill_value='extrapolate'
                )
            else:
                interp_func = interpolate.interp1d(
                    time_ms[valid_mask], 
                    values[valid_mask], 
                    kind='linear',
                    bounds_error=False,
                    fill_value='extrapolate'
                )
            
            resampled_data[col] = interp_func(new_time_ms)
        
        return pd.DataFrame(resampled_data)
    
    def get_track_coordinates(self, session: ff1.core.Session) -> np.ndarray:
        """
        Extract track layout coordinates from session data.
        
        Args:
            session: Loaded FastF1 session
            
        Returns:
            numpy array of shape (N, 2) containing X, Y coordinates
        """
        # Get circuit info from fastest lap telemetry
        laps = session.laps.pick_fastest()
        
        if laps is None or (hasattr(laps, 'empty') and laps.empty):
            # Try to get any lap
            laps = session.laps.iloc[0]
        
        telemetry = laps.get_telemetry()
        
        if 'X' not in telemetry.columns or 'Y' not in telemetry.columns:
            raise ValueError("No position data in telemetry")
        
        # Extract unique track points (reduce density for smoother rendering)
        coords = telemetry[['X', 'Y']].values
        
        # Subsample for performance (every 5th point for better detail)
        coords = coords[::5]
        
        return coords
    
    def get_available_races(self, year: int) -> List[str]:
        """
        Get list of available races for a given year.
        
        Args:
            year: Season year
            
        Returns:
            List of Grand Prix names
        """
        try:
            schedule = ff1.get_event_schedule(year)
            # Filter to only completed events (have session data)
            races = schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
            return races
        except Exception as e:
            print(f"Error fetching schedule: {e}")
            return []
    
    def get_drivers(self, session: ff1.core.Session) -> List[Tuple[str, str]]:
        """
        Get list of drivers in a session.
        
        Args:
            session: Loaded FastF1 session
            
        Returns:
            List of tuples (driver_code, full_name)
        """
        drivers = []
        for drv in session.drivers:
            try:
                info = session.get_driver(drv)
                code = info['Abbreviation']
                name = f"{info['FirstName']} {info['LastName']}"
                drivers.append((code, name))
            except Exception:
                continue
        return drivers
    
    def get_lap_times(self, session: ff1.core.Session, driver: str) -> pd.DataFrame:
        """
        Get all lap times for a driver in a session.
        
        Args:
            session: Loaded FastF1 session
            driver: Driver code
            
        Returns:
            DataFrame with lap numbers and times
        """
        laps = session.laps.pick_driver(driver)
        return laps[['LapNumber', 'LapTime', 'Compound', 'TyreLife']].copy()
