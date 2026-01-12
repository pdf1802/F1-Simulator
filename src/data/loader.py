"""
F1 Data Loader
Manages FastF1 session downloads, caching, and telemetry extraction.
Now loads FULL RACE data for authentic "What-If" simulation.
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

import fastf1 as ff1
import numpy as np
import pandas as pd
from scipy import interpolate


@dataclass
class LapData:
    """Data for a single lap."""
    lap_number: int
    lap_time_seconds: float
    compound: str
    tire_life: int
    is_pit_out: bool
    is_pit_in: bool
    position: int
    telemetry: Optional[pd.DataFrame] = None


@dataclass 
class DriverRaceData:
    """Complete race data for a single driver."""
    driver_code: str
    driver_name: str
    team: str
    team_color: Tuple[int, int, int]
    laps: List[LapData]
    final_position: int
    total_laps: int
    
    def get_position_at_lap(self, lap: int) -> int:
        """Get driver's position at a specific lap."""
        for lap_data in self.laps:
            if lap_data.lap_number == lap:
                return lap_data.position
        return self.final_position
    
    def get_compound_at_lap(self, lap: int) -> str:
        """Get tire compound at specific lap."""
        for lap_data in self.laps:
            if lap_data.lap_number == lap:
                return lap_data.compound
        return "UNKNOWN"
    
    def get_pit_stops(self) -> List[int]:
        """Get list of laps where driver pitted."""
        return [lap.lap_number for lap in self.laps if lap.is_pit_in]


# Team colors for rendering
TEAM_COLORS = {
    'red_bull': (30, 65, 255),
    'mercedes': (0, 210, 190),
    'ferrari': (220, 0, 0),
    'mclaren': (255, 135, 0),
    'aston_martin': (0, 110, 70),
    'alpine': (0, 144, 255),
    'alphatauri': (102, 146, 255),
    'rb': (102, 146, 255),
    'alfa': (155, 0, 0),
    'sauber': (155, 0, 0),
    'williams': (100, 196, 237),
    'haas': (182, 186, 189),
}


