"""
Simulation Engine
The core logic managing the dual-state simulation (Real History vs Player Simulation).
Handles the game loop integration, car physics updates, lap resets, and multi-car racing.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from .physics import PhysicsModel
from .weather import WeatherSystem

@dataclass
class CarState:
    """State of a single car in the simulation."""
    driver_code: str            # Driver abbreviation (VER, HAM, etc.)
    idx: float                  # Index in the telemetry array/map (float for smooth interpolation)
    lap: int                    # Current lap number
    position_x: float           # Geographic X
    position_y: float           # Geographic Y
    speed: float                # km/h
    gear: int                   # Current gear
    compound: str               # Tire compound name
    tire_age_laps: float        # Laps on current set
    tire_wear: float            # 0.0 (New) to 1.0 (Dead)
    mode: str = "NORMAL"        # PUSH, NORMAL, CONSERVE
    in_pit: bool = False
    pit_requested: bool = False # Player requested pit, waiting for pit entry
    pit_timer: float = 0.0      # Seconds spent in pit
    finished: bool = False
    team_color: tuple = (255, 255, 255)  # RGB color for rendering

# Team colors for rendering
TEAM_COLORS = {
    'VER': (30, 65, 255),    # Red Bull Blue
    'PER': (30, 65, 255),
    'HAM': (0, 210, 190),    # Mercedes Teal
    'RUS': (0, 210, 190),
    'LEC': (220, 0, 0),      # Ferrari Red
    'SAI': (220, 0, 0),
    'NOR': (255, 135, 0),    # McLaren Orange/Papaya
    'PIA': (255, 135, 0),
    'ALO': (0, 110, 70),     # Aston Martin Green
    'STR': (0, 110, 70),
    'OCO': (0, 144, 255),    # Alpine Blue
    'GAS': (0, 144, 255),
    'TSU': (102, 146, 255),  # RB/AlphaTauri Blue
    'RIC': (102, 146, 255),
    'BOT': (155, 0, 0),      # Alfa Romeo/Sauber
    'ZHO': (155, 0, 0),
    'ALB': (100, 196, 237),  # Williams Blue
    'SAR': (100, 196, 237),
    'MAG': (182, 186, 189),  # Haas Gray
    'HUL': (182, 186, 189),
}

class SimEngine:
    """
    Manages the real-time simulation logic for multiple cars.
    """
    
    # Pit entry zone: when car is in last 5% of lap, pit request triggers
    PIT_ENTRY_ZONE_START = 0.95  # 95% through the lap
    PIT_STOP_DURATION = 25.0     # Seconds for pit stop
    
    def __init__(
        self, 
        all_telemetry: Dict[str, pd.DataFrame],  # driver_code -> telemetry
        physics: PhysicsModel,
        weather: WeatherSystem,
        player_driver: str,
        total_laps: int = 60
    ):
        self.all_telemetry = all_telemetry
        self.physics = physics
        self.weather = weather
        self.player_driver = player_driver
        self.total_laps = total_laps
        
        # Use player's telemetry as reference for track length
        self.reference_telemetry = all_telemetry[player_driver]
        self.track_length_idx = len(self.reference_telemetry)
        
        # Initialize all car states
        self.all_cars: Dict[str, CarState] = {}
        self._init_all_cars()
        
        # Convenience references
        self.player_state: CarState = self.all_cars[player_driver]
        
        self.current_time = 0.0  # Race time in seconds
        self.paused = False      # Pause state
        
        # Simulation speed multiplier (1x = real time)
        self.time_multiplier = 1.0 
        
    def _init_all_cars(self):
        """Initialize CarState for each driver."""
        for driver_code, telemetry in self.all_telemetry.items():
            # Slight random offset to spread cars at start (simulating grid positions)
            start_offset = list(self.all_telemetry.keys()).index(driver_code) * 5
            
            color = TEAM_COLORS.get(driver_code, (200, 200, 200))
            
            self.all_cars[driver_code] = CarState(
                driver_code=driver_code,
                idx=start_offset,
                lap=1,
                position_x=0,
                position_y=0,
                speed=0,
                gear=1,
                compound="MEDIUM",
                tire_age_laps=0,
                tire_wear=0.0,
                team_color=color
            )
            
            # Sync initial position
            self._sync_state_from_telemetry(self.all_cars[driver_code], telemetry)
    
    def toggle_pause(self):
        """Toggle pause state."""
        self.paused = not self.paused
        return self.paused
        
    def update(self, dt_seconds: float):
        """
        Advance simulation by dt seconds (game time).
        """
        if self.paused:
            return
            
        simulation_dt = dt_seconds * self.time_multiplier
        self.current_time += simulation_dt
        
        # Update all cars
        for driver_code, car_state in self.all_cars.items():
            telemetry = self.all_telemetry[driver_code]
            track_len = len(telemetry)
            
            if driver_code == self.player_driver:
                self._update_player(simulation_dt, car_state, telemetry, track_len)
            else:
                self._update_ghost(simulation_dt, car_state, telemetry, track_len)
    
    def _update_ghost(self, dt: float, state: CarState, telemetry: pd.DataFrame, track_len: int):
        """
        Advance ghost car (AI/historical) by moving forward in telemetry time.
        """
        if state.finished:
            return
            
        # Add slight variation to make ghosts feel more "alive"
        # Base: 10 indices per second (100ms per index)
        speed_variation = 0.95 + (hash(state.driver_code) % 10) * 0.01  # 0.95 to 1.04
        indices_to_move = dt * 10 * speed_variation
        
        state.idx += indices_to_move
        
        # Loop logic
        if state.idx >= track_len:
            state.idx -= track_len
            state.lap += 1
            if state.lap > self.total_laps:
                state.finished = True
                state.idx = track_len - 1
                
        self._sync_state_from_telemetry(state, telemetry)
        
    def _update_player(self, dt: float, state: CarState, telemetry: pd.DataFrame, track_len: int):
        """
        Advance player car based on Physics.
        """
        if state.finished:
            return
        
        # Check pit entry zone
        lap_progress = state.idx / track_len
        
        # If pit was requested and we're in the pit entry zone, trigger pit stop
        if state.pit_requested and lap_progress >= self.PIT_ENTRY_ZONE_START:
            state.in_pit = True
            state.pit_requested = False
            
        # Handle active Pit Stop
        if state.in_pit:
            state.pit_timer += dt
            if state.pit_timer >= self.PIT_STOP_DURATION:
                state.in_pit = False
                state.pit_timer = 0
                state.tire_wear = 0.0
                state.tire_age_laps = 0
            else:
                return  # Car is stationary in pit box
        
        # Get environmental factors
        rain_level = self.weather.get_current_weather(self.current_time)
        
        # Calculate performance modifier
        pace_factor = self.physics.calculate_pace_factor(
            state.compound,
            state.tire_wear,
            state.mode,
            rain_level
        )
        
        # Calculate movement
        base_speed_indices = dt * 10  # Baseline 100ms progress
        actual_move = base_speed_indices * pace_factor
        
        state.idx += actual_move
        
        # Accumulate tire wear
        lap_progress_pct = actual_move / track_len
        wear_increment = self.physics.calculate_tire_wear(
            state.compound,
            state.tire_wear,
            state.mode
        )
        state.tire_wear += wear_increment * lap_progress_pct
        state.tire_age_laps += lap_progress_pct
        state.tire_wear = min(0.99, state.tire_wear)
        
        # Loop logic
        if state.idx >= track_len:
            state.idx -= track_len
            state.lap += 1
            if state.lap > self.total_laps:
                state.finished = True
                state.idx = track_len - 1

        self._sync_state_from_telemetry(state, telemetry)
        
    def _sync_state_from_telemetry(self, state: CarState, telemetry: pd.DataFrame):
        """
        Update X,Y,Speed,Gear based on current index.
        """
        idx_int = int(state.idx)
        track_len = len(telemetry)
        idx_int = max(0, min(idx_int, track_len - 1))
        
        row = telemetry.iloc[idx_int]
        
        state.position_x = row['X']
        state.position_y = row['Y']
        state.speed = row.get('Speed', 0)
        state.gear = int(row.get('nGear', 1))
        
    # Player Actions
    def set_mode(self, mode: str):
        if mode in ['PUSH', 'NORMAL', 'CONSERVE']:
            self.player_state.mode = mode
            
    def request_box(self, new_compound: str):
        """
        Request pit stop. Car will enter pits at the pit entry zone (end of current lap).
        """
        if not self.player_state.in_pit and not self.player_state.pit_requested:
            self.player_state.pit_requested = True
            self.player_state.compound = new_compound
            return True
        return False
    
    def cancel_box(self):
        """Cancel a pending pit request."""
        if self.player_state.pit_requested and not self.player_state.in_pit:
            self.player_state.pit_requested = False
            return True
        return False
    
    def get_sorted_cars(self) -> List[CarState]:
        """Get all cars sorted by race position (lap + track progress)."""
        def race_position_key(car: CarState):
            return -(car.lap * 1000000 + car.idx)  # Negative for descending
        
        return sorted(self.all_cars.values(), key=race_position_key)
    
    def get_player_position(self) -> int:
        """Get player's current race position (1st, 2nd, etc.)."""
        sorted_cars = self.get_sorted_cars()
        for i, car in enumerate(sorted_cars):
            if car.driver_code == self.player_driver:
                return i + 1
        return len(sorted_cars)
    
    def jump_to_lap(self, target_lap: int):
        """
        Jump all cars to a specific lap.
        Useful for skipping ahead in the race.
        """
        target_lap = max(1, min(target_lap, self.total_laps))
        
        for driver_code, car in self.all_cars.items():
            car.lap = target_lap
            car.idx = 0  # Start of lap
            car.finished = (target_lap > self.total_laps)
            
            # Reset pit states when jumping
            car.in_pit = False
            car.pit_requested = False
            car.pit_timer = 0
            
            # Sync positions
            telemetry = self.all_telemetry[driver_code]
            self._sync_state_from_telemetry(car, telemetry)
        
        # Update race time estimate (rough: 90 seconds per lap average)
        self.current_time = (target_lap - 1) * 90.0
        
    def set_race_progress(self, progress: float):
        """
        Set race progress as a percentage (0.0 to 1.0).
        Used by timeline scrubber.
        """
        progress = max(0.0, min(1.0, progress))
        
        # Calculate target lap and track position
        total_race_distance = self.total_laps  # In laps
        current_distance = progress * total_race_distance
        
        target_lap = int(current_distance) + 1
        lap_progress = current_distance - int(current_distance)
        
        for driver_code, car in self.all_cars.items():
            telemetry = self.all_telemetry[driver_code]
            track_len = len(telemetry)
            
            car.lap = min(target_lap, self.total_laps)
            car.idx = lap_progress * track_len
            car.finished = (target_lap > self.total_laps)
            
            # Reset pit states
            car.in_pit = False
            car.pit_requested = False
            car.pit_timer = 0
            
            self._sync_state_from_telemetry(car, telemetry)
        
        self.current_time = progress * self.total_laps * 90.0  # Estimate
    
    def get_race_progress(self) -> float:
        """
        Get current race progress as percentage (0.0 to 1.0).
        Based on leader position.
        """
        leader = self.get_sorted_cars()[0] if self.all_cars else None
        if not leader:
            return 0.0
        
        telemetry = self.all_telemetry.get(leader.driver_code)
        if telemetry is None:
            return 0.0
            
        track_len = len(telemetry)
        completed_laps = leader.lap - 1
        lap_progress = leader.idx / track_len if track_len > 0 else 0
        
        total_progress = (completed_laps + lap_progress) / self.total_laps
        return min(1.0, max(0.0, total_progress))

