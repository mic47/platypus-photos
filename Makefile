ci:
	black .
	mypy  --no-incremental .
	pylint *py gallery db data_model
