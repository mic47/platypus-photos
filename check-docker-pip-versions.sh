#!/bin/bash

if [[ -z "$(comm -2 -3 <(cat docker/service.dockerfile | grep '\b[-a-z_0-9A-Z]*==\b[0-9.]*\b' -o | sort) <(cat requirements.txt | sort) )" ]] ; then
  echo "docker/service.dockerfile and requirements.txt versions are consistent"
else
  echo "docker/service.dockerfile and requirements.txt versions are not consistent!"
  exit 1;
fi
