"""Development tools. Never shipped to the aircraft.

Everything in this package may import heavy dependencies -- AeroSandbox,
CasADi, matplotlib -- because none of it runs in the field. The aircraft
carries ``aerosizer`` and a directory of JSON, and nothing else.

The dependency direction is one way and must stay that way:

    tools  ->  aerosizer          allowed
    aerosizer  ->  tools          never
    aerosizer  ->  aerosandbox    never

``tests/test_separation.py`` enforces the last two, because the offline
guarantee is only worth what it can be checked against.
"""
