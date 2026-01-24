# BOSS IR-2 Controller 🎸

An unofficial, open-source Python controller and preset manager for the **BOSS IR-2 Amp & Cabinet** pedal.

![GUI Screenshot](docs/gui.PNG)

## Features

- 🎛️ **Full Real-time Control**: Adjust Gain, Level, Ambience, and 3-Band EQ.
- 🔊 **Amp Model Selection**: Switch between all 11 amp models instantly.
- 💾 **Preset Manager**: Save and Load your favorite tones to JSON files.
- 🔄 **Bidirectional Sync**: Read the current state from the pedal to the GUI.
- 🖥️ **Modern GUI**: Dark mode interface with rotary knobs (using `customtkinter` & `tkdial`).

## Installation

1. **Install Python 3.10+**
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Connect your BOSS IR-2 via USB.
2. Run the GUI:
   ```bash
   python run.py
   ```
3. Click **SYNC FROM PEDAL** to read current settings.
4. Enjoy tweaking!

## Project Structure

- `src/`: Main application code (GUI and Control Logic).
- `reverse_engineering/`: Jupyter notebooks used to decipher the SysEx protocol.
- `docs/`: Documentation and screenshots.

## Requirements

- `mido`
- `python-rtmidi`
- `customtkinter`
- `tkdial`

## Disclaimer

This is an unofficial project and is not affiliated with Roland Corporation or BOSS. Use at your own risk.
