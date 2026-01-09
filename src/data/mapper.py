"""
Coordinate Mapper
Transforms geographic/track coordinates to screen pixel coordinates.
Auto-scales any circuit to fit perfectly within the display area.
"""

from typing import Tuple, Optional
import numpy as np


class CoordinateMapper:
    """
    Handles coordinate transformation from track space to screen pixels.
    Preserves aspect ratio and centers the track with configurable padding.
    """
    
    def __init__(
        self, 
        screen_width: int = 1280, 
        screen_height: int = 720, 
        padding: int = 50
    ):
        """
        Initialize the coordinate mapper.
        
        Args:
            screen_width: Target screen width in pixels
            screen_height: Target screen height in pixels
            padding: Margin from screen edges in pixels
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.padding = padding
        
        # Transformation parameters (set when fit_to_screen is called)
        self._scale: float = 1.0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0
        self._x_min: float = 0.0
        self._y_min: float = 0.0
        
        # Cache for transformed coordinates
        self._cached_track: Optional[np.ndarray] = None
        self._cached_pixels: Optional[np.ndarray] = None
    
    def fit_to_screen(self, track_coords: np.ndarray) -> np.ndarray:
        """
        Transform track coordinates to fit the screen while preserving aspect ratio.
        
        Algorithm:
        1. Find bounding box of track (min/max X and Y)
        2. Calculate scale factors for X and Y dimensions
        3. Use the smaller scale to preserve aspect ratio (uniform scaling)
        4. Calculate offset to center the track on screen
        5. Apply transformation to all points
        
        Args:
            track_coords: numpy array of shape (N, 2) with X, Y coordinates
            
        Returns:
            numpy array of shape (N, 2) with pixel coordinates
        """
        if len(track_coords) == 0:
            return np.array([])
        
        # Check cache
        if (self._cached_track is not None and 
            np.array_equal(track_coords, self._cached_track)):
            return self._cached_pixels
        
        # Step 1: Find bounding box
        x_coords = track_coords[:, 0]
        y_coords = track_coords[:, 1]
        
        self._x_min = np.min(x_coords)
        x_max = np.max(x_coords)
        self._y_min = np.min(y_coords)
        y_max = np.max(y_coords)
        
        track_width = x_max - self._x_min
        track_height = y_max - self._y_min
        
        # Avoid division by zero
        if track_width == 0:
            track_width = 1
        if track_height == 0:
            track_height = 1
        
        # Step 2: Calculate available screen space
        available_width = self.screen_width - (2 * self.padding)
        available_height = self.screen_height - (2 * self.padding)
        
        # Step 3: Calculate uniform scale (preserve aspect ratio)
        scale_x = available_width / track_width
        scale_y = available_height / track_height
        self._scale = min(scale_x, scale_y)  # Use smaller to fit both dimensions
        
        # Step 4: Calculate centering offset
        scaled_width = track_width * self._scale
        scaled_height = track_height * self._scale
        
        self._offset_x = (self.screen_width - scaled_width) / 2
        self._offset_y = (self.screen_height - scaled_height) / 2
        
        # Step 5: Transform all coordinates
        pixel_coords = np.zeros_like(track_coords)
        pixel_coords[:, 0] = (x_coords - self._x_min) * self._scale + self._offset_x
        pixel_coords[:, 1] = (y_coords - self._y_min) * self._scale + self._offset_y
        
        # Cache results
        self._cached_track = track_coords.copy()
        self._cached_pixels = pixel_coords.copy()
        
        return pixel_coords
    
    def geo_to_pixel(self, geo_x: float, geo_y: float) -> Tuple[int, int]:
        """
        Convert a single geographic coordinate to pixel position.
        
        Note: fit_to_screen must be called first to set transformation parameters.
        
        Args:
            geo_x: Geographic X coordinate
            geo_y: Geographic Y coordinate
            
        Returns:
            Tuple of (pixel_x, pixel_y) as integers
        """
        pixel_x = (geo_x - self._x_min) * self._scale + self._offset_x
        pixel_y = (geo_y - self._y_min) * self._scale + self._offset_y
        
        return (int(pixel_x), int(pixel_y))
    
    def pixel_to_geo(self, pixel_x: int, pixel_y: int) -> Tuple[float, float]:
        """
        Convert pixel position back to geographic coordinates.
        
        Args:
            pixel_x: Pixel X position
            pixel_y: Pixel Y position
            
        Returns:
            Tuple of (geo_x, geo_y)
        """
        geo_x = (pixel_x - self._offset_x) / self._scale + self._x_min
        geo_y = (pixel_y - self._offset_y) / self._scale + self._y_min
        
        return (geo_x, geo_y)
    
    def get_scale(self) -> float:
        """Get current scale factor (useful for sizing elements)."""
        return self._scale
    
    def get_pit_lane_offset(self) -> Tuple[int, int]:
        """
        Get a visual offset for pit lane rendering.
        Used to move cars visually away from the racing line when in pits.
        
        Returns:
            Tuple of (offset_x, offset_y) in pixels
        """
        # Offset perpendicular to typical track direction
        # This is a simple heuristic - could be refined per-circuit
        offset_distance = 30  # pixels
        return (offset_distance, offset_distance // 2)
    
    def interpolate_position(
        self, 
        track_pixels: np.ndarray, 
        index: float
    ) -> Tuple[int, int]:
        """
        Get interpolated position between track points.
        
        Args:
            track_pixels: Array of pixel coordinates
            index: Float index (e.g., 5.3 means 30% between point 5 and 6)
            
        Returns:
            Interpolated (x, y) pixel position
        """
        if len(track_pixels) == 0:
            return (0, 0)
        
        # Clamp index to valid range
        max_idx = len(track_pixels) - 1
        index = max(0, min(index, max_idx))
        
        # Get integer indices
        idx_low = int(index)
        idx_high = min(idx_low + 1, max_idx)
        
        # Interpolation factor
        t = index - idx_low
        
        # Linear interpolation
        x = track_pixels[idx_low, 0] * (1 - t) + track_pixels[idx_high, 0] * t
        y = track_pixels[idx_low, 1] * (1 - t) + track_pixels[idx_high, 1] * t
        
        return (int(x), int(y))
