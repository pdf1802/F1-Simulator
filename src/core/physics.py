"""
Physics Model
Calculates tire degradation, lap time penalties, and physical interactions.
"""

from typing import Dict

class PhysicsModel:
    """
    Handles tire physics and environmental effects on car performance.
    """
    
    # Base degradation per lap (percentage 0.0-1.0)
    # Based on rough F1 approximation
    TIRE_WEAR_RATES = {
        'SOFT': 0.035,         # ~28 laps life
        'MEDIUM': 0.025,       # ~40 laps life
        'HARD': 0.018,         # ~55 laps life
        'INTERMEDIATE': 0.030, # Dependent on track condition
        'WET': 0.022           # Robust but slow
    }
    
    # Base lap time delta vs Soft (seconds)
    COMPOUND_PACE_DELTA = {
        'SOFT': 0.0,
        'MEDIUM': 0.5,
        'HARD': 1.1,
        'INTERMEDIATE': 2.0,   # On dry track
        'WET': 4.5            # On dry track
    }
    
    # Push modes affect both pace and wear
    MODE_MULTIPLIERS = {
        'PUSH': {'wear': 1.6, 'pace': 1.05},    # 5% faster, 60% more wear
        'NORMAL': {'wear': 1.0, 'pace': 1.0},   # Standard
        'CONSERVE': {'wear': 0.6, 'pace': 0.92} # 8% slower, 40% less wear
    }
    
    def calculate_tire_wear(self, compound: str, current_wear: float, mode: str) -> float:
        """
        Calculate incremental tire wear for one tick/lap.
        
        Args:
            compound: Tire compound name
            current_wear: Current wear level (0.0 - 1.0)
            mode: Driving mode (PUSH/NORMAL/CONSERVE)
            
        Returns:
            New wear increment to add
        """
        base = self.TIRE_WEAR_RATES.get(compound.upper(), 0.025)
        mult = self.MODE_MULTIPLIERS.get(mode, self.MODE_MULTIPLIERS['NORMAL'])['wear']
        
        # Wear accelerates as tire gets older (cliff effect)
        cliff_factor = 1.0 + (current_wear * 1.5)  # Up to 2.5x wear at end of life
        
        return base * mult * cliff_factor
        
    def calculate_pace_factor(self, compound: str, wear: float, mode: str, rain_intensity: float) -> float:
        """
        Calculate speed multiplier (1.0 = base speed).
        
        Args:
            compound: Tire compound
            wear: Current tire wear (0.0 - 1.0)
            mode: Driving mode
            rain_intensity: 0.0 (dry) to 1.0 (storm)
            
        Returns:
            Speed multiplier (e.g., 0.95 means 5% slower)
        """
        # 1. Tire Performance (fresh vs worn)
        # Fresh tires are fastest. Wear reduces grip linearly then exponentially.
        wear_penalty = 0.0
        if wear < 0.6:
            wear_penalty = wear * 0.1  # Linear drop off up to 60%
        else:
            wear_penalty = 0.06 + ((wear - 0.6) * 0.5)  # Massive drop off after cliff
            
        # 2. Compound Delta
        # Normalize base delta to percentage (approx 1.5s lap = ~1.5%)
        compound_delta = self.COMPOUND_PACE_DELTA.get(compound.upper(), 0.5) * 0.012
        
        # 3. Weather Penalty (The crucial cross-over logic)
        weather_penalty = 0.0
        
        if rain_intensity < 0.1:  # DRY
            if compound in ['INTERMEDIATE', 'WET']:
                weather_penalty = 0.05 + (rain_intensity * 0.1) # Wrong tire
        elif rain_intensity < 0.6: # DAMP/INTER conditions
             if compound == 'SLICK': # (Soft/Med/Hard)
                 weather_penalty = rain_intensity * 0.8 # Slicks on wet is bad
             elif compound == 'WET':
                 weather_penalty = 0.05 # Wets on inter track is slow
             # Inter is optimal here
        else: # HEAVY WET
            if compound != 'WET':
                weather_penalty = rain_intensity * 1.2 # Anything but wet is un-drivable
        
        # 4. Mode
        mode_pace = self.MODE_MULTIPLIERS.get(mode, self.MODE_MULTIPLIERS['NORMAL'])['pace']
        
        # Combine factors
        # Start with mode, subtract penalties
        total_perf = mode_pace - wear_penalty - compound_delta - weather_penalty
        
        return max(0.1, total_perf) # Minimum speed 10%
