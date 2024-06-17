ci:
	black .
	mypy .
	coverage run --source=. -m unittest discover -p test_*.py
	coverage report
	mypy  --no-incremental .
	pylint pphoto
	vulture .

covfefe:
	coverage run --source=. -m unittest discover -p test_*.py && coverage html
