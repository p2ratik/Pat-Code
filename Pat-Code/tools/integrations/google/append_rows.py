"""AppendGoogleSheetRowsTool — appends new rows to a Google Sheets spreadsheet via Sheets v4 API."""
import httpx
from pydantic import BaseModel, Field
from typing import Any

from config.config import Config
from tools.base import ToolInvocation, ToolResult
from tools.integrations.base import OAuthTool

_SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


class AppendRowsParams(BaseModel):
    spreadsheet_id: str = Field(..., description="The Google Sheets document ID (from the URL).")
    range: str = Field(..., description="A1 notation target range, e.g. 'Sheet1!A1'. Google appends after the last row of data in this range.")
    rows: list[list[Any]] = Field(..., description="List of rows to append. Each row is a list of cell values, e.g. [[\"Alice\", 30], [\"Bob\", 25]].")
    value_input: str = Field(
        "USER_ENTERED",
        description="How input is interpreted: USER_ENTERED (parses formulas/dates) or RAW.",
    )


class AppendGoogleSheetRowsTool(OAuthTool):
    name = "append_google_sheet_rows"
    description = (
        "Append one or more rows to a Google Sheets spreadsheet. "
        "Provide the spreadsheet_id, a target range like 'Sheet1!A1', and a list of rows. "
        "Each row is a list of cell values. Google Sheets inserts after the last existing row of data."
    )
    provider_name = "google"
    required_scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    schema = AppendRowsParams

    def __init__(self, config: Config):
        super().__init__(config)

    async def run(self, client: httpx.AsyncClient, invocation: ToolInvocation) -> ToolResult:
        """Calls the Sheets v4 values.append endpoint and returns the updated range."""
        params = AppendRowsParams(**invocation.params)
        url = (
            f"{_SHEETS_BASE}/{params.spreadsheet_id}/values/{params.range}:append"
        )
        body = {"values": params.rows}

        try:
            resp = await client.post(
                url,
                json=body,
                params={
                    "valueInputOption": params.value_input,
                    "insertDataOption": "INSERT_ROWS",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            return ToolResult.error_result(
                f"Google Sheets API error {exc.response.status_code}: {detail}",
                metadata={"spreadsheet_id": params.spreadsheet_id, "range": params.range},
            )
        except Exception as exc:
            return ToolResult.error_result(f"Request failed: {exc}")

        result = resp.json()
        updates = result.get("updates", {})
        updated_range = updates.get("updatedRange", params.range)
        rows_written = len(params.rows)

        return ToolResult.success_result(
            f"Successfully appended {rows_written} row(s) to '{updated_range}'.",
            metadata={
                "spreadsheet_id": params.spreadsheet_id,
                "updated_range": updated_range,
                "rows_appended": rows_written,
            },
        )
