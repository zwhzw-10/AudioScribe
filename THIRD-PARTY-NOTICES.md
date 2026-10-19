# Mac preview runtime notices

Project source and Logo: MIT, see LICENSE. Third-party software is not relicensed by this project.

The bundled Python 3.12.15 is the Apple Silicon install-only distribution from astral-sh/python-build-standalone, release 20261013; its Python license is included at runtime/lib/python3.12/LICENSE.txt. Tcl/Tk and linked runtime libraries retain their respective upstream licenses. See the distribution source and build metadata at https://github.com/astral-sh/python-build-standalone/releases/tag/20261013.

Python wheel metadata and license files are retained under runtime/lib/python3.12/site-packages/*.dist-info. The exact tested versions are listed in native/macos/requirements.lock. Components include faster-whisper (MIT), CTranslate2 (MIT), NumPy (BSD and bundled library notices), PyAV (BSD with linked FFmpeg library licenses), ONNX Runtime (MIT), sherpa-onnx (Apache-2.0), SentencePiece (Apache-2.0), Sacremoses (MIT), subword-nmt (MIT), and yt-dlp and its dependencies (see packaged licenses). Preserve those license files when redistributing.

CaptionCraft additionally bundles Deno 2.9.7 from https://github.com/denoland/deno/releases/tag/v2.9.7. Its MIT license is included alongside the binary; upstream source contains the full dependency and third-party license inventory. AudioScribe does not bundle Deno.

No separately downloaded Whisper, Sherpa, or translation model weights, and no user recordings, are included in the installer. Small VAD assets shipped inside the upstream recognition wheel remain included. Whisper, Sherpa, and Argos model packages are downloaded separately on demand and have their own model-specific licensing. Do not infer a model license from this repository's MIT license.
