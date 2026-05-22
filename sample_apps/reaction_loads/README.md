# Reaction Loads

Generates a VIKTOR `TableView` with random reaction rows from a distributed load.

## Run

```bash
viktor-cli create-app "Reaction Loads" --registered-name reaction-loads-sample
viktor-cli clean-start
```

The view method is named `get_data_view` so it can be called by the workflow agent template with the default remote method name.
