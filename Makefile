.PHONY: build clean install help

build: clean
	uv run pyinstaller build_app.spec

clean:
	/bin/rm -rf dist build || true

install: build
	cp -r dist/Listener.app /Applications/

fix:
	uvx ruff check --fix .
	uvx ruff format .

help:
	@echo "Available targets:"
	@echo "  build    - Build the Listener.app bundle"
	@echo "  clean    - Remove build artifacts (dist/ and build/)"
	@echo "  install  - Build and install the app to /Applications/"
	@echo "  help     - Show this help message"
