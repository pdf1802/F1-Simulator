"""
Menu Screen
Simple Pygame-based menu for selecting Year, Grand Prix, and Driver.
"""

import pygame
from typing import Tuple, List, Optional
from ..data.loader import F1DataLoader

class MenuScreen:
    def __init__(self, screen: pygame.Surface, loader: F1DataLoader):
        self.screen = screen
        self.loader = loader
        self.width = screen.get_width()
        self.height = screen.get_height()
        
        # Colors
        self.BG_COLOR = (30, 30, 30)
        self.TEXT_COLOR = (255, 255, 255)
        self.HIGHLIGHT_COLOR = (255, 0, 0)
        
        # Fonts
        self.title_font = pygame.font.SysFont("Arial", 48, bold=True)
        self.item_font = pygame.font.SysFont("Arial", 32)
        
    def draw_text_centered(self, text: str, y: int, color: Tuple[int,int,int]):
        surf = self.item_font.render(text, True, color)
        rect = surf.get_rect(center=(self.width // 2, y))
        self.screen.blit(surf, rect)
        return rect
        
    def run(self) -> Tuple[int, str, str]:
        """
        Main menu loop. 
        Returns (year, race_name, driver_code)
        """
        step = 0 # 0: Year, 1: Race, 2: Driver
        
        selected_year = 2024
        selected_race = ""
        selected_driver = ""
        
        # Cache lists
        years = self.loader.AVAILABLE_YEARS
        races = []
        drivers = []
        
        selection_idx = 0
        
        clock = pygame.time.Clock()
        running = True
        
        while running:
            self.screen.fill(self.BG_COLOR)
            
            # Title
            title_surf = self.title_font.render("F1 STRATEGY ENGINEER", True, self.HIGHLIGHT_COLOR)
            self.screen.blit(title_surf, title_surf.get_rect(center=(self.width//2, 80)))
            
            # Step Logic
            current_options = []
            if step == 0:
                self.draw_text_centered("Select Season", 150, (200, 200, 200))
                current_options = [str(y) for y in years]
            elif step == 1:
                self.draw_text_centered(f"Select Grand Prix ({selected_year})", 150, (200, 200, 200))
                current_options = races
            elif step == 2:
                self.draw_text_centered(f"Select Driver ({selected_race})", 150, (200, 200, 200))
                current_options = [f"{code} - {name}" for code, name in drivers]
                
            # Render Options
            # Simple scroll/list implementation
            start_y = 220
            items_per_page = 10
            start_idx = max(0, selection_idx - items_per_page // 2)
            end_idx = min(len(current_options), start_idx + items_per_page)
            
            for i in range(start_idx, end_idx):
                opt = current_options[i]
                color = self.HIGHLIGHT_COLOR if i == selection_idx else self.TEXT_COLOR
                self.draw_text_centered(opt, start_y + (i - start_idx) * 50, color)
            
            pygame.display.flip()
            
            # Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                    
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        selection_idx = max(0, selection_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        selection_idx = min(len(current_options) - 1, selection_idx + 1)
                    elif event.key == pygame.K_RETURN:
                        # Confirm selection
                        if step == 0: # Year selected
                            selected_year = int(current_options[selection_idx])
                            # Load races for this year
                            print(f"Loading {selected_year} schedule...")
                            races = self.loader.get_available_races(selected_year)
                            if not races:
                                print("No races found!")
                                continue
                            step = 1
                            selection_idx = 0
                            
                        elif step == 1: # Race selected
                            selected_race = current_options[selection_idx]
                            # Load session just to get driver list? 
                            # This might take a moment, show loading
                            self.draw_text_centered("Loading Session Data...", self.height - 100, self.HIGHLIGHT_COLOR)
                            pygame.display.flip()
                            
                            session = self.loader.load_session(selected_year, selected_race, 'R')
                            raw_drivers = self.loader.get_drivers(session)
                            drivers = raw_drivers # List of tuples
                            step = 2
                            selection_idx = 0
                            
                        elif step == 2: # Driver selected
                            # Get just the code from the string "VER - Max Verstappen"
                            # Actually drivers list is tuples (code, name)
                            # But current_options is strings.
                            # We can just use the index map to the 'drivers' list
                            selected_driver = drivers[selection_idx][0]
                            return selected_year, selected_race, selected_driver
                            
                    elif event.key == pygame.K_ESCAPE:
                        if step > 0:
                            step -= 1
                            selection_idx = 0
                        else:
                            running = False
            
            clock.tick(30)
            
        pygame.quit()
        exit()
