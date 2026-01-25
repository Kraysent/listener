This is an app which is basically https://wisprflow.ai/ but with local model. On startup it will listen for Right Option button and, when pressed, will start recording, when pressed again, will stop recording. After transcription is completed it will:

1. try to add the text to whatever textbox is active at the moment
2. will save the text to clipboard

Made for MacOS, `make dmg` will build .dmg installer. Do not forget to (probably manually) add permissions:
1. Input Detection
2. Accessiblity
3. Microphone

Maybe the app will request some of them, maybe not.

Mostly vibecoded so use at your own risk. 
