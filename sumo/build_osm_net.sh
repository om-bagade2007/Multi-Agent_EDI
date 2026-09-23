#!/usr/bin/env sh
set -eu
: "${SUMO_HOME:?Set SUMO_HOME to use netconvert}"
netconvert --osm-files "${OSM_FILE:-sumo/city.osm.xml}" --output-file=sumo/osm.net.xml
