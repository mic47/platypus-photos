cipy:
	black .
	mypy .
	coverage run --source=. -m unittest discover -p test_*.py
	coverage report
	mypy  --no-incremental .
	pylint pphoto
	vulture .

cits:
	yarn prettier
	yarn typecheck
	yarn lint

gen:
	python3 -m pphoto.apps.generator
	yarn gen-code

ci:
	make cipy
	yarn
	make gen
	make cits

covfefe:
	coverage run --source=. -m unittest discover -p test_*.py && coverage html
