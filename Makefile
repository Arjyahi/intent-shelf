PYTHON ?= python
PIP ?= $(PYTHON) -m pip
NPM ?= npm

.PHONY: data-install data-validate data-preprocess data-split data-phase1 backend-install backend-dev backend-test frontend-install frontend-dev docker-up docker-down

data-install:
	$(PIP) install -r requirements-data.txt

data-validate:
	$(PYTHON) scripts/data/validate_raw_data.py

data-preprocess:
	$(PYTHON) scripts/data/preprocess_hm_data.py

data-split:
	$(PYTHON) scripts/data/create_time_split.py

data-phase1:
	$(PYTHON) scripts/data/run_phase1.py

backend-install:
	cd backend && $(PIP) install -r requirements.txt

backend-dev:
	cd backend && $(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 18001

backend-test:
	cd backend && $(PYTHON) -m pytest

frontend-install:
	cd frontend && $(NPM) install

frontend-dev:
	cd frontend && $(NPM) run dev -- --port 13000

docker-up:
	docker compose up --build

docker-down:
	docker compose down
