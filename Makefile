ci:
	black .
	mypy .
	coverage run --source=. -m unittest discover -p test_*.py
	coverage report
	mypy  --no-incremental .
	pylint gallery db data_model annots apps utils file_mgmt
	vulture .

covfefe:
	coverage run --source=. -m unittest discover -p test_*.py && coverage html
