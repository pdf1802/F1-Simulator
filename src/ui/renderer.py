"""
Game Renderer
Handles all Pygame drawing: Track, Cars (all drivers), HUD, and Controls.
Features separate visual styles for ghost vs player and pit stop offsets.
"""

import pygame
import numpy as np
from typing import Tuple, Dict, List
from ..data.mapper import CoordinateMapper
from ..core.sim_engine import CarState

class GameRenderer:
    # Color Palette
    COLOR_BG = (20, 20, 20)
    COLOR_TRACK = (60, 60, 60)
    COLOR_TRACK_BORDER = (100, 100, 100)
    COLOR_PLAYER = (255, 0, 0)      # Default player color
    COLOR_GHOST = (200, 200, 200)   # Light Gray
    COLOR_TEXT = (255, 255, 255)
    
    # UI Colors
    COLOR_UI_BG = (40, 40, 40, 200) # Semi-transparent
    COLOR_BTN_NORMAL = (0, 100, 200)
    COLOR_BTN_HOVER = (0, 120, 240)
    COLOR_BTN_ACTIVE = (0, 80, 160)
    COLOR_BTN_PENDING = (255, 165, 0)  # Orange for pending pit
    
    def __init__(self, screen: pygame.Surface, mapper: CoordinateMapper):
        self.screen = screen
        self.mapper = mapper
        self.width = screen.get_width()
        self.height = screen.get_height()
        
        self.font_large = pygame.font.SysFont("Consolas", 24, bold=True)
        self.font_small = pygame.font.SysFont("Consolas", 16)
        self.font_tiny = pygame.font.SysFont("Consolas", 11)
        
        # Pre-render track surface
        self.track_surface = None
        
        # Interactive Button Rects
        self.btn_push = pygame.Rect(self.width - 320, self.height - 80, 100, 50)
        self.btn_normal = pygame.Rect(self.width - 210, self.height - 80, 100, 50)
        self.btn_conserve = pygame.Rect(self.width - 100, self.height - 80, 100, 50)
        self.btn_box = pygame.Rect(self.width - 150, self.height - 150, 120, 50)
        
    def draw_track(self, track_coords: np.ndarray):
        """
        Draw the track layout.
        Uses cached surface to avoid transforming points every frame.
        """
        if self.track_surface is None:
            self.track_surface = pygame.Surface((self.width, self.height))
            self.track_surface.fill(self.COLOR_BG)
            
            # Transform points
            pixels = self.mapper.fit_to_screen(track_coords)
            
            if len(pixels) > 1:
                # Convert to list of tuples for pygame
                point_list = [(int(p[0]), int(p[1])) for p in pixels]
                
                # Draw border (closed loop)
                pygame.draw.lines(self.track_surface, self.COLOR_TRACK_BORDER, True, point_list, 14)
                # Draw tarmac
                pygame.draw.lines(self.track_surface, self.COLOR_TRACK, True, point_list, 10)
                
                # Draw Start/Finish line (first point)
                sf_line_start = point_list[0]
                pygame.draw.circle(self.track_surface, (255, 255, 255), sf_line_start, 8)
                
                # Draw pit entry indicator (at 95% of track)
                pit_idx = int(len(point_list) * 0.95)
                pit_point = point_list[pit_idx]
                pygame.draw.circle(self.track_surface, (255, 165, 0), pit_point, 6)  # Orange
        
        # Blit cached background
        self.screen.blit(self.track_surface, (0, 0))

    def draw_all_cars(self, all_cars: Dict[str, CarState], player_driver: str):
        """
        Draw ALL cars on track. Player car is highlighted differently.
        """
        # Sort cars so player is drawn last (on top)
        cars_to_draw = []
        for driver_code, car in all_cars.items():
            is_player = (driver_code == player_driver)
            cars_to_draw.append((car, is_player))
        
        # Draw non-players first, then player on top
        cars_to_draw.sort(key=lambda x: x[1])
        
        for car, is_player in cars_to_draw:
            self._draw_car(car, is_player)
    
    def _draw_car(self, car: CarState, is_player: bool):
        """Draw a single car on the track."""
        pixel = self.mapper.geo_to_pixel(car.track_x, car.track_y)
        
        # Apply Pit Stop Offset for cars in pit
        if car.in_pit:
            offset = self.mapper.get_pit_lane_offset()
            original_pixel = pixel
            pixel = (pixel[0] + offset[0], pixel[1] + offset[1])
            # Draw connector line
            pygame.draw.line(self.screen, (80, 80, 80), original_pixel, pixel, 1)
        
        x, y = pixel
        
        if is_player:
            # Player car: Larger, solid, with label
            radius = 14
            color = car.team_color
            
            # Outer glow effect
            glow_surf = pygame.Surface((radius*4, radius*4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*color, 60), (radius*2, radius*2), radius + 6)
            self.screen.blit(glow_surf, (x - radius*2, y - radius*2))
            
            # Main circle
            pygame.draw.circle(self.screen, color, (x, y), radius)
            pygame.draw.circle(self.screen, (255, 255, 255), (x, y), radius, 3)
            
            # Label
            label = car.driver_code
            text = self.font_small.render(label, True, (255, 255, 255))
            text_bg = pygame.Surface((text.get_width() + 6, text.get_height() + 2), pygame.SRCALPHA)
            text_bg.fill((0, 0, 0, 180))
            self.screen.blit(text_bg, (x + 16, y - 10))
            self.screen.blit(text, (x + 19, y - 9))
            
            # Pit request indicator
            if car.pit_requested:
                pit_text = self.font_tiny.render("PIT", True, (255, 165, 0))
                self.screen.blit(pit_text, (x + 16, y + 5))
        else:
            # Other cars: Smaller, semi-transparent
            radius = 8
            color = car.team_color
            
            # Semi-transparent circle
            surf = pygame.Surface((radius*2 + 2, radius*2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color, 180), (radius + 1, radius + 1), radius)
            pygame.draw.circle(surf, (255, 255, 255, 100), (radius + 1, radius + 1), radius, 1)
            self.screen.blit(surf, (x - radius - 1, y - radius - 1))
            
            # Small driver code
            label = self.font_tiny.render(car.driver_code, True, (200, 200, 200))
            self.screen.blit(label, (x + 10, y - 5))

    def draw_dashboard(self, state: CarState, laps_total: int, current_weather_rain: float, 
                       player_position: int, total_cars: int, comparison: dict = None):
        """
        Draw TV-style telemetry HUD with position info and historical comparison.
        """
        # Dashboard Panel Background
        panel_w, panel_h = 320, 260
        panel_x, panel_y = 20, self.height - 280
        
        surf = pygame.Surface((panel_w, panel_h))
        surf.set_alpha(200)
        surf.fill((0, 0, 0))
        self.screen.blit(surf, (panel_x, panel_y))
        
        # Draw Border
        pygame.draw.rect(self.screen, self.COLOR_TEXT, (panel_x, panel_y, panel_w, panel_h), 2)
        
        # Position badge
        pos_color = (255, 215, 0) if player_position == 1 else (192, 192, 192) if player_position == 2 else (205, 127, 50) if player_position == 3 else (255, 255, 255)
        pos_text = self.font_large.render(f"P{player_position}", True, pos_color)
        self.screen.blit(pos_text, (panel_x + 20, panel_y + 15))
        
        # Historical comparison (if available)
        if comparison:
            delta = comparison.get('position_delta', 0)
            if delta > 0:
                delta_text = f"+{delta} vs REAL"
                delta_color = (0, 255, 0)  # Green = better
            elif delta < 0:
                delta_text = f"{delta} vs REAL"
                delta_color = (255, 0, 0)  # Red = worse
            else:
                delta_text = "= REAL"
                delta_color = (255, 255, 255)
            
            cmp_surf = self.font_small.render(delta_text, True, delta_color)
            self.screen.blit(cmp_surf, (panel_x + 80, panel_y + 18))
        
        # Pit status
        pit_status = ""
        if state.in_pit:
            pit_status = f"IN PIT ({state.pit_timer:.1f}s)"
        elif state.pit_requested:
            pit_status = "PIT REQUESTED"
        
        # Data Rows
        lines = [
            f"LAP: {state.current_lap} / {laps_total}",
            f"TIRE: {state.compound} ({state.tire_age}L)",
            f"WEAR: {int(state.tire_wear * 100)}%",
            f"GAP: +{state.gap_to_leader:.1f}s" if state.gap_to_leader > 0 else "GAP: LEADER",
            f"LAST: {state.last_lap_time:.1f}s",
            f"MODE: {state.mode}",
            pit_status
        ]
        
        for i, line in enumerate(lines):
            if not line:
                continue
            font = self.font_small
            color = self.COLOR_TEXT
            
            # Color code wear
            if "WEAR" in line:
                if state.tire_wear > 0.7: color = (255, 0, 0)
                elif state.tire_wear > 0.4: color = (255, 255, 0)
            
            # Color pit status
            if "PIT" in line:
                color = (255, 165, 0)
                
            tsurf = font.render(line, True, color)
            self.screen.blit(tsurf, (panel_x + 20, panel_y + 50 + i*25))
    
    def draw_leaderboard(self, sorted_cars: List[CarState], player_driver: str):
        """
        Draw a mini leaderboard showing top positions.
        """
        panel_w, panel_h = 180, min(220, 30 + len(sorted_cars) * 18)
        panel_x, panel_y = self.width - panel_w - 20, 20
        
        surf = pygame.Surface((panel_w, panel_h))
        surf.set_alpha(180)
        surf.fill((0, 0, 0))
        self.screen.blit(surf, (panel_x, panel_y))
        pygame.draw.rect(self.screen, (100, 100, 100), (panel_x, panel_y, panel_w, panel_h), 1)
        
        # Title
        title = self.font_small.render("STANDINGS", True, self.COLOR_TEXT)
        self.screen.blit(title, (panel_x + 10, panel_y + 5))
        
        # Show top 10 + player if not in top 10
        top_n = sorted_cars[:10]
        player_shown = False
        
        for i, car in enumerate(top_n):
            is_player = (car.driver_code == player_driver)
            if is_player:
                player_shown = True
            
            y_pos = panel_y + 28 + i * 18
            
            # Position number
            pos_text = self.font_tiny.render(f"{i+1}.", True, (150, 150, 150))
            self.screen.blit(pos_text, (panel_x + 10, y_pos))
            
            # Driver code with team color
            color = car.team_color if not is_player else (255, 255, 255)
            bg_color = (50, 50, 50) if is_player else None
            
            if bg_color:
                pygame.draw.rect(self.screen, bg_color, (panel_x + 30, y_pos - 1, 50, 16))
            
            drv_text = self.font_tiny.render(car.driver_code, True, color)
            self.screen.blit(drv_text, (panel_x + 35, y_pos))
            
            # Lap and gap info
            if car.gap_to_leader > 0:
                gap_text = self.font_tiny.render(f"+{car.gap_to_leader:.1f}s", True, (120, 120, 120))
            else:
                gap_text = self.font_tiny.render(f"L{car.current_lap}", True, (120, 120, 120))
            self.screen.blit(gap_text, (panel_x + 90, y_pos))
            
    def draw_controls(self, current_mode: str, pit_requested: bool = False):
        """
        Draw interactive buttons.
        """
        mouse_pos = pygame.mouse.get_pos()
        
        buttons = [
            (self.btn_push, "PUSH", "PUSH"),
            (self.btn_normal, "NORMAL", "NORMAL"),
            (self.btn_conserve, "SAVE", "CONSERVE"),
            (self.btn_box, "BOX BOX" if not pit_requested else "CANCEL", "BOX")
        ]
        
        for rect, label, mode_id in buttons:
            is_hover = rect.collidepoint(mouse_pos)
            is_active = (mode_id == current_mode)
            
            if mode_id == "BOX" and pit_requested:
                color = self.COLOR_BTN_PENDING
            elif is_active:
                color = self.COLOR_BTN_ACTIVE
            elif is_hover:
                color = self.COLOR_BTN_HOVER
            else:
                color = self.COLOR_BTN_NORMAL
            
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 2, border_radius=5)
            
            text = self.font_small.render(label, True, self.COLOR_TEXT)
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)
    
    def draw_pause_overlay(self):
        """Draw pause screen overlay."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))
        
        pause_text = self.font_large.render("PAUSED", True, (255, 255, 255))
        text_rect = pause_text.get_rect(center=(self.width // 2, self.height // 2 - 20))
        self.screen.blit(pause_text, text_rect)
        
        hint_text = self.font_small.render("Press SPACE to resume | ESC to quit", True, (180, 180, 180))
        hint_rect = hint_text.get_rect(center=(self.width // 2, self.height // 2 + 20))
        self.screen.blit(hint_text, hint_rect)
    
    def draw_timeline(self, progress: float, current_lap: int, total_laps: int):
        """
        Draw timeline scrubber bar at the top of the screen.
        Shows race progress and allows clicking to jump.
        """
        # Timeline bar dimensions
        bar_height = 30
        bar_margin = 20
        bar_x = 200  # Leave space for lap counter
        bar_width = self.width - bar_x - 200  # Leave space on right for buttons
        bar_y = 10
        
        # Background
        pygame.draw.rect(self.screen, (40, 40, 40), (bar_x, bar_y, bar_width, bar_height), border_radius=5)
        pygame.draw.rect(self.screen, (80, 80, 80), (bar_x, bar_y, bar_width, bar_height), 2, border_radius=5)
        
        # Progress fill
        fill_width = int(bar_width * progress)
        if fill_width > 0:
            pygame.draw.rect(self.screen, (0, 150, 255), (bar_x + 2, bar_y + 2, fill_width - 4, bar_height - 4), border_radius=3)
        
        # Lap markers
        for lap in range(1, total_laps + 1):
            lap_x = bar_x + int((lap / total_laps) * bar_width)
            if lap % 10 == 0:  # Major markers every 10 laps
                pygame.draw.line(self.screen, (150, 150, 150), (lap_x, bar_y), (lap_x, bar_y + bar_height), 2)
                lap_text = self.font_tiny.render(str(lap), True, (150, 150, 150))
                self.screen.blit(lap_text, (lap_x - 8, bar_y + bar_height + 2))
            elif lap % 5 == 0:  # Minor markers every 5 laps
                pygame.draw.line(self.screen, (80, 80, 80), (lap_x, bar_y + 5), (lap_x, bar_y + bar_height - 5), 1)
        
        # Current position indicator
        pos_x = bar_x + int(progress * bar_width)
        pygame.draw.polygon(self.screen, (255, 255, 255), [
            (pos_x, bar_y + bar_height),
            (pos_x - 6, bar_y + bar_height + 8),
            (pos_x + 6, bar_y + bar_height + 8)
        ])
        
        # Lap counter on the left
        lap_label = f"LAP {current_lap}/{total_laps}"
        lap_text = self.font_large.render(lap_label, True, self.COLOR_TEXT)
        self.screen.blit(lap_text, (20, bar_y + 3))
        
        # Store timeline rect for click handling
        self.timeline_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        self.timeline_bar_x = bar_x
        self.timeline_bar_width = bar_width
        
    def draw_lap_controls(self, current_lap: int, total_laps: int):
        """
        Draw lap jump buttons (<<, <, >, >>).
        """
        btn_size = 35
        btn_y = 10
        start_x = self.width - 180
        
        self.btn_lap_start = pygame.Rect(start_x, btn_y, btn_size, btn_size)
        self.btn_lap_prev = pygame.Rect(start_x + 40, btn_y, btn_size, btn_size)
        self.btn_lap_next = pygame.Rect(start_x + 80, btn_y, btn_size, btn_size)
        self.btn_lap_end = pygame.Rect(start_x + 120, btn_y, btn_size, btn_size)
        
        buttons = [
            (self.btn_lap_start, "<<"),
            (self.btn_lap_prev, "<"),
            (self.btn_lap_next, ">"),
            (self.btn_lap_end, ">>"),
        ]
        
        mouse_pos = pygame.mouse.get_pos()
        
        for rect, label in buttons:
            is_hover = rect.collidepoint(mouse_pos)
            color = self.COLOR_BTN_HOVER if is_hover else self.COLOR_BTN_NORMAL
            
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 1, border_radius=5)
            
            text = self.font_small.render(label, True, self.COLOR_TEXT)
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)
            
    def handle_input(self, event, engine):
        """
        Handle UI clicks to control engine.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            
            # Strategy buttons
            if self.btn_push.collidepoint(mouse_pos):
                engine.set_mode("PUSH")
            elif self.btn_normal.collidepoint(mouse_pos):
                engine.set_mode("NORMAL")
            elif self.btn_conserve.collidepoint(mouse_pos):
                engine.set_mode("CONSERVE")
            elif self.btn_box.collidepoint(mouse_pos):
                if engine.player_state.pit_requested:
                    engine.cancel_pit()
                else:
                    current = engine.player_state.compound
                    next_compound = "MEDIUM" if current == "SOFT" else ("HARD" if current == "MEDIUM" else "SOFT")
                    engine.request_pit(next_compound)
            
            # Timeline scrubber
            elif hasattr(self, 'timeline_rect') and self.timeline_rect.collidepoint(mouse_pos):
                # Calculate progress from click position
                click_x = mouse_pos[0] - self.timeline_bar_x
                progress = click_x / self.timeline_bar_width
                progress = max(0.0, min(1.0, progress))
                engine.set_race_progress(progress)
            
            # Lap jump buttons
            elif hasattr(self, 'btn_lap_start') and self.btn_lap_start.collidepoint(mouse_pos):
                engine.jump_to_lap(1)
            elif hasattr(self, 'btn_lap_prev') and self.btn_lap_prev.collidepoint(mouse_pos):
                engine.jump_to_lap(engine.player_state.current_lap - 1)
            elif hasattr(self, 'btn_lap_next') and self.btn_lap_next.collidepoint(mouse_pos):
                engine.jump_to_lap(engine.player_state.current_lap + 1)
            elif hasattr(self, 'btn_lap_end') and self.btn_lap_end.collidepoint(mouse_pos):
                engine.jump_to_lap(engine.total_laps - 2)  # Jump to last 2 laps

