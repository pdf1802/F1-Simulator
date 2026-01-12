"""
F1 Strategy Engineer - What-If Race Simulator
Replays REAL race data while letting you modify one driver's strategy.
"""

import sys
import pygame
from src.data.loader import F1DataLoader
from src.data.mapper import CoordinateMapper
from src.core.sim_engine import WhatIfSimEngine
from src.core.physics import PhysicsModel
from src.core.weather import WeatherSystem
from src.ui.menu import MenuScreen
from src.ui.renderer import GameRenderer

# Screen configuration
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
WINDOW_FLAGS = pygame.RESIZABLE

def main():
    # 1. Init Pygame
    pygame.init()
    pygame.display.set_caption("F1 Strategy Engineer - What-If Simulator")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), WINDOW_FLAGS)
    clock = pygame.time.Clock()
    
    # 2. Menu for race selection
    loader = F1DataLoader()
    menu = MenuScreen(screen, loader)
    
    try:
        year, gp, player_driver = menu.run()
    except SystemExit:
        return
        
    # 3. Loading Phase
    loading_font = pygame.font.SysFont("Arial", 28)
    
    def show_loading(message: str):
        screen.fill((20, 20, 20))
        text = loading_font.render(message, True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
    
    show_loading(f"Loading {year} {gp}...")
    
    # Load session
    session = loader.load_session(year, gp, 'R')
    track_coords = loader.get_track_coordinates(session)
    
    # Load FULL race data for all drivers
    show_loading("Loading race data for all drivers...")
    
    def progress_callback(driver, current, total):
        show_loading(f"Loading: {driver} ({current}/{total})")
    
    race_data = loader.load_full_race_data(session, progress_callback=progress_callback)
    
    if player_driver not in race_data:
        if race_data:
            player_driver = list(race_data.keys())[0]
            print(f"Warning: Selected driver not available, using {player_driver}")
        else:
            show_loading("Error: No race data available!")
            pygame.time.wait(3000)
            pygame.quit()
            return
    
    # Get reference telemetry for track rendering
    show_loading("Loading track layout...")
    reference_telemetry = loader.get_reference_lap_telemetry(session, player_driver)
    
    # Get total laps
    total_laps = max(d.total_laps for d in race_data.values())
    
    # 4. Init Systems
    show_loading("Initializing simulation...")
    
    mapper = CoordinateMapper(SCREEN_WIDTH, SCREEN_HEIGHT, padding=80)
    weather = WeatherSystem()
    weather.load_from_session(session)
    
    physics = PhysicsModel()
    
    engine = WhatIfSimEngine(
        race_data=race_data,
        reference_telemetry=reference_telemetry,
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
    
    # Get player info for display
    player_info = race_data[player_driver]
    print(f"\n{'='*50}")
    print(f"WHAT-IF MODE: {player_driver} - {player_info.driver_name}")
    print(f"Real Result: P{player_info.final_position}")
    print(f"Real Pit Stops: Laps {player_info.get_pit_stops()}")
    print(f"{'='*50}")
    print("\nControls:")
    print("  SPACE - Pause/Resume")
    print("  ESC   - Quit")
    print("  Click timeline to jump")
    print("  Modify strategy and see what happens!\n")
    
    while running:
        dt = clock.tick(fps) / 1000.0
        
        # Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    engine.toggle_pause()
                elif event.key == pygame.K_r:
                    weather.toggle_sandbox()
                    weather.set_sandbox_rain(0.8 if weather.sandbox_mode else 0.0)
            
            if not engine.paused:
                renderer.handle_input(event, engine)
            
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), WINDOW_FLAGS)
                mapper = CoordinateMapper(event.w, event.h, padding=80)
                renderer = GameRenderer(screen, mapper)
                renderer.track_surface = None
        
        # Update simulation
        engine.update(dt)
        
        # Render
        screen.fill(renderer.COLOR_BG)
        
        # Draw track
        renderer.draw_track(track_coords)
        
        # Draw all cars
        renderer.draw_all_cars(engine.cars, player_driver)
        
        # Draw timeline
        race_progress = engine.get_race_progress()
        renderer.draw_timeline(race_progress, engine.player_state.current_lap, total_laps)
        renderer.draw_lap_controls(engine.player_state.current_lap, total_laps)
        
        # Draw dashboard with comparison
        rain_level = weather.get_current_weather(engine.race_time)
        player_position = engine.get_player_position()
        comparison = engine.get_historical_comparison()
        
        renderer.draw_dashboard(
            engine.player_state, 
            total_laps, 
            rain_level,
            player_position,
            len(engine.cars),
            comparison
        )
        
        # Draw leaderboard
        sorted_cars = engine.get_sorted_cars()
        renderer.draw_leaderboard(sorted_cars, player_driver)
        
        # Draw controls
        renderer.draw_controls(
            engine.player_state.mode,
            engine.player_state.pit_requested
        )
        
        # Weather indicator
        if weather.sandbox_mode:
            font = pygame.font.SysFont("Arial", 20)
            txt = font.render(f"SANDBOX WEATHER: {weather.sandbox_intensity:.0%}", True, (0, 255, 255))
            screen.blit(txt, (20, 50))
        
        # Pause overlay
        if engine.paused:
            renderer.draw_pause_overlay()
        
        pygame.display.flip()
        
    # Show final comparison
    final_comparison = engine.get_historical_comparison()
    print(f"\n{'='*50}")
    print("FINAL RESULT")
    print(f"Your Position: P{engine.player_state.position}")
    print(f"Real Position: P{final_comparison['real_final_position']}")
    delta = final_comparison['real_final_position'] - engine.player_state.position
    if delta > 0:
        print(f"You did BETTER by {delta} positions! 🎉")
    elif delta < 0:
        print(f"You did WORSE by {-delta} positions.")
    else:
        print("Same result as reality.")
    print(f"{'='*50}\n")
        
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
