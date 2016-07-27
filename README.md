# SpotiPi

Flask web server hooked up to PySpotify in order to control Spotify streaming over Raspberry Pi speakers.

Use's Python 2.

## Installation

1. Run ```pip install -r requirements.txt```
2. Copy the default config to ```config.json``` and edit with Spotify username and password
3. Run ```python server.py```

Web interface will be accessible on port 3000 by default. You may need to configure speakers separately. Uses Python lib for AlsaSink to play to the speakers. Needs a seperate package installed.