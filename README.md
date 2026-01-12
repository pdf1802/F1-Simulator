# F1 Strategy Engineer - What-If Simulator

Un simulador visual 2D que te permite revivir carreras reales de F1 y experimentar con estrategias alternativas.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Pygame](https://img.shields.io/badge/Pygame-2.5+-green)
![FastF1](https://img.shields.io/badge/FastF1-3.0+-red)

## 🏎️ ¿Qué es esto?

Carga datos históricos reales (2022-2025) y responde preguntas como:

> *"¿Y si Sainz hubiera parado en vuelta 25 en vez de 30? ¿Habría adelantado a Leclerc?"*

- **Ghosts** = Los demás pilotos siguen exactamente lo que hicieron en la carrera real
- **Tu piloto** = Controlas su estrategia y ves cómo afecta al resultado

## 🚀 Instalación

```bash
# Clonar e instalar dependencias
cd f1-complete-war-room
pip install -r requirements.txt

# Ejecutar
python main.py
```

## 🎮 Controles

| Tecla/Acción | Efecto |
|--------------|--------|
| `SPACE` | Pausar / Reanudar |
| `ESC` | Salir |
| `R` | Activar lluvia (sandbox) |
| Click en timeline | Saltar a ese punto |
| `<<` `<` `>` `>>` | Navegar vueltas |
| `PUSH` | Modo agresivo (+desgaste) |
| `NORMAL` | Modo estándar |
| `SAVE` | Modo conservador (-desgaste) |
| `BOX BOX` | Solicitar parada en boxes |

## 📊 Características

- **Datos reales**: Tiempos de vuelta, pit stops, posiciones históricas
- **Comparación en vivo**: Muestra `+2 vs REAL` si vas mejor que la realidad
- **Timeline interactivo**: Salta a cualquier vuelta
- **Todos los coches**: Visualiza la carrera completa, no solo tu piloto
- **Física simplificada**: Desgaste de neumáticos y penalizaciones por lluvia

## 📁 Estructura

```
├── main.py                 # Punto de entrada
├── requirements.txt        # Dependencias
├── cache/                  # Caché de FastF1
└── src/
    ├── data/
    │   ├── loader.py       # Carga de datos FastF1
    │   └── mapper.py       # Transformación coordenadas
    ├── core/
    │   ├── sim_engine.py   # Motor What-If
    │   ├── physics.py      # Física de neumáticos
    │   └── weather.py      # Sistema de clima
    └── ui/
        ├── menu.py         # Menú de selección
        └── renderer.py     # Renderizado Pygame
```

## 📝 Notas

- La primera carga de una carrera puede tardar ~30 segundos (descarga de datos)
- Las carreras posteriores cargan desde caché
- Requiere conexión a internet para la primera descarga

## 🔧 Stack

- **FastF1**: Datos oficiales de F1
- **Pygame**: Renderizado 2D
- **SciPy**: Interpolación de telemetría
- **Pandas/NumPy**: Procesamiento de datos
