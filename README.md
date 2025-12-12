# Scummypy
Scummypy is a (Humongous Entertainment) SCUMM like game engine built with the Pygame library in Python. Its primary purpose is to help me learn Python, might as well make a game while so.

## Setup

### 1. Scummypy targets Python 3.10+ so check your version:

`python --version`

If Python is not installed, download it from: https://www.python.org/downloads/

On Windows, make sure “Add Python to PATH” is checked during install.

### 2. Install Pygame
`pip install pygame`

Verify installation:

`python -c "import pygame; print(pygame.version.ver)"`

### 3. Download Scummypy
From Github download
> scummypy (Folder containing all of the core Python)

>game_state.py

>main.py

### 2. Run the game
`python main.py`

I use VSCode on Windows so I "Run Python File in Terminal" directly on the main.py file.

Troubleshooting VSCode

`ModuleNotFoundError: No module named 'pygame'`

This means VS Code is using the wrong Python interpreter.

## Author
* **WindowsTV(Ryan)**

## Built With
* [Pygame](https://www.pygame.org/news)
