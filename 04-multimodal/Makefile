.PHONY: venv install run

venv:
	python -m venv .venv
	.venv/Scripts/python -m pip install --upgrade pip setuptools wheel

install: venv
	.venv/Scripts/python -m pip install -r requirements.txt

run: install
	.venv/Scripts/python -m src.main


