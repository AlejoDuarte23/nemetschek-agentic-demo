# Footing

Sizes a rectangular pad footing from axial loads and biaxial moments.

The app assumes:

- allowable bearing pressure: `150 kPa`
- concrete unit weight: `24 kN/m3`
- middle-kern check: `6 * (ex / B + ey / L) <= 1`

## Run

```bash
viktor-cli create-app "Footing" --registered-name footing-sample
viktor-cli clean-start
```

The result is exposed through a VIKTOR `DataView` named `get_data_view`.
