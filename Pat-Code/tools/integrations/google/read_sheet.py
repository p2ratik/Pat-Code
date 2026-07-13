"""ReadGoogleSheetTool — reads cell values from a Google Sheets range via the Sheets v4 API."""
import json
import httpx
from pydantic import BaseModel, Field

from config.config import Config
from tools.base import ToolInvocation, ToolResult
from tools.integrations.base import OAuthTool

_SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


class ReadSheetParams(BaseModel):
    spreadsheet_id: str = Field(..., description="The Google Sheets document ID (from the URL).")
    range: str = Field(..., description="A1 notation range, e.g. 'Sheet1!A1:C10'.")
    value_render: str = Field(
        "FORMATTED_VALUE",
        description="How values are rendered: FORMATTED_VALUE, UNFORMATTED_VALUE, or FORMULA.",
    )


class ReadGoogleSheetTool(OAuthTool):
    name = "read_google_sheet"
    description = (
        "Read cell values from a Google Sheets spreadsheet. "
        "Provide the spreadsheet_id (from the URL) and an A1-notation range like 'Sheet1!A1:C10'."
    )
    provider_name = "google"
    required_scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    schema = ReadSheetParams

    def __init__(self, config: Config):
        super().__init__(config)

    async def run(self, client: httpx.AsyncClient, invocation: ToolInvocation) -> ToolResult:
        """Calls the Sheets v4 values.get endpoint and formats the response as a table."""
        params = ReadSheetParams(**invocation.params)
        url = f"{_SHEETS_BASE}/{params.spreadsheet_id}/values/{params.range}"

        try:
            resp = await client.get(url, params={"valueRenderOption": params.value_render})
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            return ToolResult.error_result(
                f"Google Sheets API error {exc.response.status_code}: {detail}",
                metadata={"spreadsheet_id": params.spreadsheet_id, "range": params.range},
            )
        except Exception as exc:
            return ToolResult.error_result(f"Request failed: {exc}")

        data = resp.json()
        rows: list[list] = data.get("values", [])

        if not rows:
            return ToolResult.success_result(
                f"No data found in range '{params.range}'.",
                metadata={"rows": 0, "spreadsheet_id": params.spreadsheet_id},
            )

        lines = [f"Range: {data.get('range', params.range)} ({len(rows)} rows)\n"]
        for row in rows:
            lines.append("\t".join(str(cell) for cell in row))

        return ToolResult.success_result(
            "\n".join(lines),
            metadata={"rows": len(rows), "spreadsheet_id": params.spreadsheet_id},
        )
