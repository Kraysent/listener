# Listener

A macOS menu bar app that transcribes speech to text using OpenAI's Whisper model and copies the result to your clipboard.

## Features

- Menu bar icon shows current status (🎤 ready, 🔴 recording, ⏳ transcribing)
- Press FN key to start/stop recording
- Local Whisper model via faster-whisper (no API key required, optimized for speed)
- Automatically copies transcription to clipboard

## Installation

1. Install dependencies:
   ```bash
   pip install -e .
   ```

2. Run the app:
   ```bash
   python main.py
   ```

## Usage

1. Launch the app - you'll see a 🎤 icon in your menu bar
2. Wait for the "Ready" notification (model loading takes a few seconds on first run)
3. Press the **FN key** to start recording
4. Speak into your microphone
5. Press the **FN key** again to stop and transcribe
6. The transcribed text is automatically copied to your clipboard

## Permissions

The app requires:
- **Microphone access**: You'll be prompted when first recording
- **Accessibility permissions**: Required for global hotkey detection (System Settings → Privacy & Security → Accessibility)

## Configuration

### Whisper Model

Edit the `WHISPER_MODEL` constant in `main.py` to change transcription quality:

| Model    | Speed   | Quality | VRAM    |
|----------|---------|---------|---------|
| `tiny`   | Fastest | Lower   | ~1 GB   |
| `base`   | Fast    | Good    | ~1 GB   |
| `small`  | Medium  | Better  | ~2 GB   |
| `medium` | Slow    | Best    | ~5 GB   |

Default is `base` for a good balance of speed and accuracy.

### Sample Rate

The `SAMPLE_RATE` constant (default: 16000 Hz) matches Whisper's expected input format.

### Hotkey

The `FN_KEY_CODE` constant (default: 63) can be changed to use a different key. Common macOS key codes:
- 63: FN
- 55: Command
- 58: Option
- 59: Control
