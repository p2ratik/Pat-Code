from pydantic import BaseModel, Field
from tools.base import Tool, Toolkind, ToolResult, ToolInvocation
from utils.paths import is_binary_file, resolve_path
from utils.text import count_tokens, truncate_text

# Required parameters for the Read File operation
class ReadFileParams(BaseModel):

    path: str = Field(
        ...,
        description="Path to the file to read (relative to working directory or absolute)",
    )

    offset: int = Field(
        1,
        ge=1,
        description="Line number to start reading from (1-based). Defaults to 1",
    )

    limit: int | None = Field(
        None,
        ge=1,
        description="Maximum number of lines to read. If not specified, reads entire file.",
    )

class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the contents of a text file. Returns the file content with line numbers. "
        "For large files, use offset and limit to read specific portions. "
        "Cannot read binary files (images, executables, etc.)."
    )
    kind = Toolkind.READ
    schema = ReadFileParams #property not a function

    MAX_FILE_SIZE = 1024*1024*10 # 10 MB default
    MAX_OUTPUT_TOKENS = 25000

    async def execute(self, invocation:ToolInvocation):
        params = ReadFileParams(**invocation.params)
        path = resolve_path(base=invocation.cwd, path=params.path)

        if not path.exists():
            return ToolResult.error_result(f"File not found: {path}")

        if not path.is_file():
            return ToolResult.error_result(f"Path is not a file: {path}")       

        file_size = path.stat().st_size # File size in bytes

        if file_size > self.MAX_FILE_SIZE:
            return ToolResult.error_result(
                f"File too large ({file_size / (1024*1024):.1f}MB). "
                f"Maximum is {self.MAX_FILE_SIZE / (1024*1024):.0f}MB."
            )

        if is_binary_file(path=path):
            file_size_mb = file_size / (1024 * 1024)
            size_str = (
                f"{file_size_mb:.2f}MB" if file_size_mb >= 1 else f"{file_size} bytes"
            )
            return ToolResult.error_result(
                f"Cannot read binary file: {path.name} ({size_str}) "
                f"This tool only reads text files."
            )
        
        # Central try block
        try:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="latin-1")                   

            lines = content.splitlines() # List of lines [.....]
            total_lines = len(lines)

            if total_lines == 0: # Empty file
                return ToolResult.success_result(output="file is empty", metadata={"line": 0})
            
            start_idx = max(0, params.offset - 1) # 0 based and 1 based indexing 

            if params.limit is not None:
                end_idx = min(start_idx + params.limit, total_lines)
            else:
                end_idx = total_lines

            selected_lines = lines[start_idx:end_idx]

            formatted_lines = []
            # f"{i:6}|{line}" → formatted string

            # This is string formatting with width specification.

            # {i:6} means:
            # print i in a field of width 6 characters
            # right-aligned by default 

            for i, line in enumerate(selected_lines, start=start_idx + 1):
                formatted_lines.append(f"{i:6}|{line}")

            output = "\n".join(formatted_lines)
            token_count = count_tokens(text =output, model='nvidia/nemotron-3-super-120b-a12b:free')
            truncated = False

            if token_count > self.MAX_OUTPUT_TOKENS:
                output = truncate_text(
                          output,
                          self.config.model_name,
                          self.MAX_OUTPUT_TOKENS,
                          suffix=f"\n... [truncated {total_lines} total lines]",
                )
                truncated = True

            metadata_lines = []
            if metadata_lines:
                header = " | ".join(metadata_lines) + "\n\n"
                output = header + output

            return ToolResult.success_result(
                output=output,
                truncated=truncated,
                metadata={
                    "path": str(path),
                    "total_lines": total_lines,
                    "shown_start": start_idx + 1,
                    "shown_end": end_idx,
                },
            )
        except Exception as e:
            return ToolResult.error_result(f"Failed to read file: {e}")