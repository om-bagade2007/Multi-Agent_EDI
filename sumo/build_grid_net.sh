#!/usr/bin/env sh
set -eu
: "${SUMO_HOME:?Set SUMO_HOME to use netgenerate}"
netgenerate --grid --grid.number=8 --grid.length=250 --output-file=sumo/grid.net.xml
