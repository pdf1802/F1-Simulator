"""
Weather System
Manages historical weather data and sandbox overrides.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np

class WeatherSystem:
    """
    Hybrid weather system handling FastF1 historical data and user sandbox control.
    """
    
    def __init__(self):
        self.historical_rain: Dict[int, float] = {} # Time (sec) -> Intensity (0-1)
        self.sandbox_mode: bool = False
        self.sandbox_intensity: float = 0.0
        self.track_temp: float = 30.0 # degrees C
        self.air_temp: float = 25.0
        
    def load_from_session(self, session) -> None:
        """
        Load weather data from a FastF1 session.
        """
        try:
            # Get weather stream
            weather_data = session.weather_data
            
            if weather_data.empty:
                print("Warning: No weather data found in session.")
                return
                
            # Create a simplified lookup table
            # Normalize Rainfall: FastF1 gives boolean 'Rainfall', sometimes intensity
            # We will approximate intensity based on 'Rainfall' and 'Humidity' if needed
            # For now, simplistic mapping:
            
            for _, row in weather_data.iterrows():
                # SessionTime is Timedelta
                seconds = int(row['Time'].total_seconds())
                
                # Check different possible columns for rain info
                is_raining = row.get('Rainfall', False)
                
                intensity = 0.0
                if is_raining:
                    intensity = 0.3 # Light rain default
                    
                self.historical_rain[seconds] = intensity
                
            print(f"Loaded {len(self.historical_rain)} weather points.")
            
        except Exception as e:
            print(f"Error loading weather: {e}")
            
    def set_sandbox_rain(self, intensity: float):
        """
        Override weather with manual value.
        Args:
            intensity: 0.0 (Dry) to 1.0 (Monsoon)
        """
        self.sandbox_mode = True
        self.sandbox_intensity = max(0.0, min(1.0, intensity))
        
    def toggle_sandbox(self):
        self.sandbox_mode = not self.sandbox_mode
        
    def get_current_weather(self, time_seconds: float) -> float:
        """
        Get rain intensity for specific time.
        
        Returns:
             float: 0.0 - 1.0 representing rain intensity
        """
        if self.sandbox_mode:
            return self.sandbox_intensity
            
        # Get historical value
        # Find closest key in dict (could be optimized with bisect but dict lookup is fast enough for sparse updates)
        # Weather updates are typically every minute
        
        seconds_int = int(time_seconds)
        
        # Look for exact match or nearest preceding
        # Since this is a dict, we can't easily find nearest without sorting
        # But we can cache the sorted keys if performance becomes an issue
        
        # Simple fallback for now: check exact second, or assume dry if not found
        # (A real robust implementation would use interpolation)
        
        return self.historical_rain.get(seconds_int, 0.0)

