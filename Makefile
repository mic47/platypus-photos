ci:
	black .
	mypy .
	python3 -m unittest discover -p test_*.py
	mypy  --no-incremental .
	pylint gallery db data_model annots apps utils file_mgmt

covfefe:
	coverage run --source=. -m unittest discover -p test_*.py && coverage html
