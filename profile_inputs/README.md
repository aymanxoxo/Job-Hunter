# profile_inputs/ — user drop-zone

Drop a `*.py` file here defining **one** class that inherits
`core.profile_inputs.base_profile_input.BaseProfileInput` (normalises a profile source to text).
Set `accepts` to a tuple such as `("pdf",)`. Auto-discovered at startup. Built-in parsers live in
`core/profile_inputs/`. See SDD §3.3 / §14.3.
