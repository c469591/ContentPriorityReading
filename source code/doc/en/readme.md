
# Content Priority Speaking NVDA Add-on

Speak plain text content before control information for a better user experience.

## Download

* You can
[click here to download the latest version](https://github.com/c469591/ContentPriorityReading/raw/main/content_priority_reading%20V0.3.nvda-addon)
of the NVDA add-on.
* You can also visit my GitHub repository page
[Click here to go to the Content Priority Speaking GitHub repository](https://github.com/c469591/ContentPriorityReading)

### Compatibility

Tested working with NVDA 2024.1 and above

## Features

* Smart speech reordering: Automatically places text content before control type information
* Multi-language support: Pure API implementation, supports all languages supported by NVDA
* Real-time toggle: One-key enable/disable functionality
* Debug mode: Developer-friendly detailed log output
* Diagnostic tools: Built-in various diagnostic and testing features

## Keyboard Shortcuts

### Default Shortcut

* NVDA+Ctrl+Shift+Y: Toggle content priority speaking on/off

### Customizable Shortcuts

The following features can be assigned custom shortcuts through NVDA's Input Gestures dialog:

* Toggle debug mode: View detailed speech sequence processing information
* Test reordering function: Demonstrate speech reordering effect
* Show add-on status: View current settings and last processed sequence

## Usage

### Basic Usage

1. Press `NVDA+Ctrl+Shift+Y` to enable the feature
1. Browse web pages or applications normally
1. Notice the change in speech order: content will be spoken before control types

### Example Effect

Before enabling: "button OK"
After enabling: "OK button"

Before enabling: "link Home"
After enabling: "Home link"

You can also open this test page to test the effect with content priority speaking enabled
[Click here to open the test page](https://twapi.lambgui.com/lamb_gui/html/test_speech.html)

## Troubleshooting

### When the order doesn't change as expected

If you find that the add-on is not working properly in some cases, you can collect diagnostic information by following these steps:

#### 1. Enable Debug Mode

1. Open NVDA menu → Preferences → Settings → Select Debug in the Log level dropdown,
then tab to OK and press enter
1. Open NVDA menu → Preferences → Input Gestures
1. Find "Toggle debug mode" under the "Content Priority Speaking" category
1. Assign a shortcut key to it (e.g., NVDA+Ctrl+Shift+D)
1. Press the assigned shortcut to enable debug mode
1. Confirm you hear "Debug mode enabled"

#### 2. Reproduce the Problem

1. Browse web pages or use software as you normally would
1. Try to reproduce the speech order issue on problematic pages or controls
1. Test several different control types (buttons, links, text boxes, etc.)

#### 3. Copy Log Information

1. Open NVDA menu → Tools → View Log
1. In the log window, press `Ctrl+A` to select all content
1. Press `Ctrl+C` to copy the log content
1. Paste the copied log content into a text file or email and send it to me at
c469591@mail.batol.net

#### 4. Disable Debug Mode and Contact Developer

After reproducing the problem, remember to press the same shortcut to disable debug mode to avoid generating too much log information.


## Changelog

### V0.3

1. Refactored using official filter_speechSequence API, improving compatibility with other add-ons
2. Using PropertyTextCommand for precise marking of control types and states, completely solving plain text misidentification issues
3. Extended reordering scope: Not only control types (links, buttons, etc.), but states (selected, pressed, etc.) are also moved to the end
4. Added configuration saving feature, automatically remembers on/off state after restarting NVDA
5. Added multi-language support: Traditional Chinese, Simplified Chinese, English
6. Respects user settings: Won't speak properties that users have disabled in settings

### V0.21

1. Use precise control matching to avoid incorrect sorting
2. Added a test HTML file

### v0.2

* Fixed conflicts with other add-ons that need to capture speech content
