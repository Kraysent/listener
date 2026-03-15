install:
	uv sync

install-dev:
	uv sync --all-extras

check:
	@find . \
		-name "*.py" \
		-not -path "./.venv/*" \
		-not -path "./.git/*" \
		-exec uv run python -m py_compile {} +
	@uvx ruff format \
		--quiet \
		--config=pyproject.toml \
		--check
	@uvx ruff check \
		--quiet \
		--config=pyproject.toml
	@uv run pytest \
		--quiet \
		--config-file=pyproject.toml

fix:
	@uvx ruff format \
		--quiet \
		--config=pyproject.toml
	@uvx ruff check \
		--quiet \
		--config=pyproject.toml \
		--fix

build:
	uv run pyinstaller --distpath dist/app build_app.spec

update-template:
	copier update \
		--skip-answered \
		--conflict inline \
		--answers-file .template.yaml

clean:
	/bin/rm -rf dist build || true

dmg: build
	ln -s /Applications dist/app/Applications
	hdiutil create -volname "Listener" -srcfolder "dist/app" -ov -format UDZO "dist/Listener.dmg"
