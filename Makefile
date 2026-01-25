.PHONY: build clean install dmg help

build: clean
	uv run pyinstaller --distpath dist/app build_app.spec

clean:
	/bin/rm -rf dist build || true

dmg: build
	ln -s /Applications dist/app/Applications
	hdiutil create -volname "Listener" -srcfolder "dist/app" -ov -format UDZO "dist/Listener.dmg"

fix:
	uvx ruff check --fix .
	uvx ruff format .

help:
	@echo "Available targets:"
	@echo "  build    - Build the Listener.app bundle"
	@echo "  clean    - Remove build artifacts (dist/ and build/)"
	@echo "  install  - Build and install the app to /Applications/"
	@echo "  dmg      - Build the app and create a DMG file for distribution"
	@echo "  help     - Show this help message"
