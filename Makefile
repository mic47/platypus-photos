ci:
	black .
	mypy  --no-incremental .
	pylint gallery db data_model annots apps utils
