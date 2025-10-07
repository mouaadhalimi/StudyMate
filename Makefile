
.PHONY: run migrate
run:
	uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
migrate:
	alembic upgrade head
