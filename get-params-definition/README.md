# VIKTOR Entity Parameter Fetcher

Fetch entity parameter values and type information from VIKTOR via REST API.

## Setup

1. **Add your VIKTOR Personal Access Token to `.env`:**

   ```bash
   VK_TOKEN=your_actual_token_here
   ```

   Get your token from: https://demo.viktor.ai/account/tokens

2. **Install dependencies** (already done):

   ```bash
   uv sync
   ```

## Usage

Run the script to fetch entity parameters:

```bash
uv run fetch_entity_params.py
```

This will:
- Fetch entity data for workspace 2494, entity 11967 (configurable in `.env`)
- Display entity metadata (name, type, path)
- Show the editor URL
- Save full response to `entity_11967_params.json`
- Print parameter structure to console

## Configuration

Edit `.env` to change:
- `VK_TOKEN`: Your Personal Access Token (required)
- `VIKTOR_ENVIRONMENT`: VIKTOR environment (default: `demo`)
- `WORKSPACE_ID`: Target workspace ID (default: `2494`)
- `ENTITY_ID`: Target entity ID (default: `11967`)

## What you'll get

The API returns:
- **Entity metadata**: ID, name, type, parent count, path
- **Parameter values**: `properties` field contains current parameter values
- **Type information**: Parameter field types (when `param_types=true`)

⚠️ **Note**: The REST API returns parameter **values**, not the full parametrization **structure** (field definitions, validators, sections, etc.). The structure lives in the app's Python `Parametrization` class.

## Output

The script saves a JSON file with the complete entity response:

```json
{
  "id": 11967,
  "name": "Example Entity",
  "entity_type": 123,
  "entity_type_name": "Foundation",
  "properties": {
    "input": {
      "field_name": "value"
    }
  },
  "parent_count": 1,
  "path": [2494, 11967]
}
```
