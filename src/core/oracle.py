"""
Strategy Oracle
Placeholder for future AI strategy prediction.
"""

class StrategyOracle:
    """
    Provides strategic recommendations based on current race state.
    """
    
    def __init__(self):
        pass
        
    def get_recommendation(self, tire_age: int, rain_intensity: float) -> str:
        """
        Simple heuristic recommendation.
        """
        if rain_intensity > 0.5:
            return "BOX FOR WETS"
        if rain_intensity > 0.1:
            return "BOX FOR INTERS"
            
        if tire_age > 20:
            return "CONSIDER BOX"
            
        return "STAY OUT"
