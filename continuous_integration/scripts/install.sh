#!/bin/bash

# This accepts a pip selector as an optional argument as in:
# source install.sh pyqt5

set -vxeuo pipefail

sudo apt-get update
sudo apt-get install  -yy --no-install-recommends \
     qtbase5-dev \
     libxkbcommon-x11-0 \
     libxcb-cursor0 \
     libxcb-icccm4 \
     libxcb-image0 \
     libxcb-keysyms1 \
     libxcb-randr0 \
     libxcb-render-util0 \
     libxcb-xinerama0

# These packages are installed in the base environment but may be older
# versions. Explicitly upgrade them because they often create
# installation problems if out of date.
python -m pip install --upgrade pip setuptools wheel numpy
# Versioneer uses the most recent git tag to generate __version__, which appears
# in the published documentation.
git fetch --tags
if [[ -n $@ ]]; then
    python -m pip install .[$@]
else
    python -m pip install .
fi
python -m pip list
