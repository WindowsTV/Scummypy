@echo off
echo Creating scummypy_demo project structure...

REM Base directory
REM mkdir scummypy_demo
REM cd scummypy_demo

REM scummypy package
mkdir scummypy
cd scummypy
type nul > __init__.py
type nul > core.py
type nul > room.py
type nul > actor.py
type nul > costume.py
type nul > resources.py
type nul > audio.py
cd ..

REM game package
mkdir game
cd game
type nul > __init__.py
type nul > game_state.py

mkdir rooms
cd rooms
type nul > __init__.py
type nul > street.py
cd ..
cd ..

REM assets
mkdir assets

mkdir assets\rooms
type nul > assets\rooms\street_bg.png

mkdir assets\costumes
type nul > assets\costumes\sam.png
type nul > assets\costumes\sam.json

mkdir assets\audio
mkdir assets\audio\music
type nul > assets\audio\music\street_theme.ogg

mkdir assets\audio\sfx
type nul > assets\audio\sfx\click.wav

REM main entry point
type nul > main.py

echo Done! Your scummypy_demo project is ready.
pause
