# Gesture Automator - Android Touch Automation App

An Android app that records and replays touch gestures, enabling automation of taps, swipes, scrolls, and system gestures like pulling down the notification panel.

## Features

✅ **Record & Replay Gestures** - Capture your touch patterns and replay them
✅ **Multiple Gesture Types** - Supports taps, swipes, scrolls
✅ **Notification Panel Control** - Swipe down to open control center/notification panel
✅ **Save Sequences** - Store multiple gesture sequences for different tasks
✅ **Independent Execution** - Gestures run independently in the background
✅ **Customizable Timing** - Automatic delay detection between gestures

## Requirements

- Android 7.0 (API 24) or higher
- Accessibility Service permissions

## Installation

1. **Build the APK:**
   ```bash
   cd GestureAutomator
   ./gradlew assembleDebug
   ```
   The APK will be generated at: `app/build/outputs/apk/debug/app-debug.apk`

2. **Install on your device:**
   ```bash
   adb install app/build/outputs/apk/debug/app-debug.apk
   ```

3. **Open Android Studio:**
   - Open the `GestureAutomator` folder
   - Sync Gradle files
   - Run on your device or emulator

## Setup

### 1. Enable Accessibility Service

**Critical: The app requires accessibility permissions to execute gestures**

1. Open the Gesture Automator app
2. Tap "Enable Accessibility Service"
3. In Settings → Accessibility, find "Gesture Automator"
4. Toggle it ON
5. Accept the permission dialog

The app status should show "✓ Service Enabled" in green.

### 2. Grant Overlay Permission (if needed)

If prompted, allow the app to display over other apps for recording overlay.

## Usage

### Recording a Gesture Sequence

1. **Tap "Start Recording"** - Button turns red
2. **Perform your gestures** on the semi-transparent overlay:
   - Tap where you want clicks
   - Swipe for scrolling motions
   - The app records timing between gestures automatically
3. **Tap "Stop Recording"**
4. **Name your sequence** and tap "Save"

### Playing a Sequence

1. Find your saved sequence in the list
2. Tap the **"▶ Play"** button
3. The gestures will execute automatically

### Quick Actions

**Swipe Down Notification:**
- Tap "Quick Add: Swipe Down Notification"
- Instantly adds a pre-configured gesture to pull down the notification panel
- Play it anytime to open your notifications/control center

### Managing Sequences

- **Delete**: Tap the "Delete" button on any sequence
- **View Details**: Each sequence shows the number of gestures recorded

## Technical Details

### Gesture Types

- **TAP**: Single touch at a point (50ms duration)
- **SWIPE**: Touch and drag motion
- **SCROLL**: Similar to swipe, for scrolling content
- **SWIPE_DOWN_NOTIFICATION**: System gesture from top of screen

### How It Works

1. **Recording Phase**: 
   - Overlay captures touch events
   - Records coordinates, timing, and gesture type
   - Calculates delays between gestures

2. **Playback Phase**:
   - Accessibility Service executes GestureDescription objects
   - Gestures dispatched with precise timing
   - System-level touch injection

3. **Storage**:
   - Sequences saved in SharedPreferences as JSON
   - Gson library handles serialization
   - Persistent across app restarts

### Permissions Explained

- **BIND_ACCESSIBILITY_SERVICE**: Required to inject touch events
- **SYSTEM_ALERT_WINDOW**: For recording overlay
- **FOREGROUND_SERVICE**: Keeps service alive during automation

## Use Cases

- **Repetitive Task Automation**: Form filling, app navigation
- **Gaming**: Automate repetitive actions (check game ToS first)
- **Testing**: Test app workflows
- **Accessibility**: Help users with limited mobility
- **Quick Actions**: Open notification panel, navigate common paths

## Limitations

- Android 7.0+ only (requires GestureDescription API)
- Accessibility service must remain enabled
- Some apps may block accessibility injection (security apps, banking apps)
- Recording captures basic tap/swipe - complex multi-touch not supported yet

## Troubleshooting

### Gestures Not Playing

1. Check service status - should show green "✓ Service Enabled"
2. Go to Settings → Accessibility and verify service is ON
3. Restart the app after enabling service

### Recording Not Working

1. Ensure overlay permission is granted
2. Check if touches are being detected (toast messages appear)
3. Try restarting the app

### Service Keeps Disabling

1. Check battery optimization settings
2. Add app to battery whitelist
3. Disable battery optimization for Gesture Automator

## Privacy & Security

- **No Data Collection**: All data stays on your device
- **No Internet Permission**: App works completely offline
- **Local Storage Only**: Gestures saved in app's private storage
- **User Control**: You decide what gets recorded and played

## Future Enhancements

- Multi-touch gesture support
- Swipe gesture recording (currently tap-only)
- Loop/repeat options
- Conditional execution
- Import/export sequences
- Visual gesture editor
- Floating widget for quick playback

## Project Structure

```
GestureAutomator/
├── app/
│   ├── src/main/
│   │   ├── java/com/gestureautomator/app/
│   │   │   ├── MainActivity.kt              # Main UI
│   │   │   ├── AutomationAccessibilityService.kt  # Gesture execution
│   │   │   ├── GestureData.kt               # Data models
│   │   │   └── GestureStorageManager.kt     # Persistence
│   │   ├── res/
│   │   │   ├── layout/
│   │   │   │   ├── activity_main.xml
│   │   │   │   └── item_sequence.xml
│   │   │   ├── values/
│   │   │   │   ├── strings.xml
│   │   │   │   └── themes.xml
│   │   │   └── xml/
│   │   │       └── accessibility_service_config.xml
│   │   └── AndroidManifest.xml
│   └── build.gradle
├── build.gradle
├── settings.gradle
└── gradle.properties
```

## License

This is a demonstration project. Use responsibly and in accordance with app store policies and terms of service of apps you automate.

## Support

For issues or questions:
1. Check accessibility service is enabled
2. Review permissions granted
3. Check Android version compatibility (7.0+)

---

**Built with ❤️ for automation enthusiasts**
