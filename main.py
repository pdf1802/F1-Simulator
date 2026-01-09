"""
F1 Strategy Engineer - Main Entry Point
Initializes the game loop, integrated systems, and runs the simulation.
Supports windowed mode, pause, and multi-car display.
"""

import sys
import pygame
from src.data.loader import F1DataLoader
from src.data.mapper import CoordinateMapper
from src.core.sim_engine import SimEngine
from src.core.physics import PhysicsModel
from src.core.weather import WeatherSystem
from src.ui.menu import MenuScreen
from src.ui.renderer import GameRenderer

# Screen configuration
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
WINDOW_FLAGS = pygame.RESIZABLE  # Windowed, resizable

def main():
    # 1. Init Pygame
    pygame.init()
    pygame.display.set_caption("F1 Strategy Engineer v1.0")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), WINDOW_FLAGS)
    clock = pygame.time.Clock()
    
    # 2. Splash / Loading / Menu
    loader = F1DataLoader()
    menu = MenuScreen(screen, loader)
    
    try:
        year, gp, player_driver = menu.run()
    except SystemExit:
        return
        
    # 3. Loading Phase - Show loading screen
    loading_font = pygame.font.SysFont("Arial", 28)
    
    def show_loading(message: str):
        screen.fill((20, 20, 20))
        text = loading_font.render(message, True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
        pygame.display.flip()
        # Process events to keep window responsive
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
    
    show_loading(f"Loading {year} {gp}...")
    
    # Load session
    session = loader.load_session(year, gp, 'R')
    track_coords = loader.get_track_coordinates(session)
    
    # Load ALL drivers telemetry
    show_loading(f"Loading all drivers telemetry...")
    
    def progress_callback(driver, current, total):
        show_loading(f"Loading telemetry: {driver} ({current}/{total})")
    
    all_telemetry = loader.get_all_drivers_telemetry(session, progress_callback=progress_callback)
    
    if player_driver not in all_telemetry:
        # Fallback if player driver data isn't available
        if all_telemetry:
            player_driver = list(all_telemetry.keys())[0]
            print(f"Warning: Selected driver not available, using {player_driver}")
        else:
            show_loading("Error: No telemetry data available!")
            pygame.time.wait(3000)
            pygame.quit()
            return
    
    # Get total laps
    try:
        total_laps = int(session.total_laps) if hasattr(session, 'total_laps') and session.total_laps else 60
    except:
        total_laps = 60
    
    # 4. Init Systems
    show_loading("Initializing simulation...")
    
    mapper = CoordinateMapper(SCREEN_WIDTH, SCREEN_HEIGHT, padding=80)
    weather = WeatherSystem()
    weather.load_from_session(session)
    
    physics = PhysicsModel()
    
    engine = SimEngine(
        all_telemetry=all_telemetry,
        physics=physics,
        weather=weather,
        player_driver=player_driver,
        total_laps=total_laps
    )
    
    renderer = GameRenderer(screen, mapper)
    
    # Pre-compute track pixels
    mapper.fit_to_screen(track_coords)
    
    # 5. Game Loop
    running = True
    fps = 60
    
    print(f"\nRace started! You are driving as {player_driver}")
    print("Controls:")
    print("  SPACE - Pause/Resume")
    print("  ESC   - Quit")
    print("  R     - Toggle rain (sandbox)")
    print("  Click buttons for strategy\n")
    
    while running:
        dt = clock.tick(fps) / 1000.0  # Seconds
        
        # Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # Keyboard controls
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    engine.toggle_pause()
                elif event.key == pygame.K_r:
                    weather.toggle_sandbox()
                    weather.set_sandbox_rain(0.8 if weather.sandbox_mode else 0.0)
            
            # Pass input to renderer (buttons) - only when not paused
            if not engine.paused:
                renderer.handle_input(event, engine)
            
            # Handle window resize
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), WINDOW_FLAGS)
                renderer = GameRenderer(screen, mapper)
                mapper = CoordinateMapper(event.w, event.h, padding=80)
                renderer.track_surface = None  # Force track redraw
        
        # Simulation Update (respects pause internally)
        engine.update(dt)
        
        # Render
        screen.fill(renderer.COLOR_BG)
        
        # Draw layers
        renderer.draw_track(track_coords)
        renderer.draw_all_cars(engine.all_cars, player_driver)
        
        # Draw timeline and lap controls
        race_progress = engine.get_race_progress()
        renderer.draw_timeline(race_progress, engine.player_state.lap, total_laps)
        renderer.draw_lap_controls(engine.player_state.lap, total_laps)
        
        rain_level = weather.get_current_weather(engine.current_time)
        player_position = engine.get_player_position()
        renderer.draw_dashboard(
            engine.player_state, 
            total_laps, 
            rain_level,
            player_position,
            len(engine.all_cars)
        )
        
        sorted_cars = engine.get_sorted_cars()
        renderer.draw_leaderboard(sorted_cars, player_driver)
        
        renderer.draw_controls(
            engine.player_state.mode,
            engine.player_state.pit_requested
        )
        
        # Draw weather sandbox indicator (moved to not overlap timeline)
        if weather.sandbox_mode:
            font = pygame.font.SysFont("Arial", 20)
            txt = font.render(f"SANDBOX WEATHER: {weather.sandbox_intensity:.0%}", True, (0, 255, 255))
            screen.blit(txt, (20, 50))
        
        # Pause overlay (draw last)
        if engine.paused:
            renderer.draw_pause_overlay()
        
        pygame.display.flip()
        
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
