# Apple Silicon macOS preview

Requires macOS 14 or newer and Google Chrome. Intel is not included in this build.

The installer is a self-contained `.app`: it includes a relocatable arm64 CPython runtime and wheels. No Homebrew, system Python, administrator access, login item, or background service is required. Models are downloaded on first use. The current package is a local preview, without Developer ID signing or notarization.

## Reproduce the build

1. Download the exact Python archive in `runtime-sources.json`, verify its SHA256, and extract it into a work directory.
2. Run that runtime's `bin/python3 -m pip install --only-binary=:all: -r native/macos/requirements.lock`.
3. CaptionCraft also needs the Deno binary from the same source manifest, after verifying its SHA256.
4. Run `python3 native/macos/build.py --product PRODUCT --runtime /path/to/python --output /empty/output` (add `--deno /path/to/deno` for CaptionCraft). Replace PRODUCT with this repository's name.
5. Archive the resulting app using `ditto -c -k --sequesterRsrc --keepParent "PRODUCT Installer.app" "PRODUCT-Mac.zip"` to preserve executable bits and symlinks.

The lock contains the tested runtime dependency set, shared by both preview installers. AudioScribe does not activate the streaming or video-download components. Package notices and all dependency `.dist-info` licenses must remain included.

## Installation layout

`~/Library/Application Support/PRODUCT/Extension` is the exact, stable folder to load in `chrome://extensions`. In the macOS folder picker, press Command-Shift-G, paste that path, press Return, then Select. Do not select the ZIP, installer app, icons, or _locales subfolder.

`Versions/<unique build>/` holds the app runtime. `Data/` holds private pairing settings and downloaded models. Updates leave old runtimes, extension backups, and Data intact. Close any active transcription before updating and reload the extension afterward. Do not move the installed Extension folder.

The installer writes only its own manifest to `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/`. This manifest has an absolute executable path and one explicit extension origin. The host checks the origin again, creates a 0600 token file, binds only loopback, and stops its own recognition process when Chrome closes the native connection. Chrome Beta/Canary, Chromium, Edge, and Safari are outside this preview's installer support.

The installer also has a CLI for test installations: `Contents/MacOS/install --install --destination /test/product --chrome-directory /test/NativeMessagingHosts`. Without those optional paths, `--install` installs for the current user. The GUI requires the user to click Install.

## Validation

Run the original Python and JavaScript suites and `tests/test_macos.py`. Additional acceptance checks must exercise a relocated built app, native framing and EOF shutdown, actual recognition and translation, and Chrome's user-granted tab audio capture. An import check alone does not verify those capabilities.

Reference: [Chrome Native Messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging), [CTranslate2 installation](https://opennmt.net/CTranslate2/installation.html), [Python standalone releases](https://github.com/astral-sh/python-build-standalone/releases).