class F1DataLoader:
    """
    Handles all FastF1 data loading with intelligent caching.
    Loads FULL RACE data for What-If simulation.
    """
    
    AVAILABLE_YEARS = [2022, 2023, 2024, 2025]
    
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        ff1.Cache.enable_cache(str(self.cache_dir))
        self._current_session: Optional[ff1.core.Session] = None
    
    def load_session(self, year: int, gp: str, session_type: str = 'R') -> ff1.core.Session:
        """Load a race session from FastF1."""
        print(f"Loading session: {year} {gp} - {session_type}...")
        session = ff1.get_session(year, gp, session_type)
        session.load()
        self._current_session = session
        print(f"Session loaded: {session.event['EventName']}")
        return session
    
    def load_full_race_data(
        self,
        session: ff1.core.Session,
        progress_callback=None
    ) -> Dict[str, DriverRaceData]:
        """
        Load COMPLETE race data for ALL drivers.
        Includes all laps, pit stops, positions, and tire compounds.
        
        Returns:
            Dictionary mapping driver_code -> DriverRaceData
        """
        all_drivers_data = {}
        drivers = self.get_drivers(session)
        total = len(drivers)
        
        for i, (driver_code, driver_name) in enumerate(drivers):
            if progress_callback:
                progress_callback(driver_code, i + 1, total)
            
            try:
                driver_data = self._load_driver_race_data(session, driver_code, driver_name)
                if driver_data and len(driver_data.laps) > 0:
                    all_drivers_data[driver_code] = driver_data
                    print(f"  Loaded {driver_code}: {len(driver_data.laps)} laps, P{driver_data.final_position}")
            except Exception as e:
                print(f"  Error loading {driver_code}: {e}")
                continue
        
        return all_drivers_data
    
    def _load_driver_race_data(
        self, 
        session: ff1.core.Session, 
        driver_code: str,
        driver_name: str
    ) -> Optional[DriverRaceData]:
        """Load complete race data for a single driver."""
        driver_laps = session.laps.pick_driver(driver_code)
        
        if driver_laps.empty:
            return None
        
        # Get driver info
        try:
            driver_info = session.get_driver(driver_code)
            team = driver_info.get('TeamName', 'Unknown')
            team_key = team.lower().replace(' ', '_').replace('-', '_')
            team_color = TEAM_COLORS.get(team_key, (200, 200, 200))
        except:
            team = 'Unknown'
            team_color = (200, 200, 200)
        
        # Process each lap
        laps_data = []
        for _, lap_row in driver_laps.iterrows():
            lap_number = int(lap_row['LapNumber'])
            
            # Lap time (handle NaT)
            lap_time = lap_row['LapTime']
            if pd.isna(lap_time):
                lap_time_seconds = 90.0  # Default estimate
            else:
                lap_time_seconds = lap_time.total_seconds()
            
            # Tire info
            compound = str(lap_row.get('Compound', 'UNKNOWN')).upper()
            tire_life = int(lap_row.get('TyreLife', 0)) if not pd.isna(lap_row.get('TyreLife')) else 0
            
            # Pit stop detection
            is_pit_out = bool(lap_row.get('PitOutTime') is not None and not pd.isna(lap_row.get('PitOutTime')))
            is_pit_in = bool(lap_row.get('PitInTime') is not None and not pd.isna(lap_row.get('PitInTime')))
            
            # Position
            position = int(lap_row.get('Position', 20)) if not pd.isna(lap_row.get('Position')) else 20
            
            laps_data.append(LapData(
                lap_number=lap_number,
                lap_time_seconds=lap_time_seconds,
                compound=compound,
                tire_life=tire_life,
                is_pit_out=is_pit_out,
                is_pit_in=is_pit_in,
                position=position
            ))
        
        # Sort by lap number
        laps_data.sort(key=lambda x: x.lap_number)
        
        # Final position
        final_position = laps_data[-1].position if laps_data else 20
        total_laps = len(laps_data)
        
        return DriverRaceData(
            driver_code=driver_code,
            driver_name=driver_name,
            team=team,
            team_color=team_color,
            laps=laps_data,
            final_position=final_position,
            total_laps=total_laps
        )
    
    def get_reference_lap_telemetry(
        self, 
        session: ff1.core.Session, 
        driver: str,
        resample_interval_ms: int = 100
    ) -> pd.DataFrame:
        """
        Get a single reference lap telemetry for track shape.
        Used for rendering car positions on the circuit.
        """
        driver_laps = session.laps.pick_driver(driver)
        
        if driver_laps.empty:
            raise ValueError(f"No lap data found for driver {driver}")
        
        try:
            reference_lap = driver_laps.pick_fastest()
        except Exception:
            reference_lap = driver_laps.iloc[0]
        
        telemetry = reference_lap.get_telemetry()
        
        if telemetry.empty:
            raise ValueError(f"No telemetry data for driver {driver}")
        
        return self._resample_telemetry(telemetry, resample_interval_ms)
    
    def _resample_telemetry(
        self, 
        telemetry: pd.DataFrame, 
        interval_ms: int
    ) -> pd.DataFrame:
        """Resample telemetry to uniform time intervals."""
        if 'Time' in telemetry.columns:
            time_ms = telemetry['Time'].dt.total_seconds() * 1000
        elif 'SessionTime' in telemetry.columns:
            time_ms = telemetry['SessionTime'].dt.total_seconds() * 1000
        else:
            time_ms = np.arange(len(telemetry)) * 50
        
        time_ms = time_ms.values
        new_time_ms = np.arange(time_ms[0], time_ms[-1], interval_ms)
        
        numeric_cols = ['X', 'Y', 'Speed', 'nGear', 'Throttle', 'Brake', 'RPM', 'DRS']
        available_cols = [c for c in numeric_cols if c in telemetry.columns]
        
        resampled_data = {'Time_ms': new_time_ms}
        
        for col in available_cols:
            values = telemetry[col].values
            valid_mask = ~np.isnan(values)
            
            if not np.any(valid_mask):
                resampled_data[col] = np.zeros(len(new_time_ms))
                continue
            
            kind = 'nearest' if col in ['nGear', 'DRS'] else 'linear'
            interp_func = interpolate.interp1d(
                time_ms[valid_mask], 
                values[valid_mask], 
                kind=kind,
                bounds_error=False,
                fill_value='extrapolate'
            )
            resampled_data[col] = interp_func(new_time_ms)
        
        return pd.DataFrame(resampled_data)
    
    def get_track_coordinates(self, session: ff1.core.Session) -> np.ndarray:
        """Extract track layout coordinates from session data."""
        laps = session.laps.pick_fastest()
        
        if laps is None or (hasattr(laps, 'empty') and laps.empty):
            laps = session.laps.iloc[0]
        
        telemetry = laps.get_telemetry()
        
        if 'X' not in telemetry.columns or 'Y' not in telemetry.columns:
            raise ValueError("No position data in telemetry")
        
        coords = telemetry[['X', 'Y']].values
        coords = coords[::5]  # Subsample for performance
        
        return coords
    
    def get_available_races(self, year: int) -> List[str]:
        """Get list of available races for a given year."""
        try:
            schedule = ff1.get_event_schedule(year)
            races = schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
            return races
        except Exception as e:
            print(f"Error fetching schedule: {e}")
            return []
    
    def get_drivers(self, session: ff1.core.Session) -> List[Tuple[str, str]]:
        """Get list of drivers in a session."""
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
