install:
	uv sync

install-dev:
	uv sync --all-extras

check:
	@output=$$(copier check-update --answers-file .template.yaml 2>&1) || true; \
	if echo "$$output" | grep -q "up-to-date"; then \
		true; \
	elif echo "$$output" | grep -q "New template version"; then \
		echo "Template update available, run make update-template"; \
	else \
		echo "$$output"; \
	fi
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

new-branch:
	@read -p "Branch name: " branch_name && \
	branch_name=$${branch_name// /-} && \
	base=$$(git remote show origin | sed -n '/HEAD branch/s/.*: //p') && \
	echo "Selecting $$base branch as default" && \
	git fetch origin $$base && \
	git checkout -b $$branch_name origin/$$base && \
	git push -u origin $$branch_name

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
