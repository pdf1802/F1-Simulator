"""
Simulation Engine - What-If Mode
Replays the REAL race while allowing player to modify one driver's strategy.
Ghost cars follow historical data exactly. Player car responds to decisions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from .physics import PhysicsModel
from .weather import WeatherSystem
from ..data.loader import DriverRaceData, LapData


@dataclass
class CarState:
    """State of a single car in the simulation."""
    driver_code: str
    driver_name: str
    team: str
    team_color: tuple
    
    # Race progress
    current_lap: int = 1
    lap_progress: float = 0.0  # 0.0 to 1.0 within current lap
    
    # Position & timing
    position: int = 1
    gap_to_leader: float = 0.0  # Seconds behind P1
    last_lap_time: float = 90.0  # Seconds
    
    # Tire state
    compound: str = "MEDIUM"
    tire_age: int = 0  # Laps on current set
    tire_wear: float = 0.0  # 0.0 (new) to 1.0 (dead)
    
    # Pit state
    in_pit: bool = False
    pit_requested: bool = False
    pit_timer: float = 0.0
    next_compound: str = ""
    
    # Mode (player only)
    mode: str = "NORMAL"  # PUSH, NORMAL, CONSERVE
    
    # Flags
    is_player: bool = False
    finished: bool = False
    dnf: bool = False
    
    # Visual position on track
    track_x: float = 0.0
    track_y: float = 0.0


class WhatIfSimEngine:
    """
    What-If Race Simulator.
    
    - Ghost cars: Follow EXACT historical lap times/positions
    - Player car: Starts with real data, but strategy changes affect outcome
    """
    
    PIT_STOP_DURATION = 22.0  # Average pit stop time in seconds
    
    def __init__(
        self,
        race_data: Dict[str, DriverRaceData],
        reference_telemetry: pd.DataFrame,
        physics: PhysicsModel,
        weather: WeatherSystem,
        player_driver: str,
        total_laps: int
    ):
        self.race_data = race_data
        self.reference_telemetry = reference_telemetry
        self.track_length = len(reference_telemetry)
        self.physics = physics
        self.weather = weather
        self.player_driver = player_driver
        self.total_laps = total_laps
        
        # Initialize car states
        self.cars: Dict[str, CarState] = {}
        self._init_cars()
        
        # Race state
        self.current_lap = 1
        self.race_time = 0.0  # Total elapsed race time in seconds
        self.lap_start_time = 0.0  # Time when current lap started
        self.paused = False
        
        # Player reference
        self.player_state = self.cars[player_driver]
        
        # Track timing for position calculation
        self.cumulative_times: Dict[str, float] = {code: 0.0 for code in race_data.keys()}
        
    def _init_cars(self):
        """Initialize car states from race data."""
        for driver_code, driver_data in self.race_data.items():
            is_player = (driver_code == self.player_driver)
            
            # Get starting compound from lap 1
            starting_compound = "MEDIUM"
            if driver_data.laps:
                starting_compound = driver_data.laps[0].compound
            
            # Get starting position
            starting_position = driver_data.laps[0].position if driver_data.laps else 20
            
            self.cars[driver_code] = CarState(
                driver_code=driver_code,
                driver_name=driver_data.driver_name,
                team=driver_data.team,
                team_color=driver_data.team_color,
                current_lap=1,
                position=starting_position,
                compound=starting_compound,
                is_player=is_player
            )
            
            # Sync initial position
            self._sync_track_position(self.cars[driver_code])
    
    def toggle_pause(self):
        self.paused = not self.paused
        return self.paused
    
    def update(self, dt: float):
        """Advance simulation by dt seconds."""
        if self.paused:
            return
        
        self.race_time += dt
        
        # Update each car
        for driver_code, car in self.cars.items():
            if car.finished or car.dnf:
                continue
                
            if car.is_player:
                self._update_player(car, dt)
            else:
                self._update_ghost(car, dt)
        
        # Recalculate positions based on cumulative time
        self._recalculate_positions()
        
        # Update track positions for rendering
        for car in self.cars.values():
            self._sync_track_position(car)
    
    def _update_ghost(self, car: CarState, dt: float):
        """
        Update ghost car to follow REAL historical data.
        Uses actual lap times from the race.
        """
        driver_data = self.race_data[car.driver_code]
        
        # Get current lap info
        current_lap_data = self._get_lap_data(driver_data, car.current_lap)
        if not current_lap_data:
            car.finished = True
            return
        
        # Calculate progress through lap based on real lap time
        real_lap_time = current_lap_data.lap_time_seconds
        
        # Advance progress
        progress_per_second = 1.0 / real_lap_time
        car.lap_progress += progress_per_second * dt
        
        # Check if lap completed
        if car.lap_progress >= 1.0:
            car.lap_progress -= 1.0
            car.current_lap += 1
            car.last_lap_time = real_lap_time
            
            # Update tire state from historical data
            next_lap_data = self._get_lap_data(driver_data, car.current_lap)
            if next_lap_data:
                # Check for pit stop
                if current_lap_data.is_pit_in:
                    car.compound = next_lap_data.compound
                    car.tire_age = 0
                else:
                    car.tire_age = next_lap_data.tire_life
                
                car.position = next_lap_data.position
            
            # Update cumulative time
            self.cumulative_times[car.driver_code] += real_lap_time
            
            if car.current_lap > self.total_laps:
                car.finished = True
    
    def _update_player(self, car: CarState, dt: float):
        """
        Update player car with physics simulation.
        Base lap time comes from historical data, modified by player decisions.
        """
        driver_data = self.race_data[car.driver_code]
        
        # Handle pit stop
        if car.in_pit:
            car.pit_timer += dt
            if car.pit_timer >= self.PIT_STOP_DURATION:
                car.in_pit = False
                car.pit_timer = 0.0
                car.compound = car.next_compound
                car.tire_age = 0
                car.tire_wear = 0.0
            return
        
        # Get base lap time from historical data
        current_lap_data = self._get_lap_data(driver_data, car.current_lap)
        if not current_lap_data:
            car.finished = True
            return
        
        base_lap_time = current_lap_data.lap_time_seconds
        
        # Apply physics modifiers based on player decisions
        rain_level = self.weather.get_current_weather(self.race_time)
        pace_factor = self.physics.calculate_pace_factor(
            car.compound,
            car.tire_wear,
            car.mode,
            rain_level
        )
        
        # Modified lap time (faster pace = lower time)
        # pace_factor > 1.0 means faster, so divide
        modified_lap_time = base_lap_time / pace_factor
        
        # Advance progress
        progress_per_second = 1.0 / modified_lap_time
        car.lap_progress += progress_per_second * dt
        
        # Accumulate tire wear
        if car.lap_progress > 0:
            wear_rate = self.physics.calculate_tire_wear(
                car.compound,
                car.tire_wear,
                car.mode
            )
            car.tire_wear += wear_rate * dt / modified_lap_time
            car.tire_wear = min(0.99, car.tire_wear)
        
        # Check if lap completed
        if car.lap_progress >= 1.0:
            car.lap_progress -= 1.0
            car.current_lap += 1
            car.last_lap_time = modified_lap_time
            car.tire_age += 1
            
            # Update cumulative time
            self.cumulative_times[car.driver_code] += modified_lap_time
            
            # Check pit request
            if car.pit_requested:
                car.in_pit = True
                car.pit_requested = False
                self.cumulative_times[car.driver_code] += self.PIT_STOP_DURATION
            
            if car.current_lap > self.total_laps:
                car.finished = True
    
    def _get_lap_data(self, driver_data: DriverRaceData, lap: int) -> Optional[LapData]:
        """Get lap data for a specific lap number."""
        for lap_data in driver_data.laps:
            if lap_data.lap_number == lap:
                return lap_data
        return None
    
    def _recalculate_positions(self):
        """Recalculate race positions based on cumulative time + current lap progress."""
        # Build list of (driver, total_distance_equivalent)
        standings = []
        for code, car in self.cars.items():
            if car.dnf:
                distance = -1  # DNF goes to back
            else:
                # Distance = completed laps + current progress
                distance = (car.current_lap - 1) + car.lap_progress
            
            # For ties, use cumulative time (lower is better)
            standings.append((code, distance, self.cumulative_times[code]))
        
        # Sort by distance (desc), then by time (asc)
        standings.sort(key=lambda x: (-x[1], x[2]))
        
        # Assign positions
        leader_time = standings[0][2] if standings else 0
        for i, (code, distance, time) in enumerate(standings):
            self.cars[code].position = i + 1
            self.cars[code].gap_to_leader = time - leader_time
    
    def _sync_track_position(self, car: CarState):
        """Update car's X,Y position on track for rendering."""
        # Map lap_progress to telemetry index
        idx = int(car.lap_progress * (self.track_length - 1))
        idx = max(0, min(idx, self.track_length - 1))
        
        row = self.reference_telemetry.iloc[idx]
        car.track_x = row['X']
        car.track_y = row['Y']
    
    # === Player Actions ===
    
    def set_mode(self, mode: str):
        """Set player driving mode."""
        if mode in ['PUSH', 'NORMAL', 'CONSERVE']:
            self.player_state.mode = mode
    
    def request_pit(self, compound: str):
        """Request pit stop with specified compound."""
        if not self.player_state.in_pit and not self.player_state.pit_requested:
            self.player_state.pit_requested = True
            self.player_state.next_compound = compound
            return True
        return False
    
    def cancel_pit(self):
        """Cancel pending pit request."""
        if self.player_state.pit_requested and not self.player_state.in_pit:
            self.player_state.pit_requested = False
            return True
        return False
    
    def jump_to_lap(self, target_lap: int):
        """Jump all cars to a specific lap."""
        target_lap = max(1, min(target_lap, self.total_laps))
        
        for driver_code, car in self.cars.items():
            driver_data = self.race_data[driver_code]
            lap_data = self._get_lap_data(driver_data, target_lap)
            
            car.current_lap = target_lap
            car.lap_progress = 0.0
            car.finished = (target_lap > self.total_laps)
            
            if lap_data:
                car.position = lap_data.position
                car.compound = lap_data.compound
                car.tire_age = lap_data.tire_life
            
            # Recalculate cumulative time
            total_time = 0.0
            for lap in driver_data.laps:
                if lap.lap_number < target_lap:
                    total_time += lap.lap_time_seconds
            self.cumulative_times[driver_code] = total_time
            
            # Reset pit state
            car.in_pit = False
            car.pit_requested = False
            car.pit_timer = 0.0
            
            self._sync_track_position(car)
        
        self.current_lap = target_lap
        
        # Estimate race time
        self.race_time = sum(self.cumulative_times.values()) / len(self.cumulative_times)
    
    def get_race_progress(self) -> float:
        """Get race progress as 0.0-1.0."""
        leader = min(self.cars.values(), key=lambda c: c.position)
        completed = (leader.current_lap - 1 + leader.lap_progress)
        return min(1.0, completed / self.total_laps)
    
    def set_race_progress(self, progress: float):
        """Jump to a specific race progress point."""
        target_lap = int(progress * self.total_laps) + 1
        self.jump_to_lap(target_lap)
    
    def get_sorted_cars(self) -> List[CarState]:
        """Get cars sorted by position."""
        return sorted(self.cars.values(), key=lambda c: c.position)
    
    def get_player_position(self) -> int:
        """Get player's current position."""
        return self.player_state.position
    
    def get_historical_comparison(self) -> dict:
        """
        Compare player's current performance to real history.
        Returns dict with comparison data.
        """
        driver_data = self.race_data[self.player_driver]
        real_position = driver_data.get_position_at_lap(self.player_state.current_lap)
        current_position = self.player_state.position
        
        return {
            'real_position': real_position,
            'current_position': current_position,
            'position_delta': real_position - current_position,  # Positive = better than real
            'real_final_position': driver_data.final_position
        }
