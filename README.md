# MemeBoard by HoppouSan

Modern soundboard application with hotkeys, categories, favorites, automatic sound downloading from MyInstants-style links and **virtual microphone routing** for voice chats (Discord, Zoom, Teams etc.).

Perfect for memes in calls, streams or just having fun with friends.



## Features

- Paste MyInstants / sound-button links → auto-download & clean name extraction
- Custom categories + "All" / "Uncategorized" system
- Favorites (starred sounds appear first)
- Hotkey support (a–z, 0–9, F1–F12, space, arrows, enter, esc, …)
- Global **STOP ALL** with SPACE key or big red button
- Master volume slider + **separate virtual mic volume control** (0–200%)
- **Send to Voice Chat** toggle:
  - OFF → plays through your normal speakers/headset (you hear it)
  - ON  → routes audio through virtual null-sink → appears in voice chat
- Automatic creation of virtual audio cable + remapped microphone on Linux
- Always-on-top mode
- Dark modern UI with scrollable grid, elided long names + tooltips
- Right-click context menu on sounds (move category, set hotkey, favorite, delete)
- Saves settings (hotkeys, favorites, categories, volumes) in `config.json`

## Requirements

### Linux (Ubuntu / Debian / Fedora / Arch etc.)
- Python 3.8+
- `pulseaudio-utils` or `pipewire-pulse` (for `pactl`)
- `pavucontrol` (strongly recommended for debugging)

```bash
sudo apt install python3-pip pulseaudio-utils pavucontrol   
# or
sudo dnf install python3-pip pulseaudio-utils pavucontrol   
# or
sudo pacman -S python-pip pulseaudio pavuco


Windows / macOS

Python 3.8+
No extra audio tools needed (virtual cable not supported)ntro

pip install PySide6 pygame requestsl



Installation & Quick Start
From source (recommended for development)

git clone https://github.com/HoppouSan/MemeBoard.git
cd MemeBoard
pip install -r requirements.txt    # or manually install the 3 packages above
python main.py


Linux pre-built releases (planned)

.deb package for Debian/Ubuntu
.AppImage portable version
→ Coming soon in Releases

How to Use – Voice Chat Routing (Linux only)

Start MemeBoard → it creates automatically:
Virtual sink: MemeBoard_Virtual_Output
Remapped microphone: Virtual_Mic_Remap

Normal mode (hear yourself)
Leave Send to Voice Chat OFF
Choose your speakers/headset in Output (hear)
→ You hear sounds, but friends don't

Voice chat mode (friends hear memes)
Turn Send to Voice Chat ON
Sounds now play through the virtual sink
In Discord/Zoom/Teams → set Input Device / Microphone to
Virtual_Mic_Remap or Virtual_Mic_MemeBoard_Virtual_Output

If volume too quiet in voice chat
Use the Mic Vol slider (up to 200%) to boost the virtual microphone

Debugging tip
Install pavucontrol
→ Playback tab: see where MemeBoard plays
→ Recording tab: see if Discord receives audio from the remapped source

Keyboard Shortcuts

SPACE → Stop all sounds
Any assigned hotkey → play corresponding sound
Hotkeys work when window is focused (reliable on Wayland too)

Planned / Future Features

Tray icon / minimize to tray
Sound search/filter
Volume profiles (per category or global presets)
Drag & drop MP3 import
Windows/macOS virtual audio cable support (VB-Cable / BlackHole)
OBS / Stream integration




