#!/bin/bash

set -x
set -e

git pull
yarn
python3 -m pphoto.apps.generator
yarn prod-build
fastapi run pphoto/apps/gallery.py --workers 3
