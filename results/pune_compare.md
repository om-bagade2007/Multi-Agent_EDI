# Dispatch comparison (1 paired scenarios)

Seeds: [1]

| strategy   |   ('avg_response_s', 'mean') |   ('avg_response_s', 'median') |   ('avg_response_s', 'std') |   ('ambulance_util', 'mean') |   ('ambulance_util', 'median') |   ('ambulance_util', 'std') |   ('fire_util', 'mean') |   ('fire_util', 'median') |   ('fire_util', 'std') |   ('police_util', 'mean') |   ('police_util', 'median') |   ('police_util', 'std') |   ('mean_traffic_delay_s', 'mean') |   ('mean_traffic_delay_s', 'median') |   ('mean_traffic_delay_s', 'std') |
|:-----------|-----------------------------:|-------------------------------:|----------------------------:|-----------------------------:|-------------------------------:|----------------------------:|------------------------:|--------------------------:|-----------------------:|--------------------------:|----------------------------:|-------------------------:|-----------------------------------:|-------------------------------------:|----------------------------------:|
| hungarian  |                      426.052 |                        426.052 |                           0 |                        0.965 |                          0.965 |                           0 |                   0.921 |                     0.921 |                      0 |                     0.963 |                       0.963 |                        0 |                              0.433 |                                0.433 |                                 0 |
| nearest    |                      507.335 |                        507.335 |                           0 |                        0.965 |                          0.965 |                           0 |                   0.921 |                     0.921 |                      0 |                     0.963 |                       0.963 |                        0 |                              0.433 |                                0.433 |                                 0 |

Hungarian mean response-time improvement over nearest: 16.02%.

CSV: `../results/pune_compare.csv`
