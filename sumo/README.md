# Optional SUMO

SUMO is an optional best-effort adapter. Set `SUMO_HOME` and install TraCI before setting `SIM_BACKEND=sumo`. The grid network helper uses `netgenerate`; the OSM helper converts a locally supplied OSM extract to avoid network access during normal runs. GridSim remains the tested default.
