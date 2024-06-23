#!/bin/bash

set -x

git pull
yarn
yarn prod-build
fastapi run pphoto/apps/gallery.py --workers 3
