This is actually a more important design decision than it first appears. OutputProcessingHook effectively decides what the LLM remembers about the world. If it's too aggressive, the agent loses context and starts making poor decisions. If it's too permissive, your context window fills with noise.

Given everything you've built so far, I'd avoid thinking of it as an "output pruning" hook. Instead, I'd think of it as an Output Normalization & Summarization Hook.

The philosophy

Every tool produces three audiences:

The tool itself (raw output for debugging)
The runtime (verification, retries, metrics)
The LLM (only the information needed for the next reasoning step)

Your OutputProcessingHook should only care about audience #3.

So the pipeline becomes:

Tool
    ↓
ToolResult (raw)
    ↓
Verification
    ↓
Retry
    ↓
OutputProcessingHook
    ↓
LLM

Notice that the raw output is never lost—it just isn't always sent verbatim.

Principle 1: Never destroy information

I wouldn't mutate ToolResult.output.

Instead, create another field on ExecutionResult.

For example:

ExecutionResult
├── tool_result
├── repair_instruction
├── processed_output

where

processed_output

is exactly what the LLM receives.

That way you always have

Raw output
Processed output

for debugging.

Principle 2: Process by tool type

Don't apply one global rule.

A shell tool behaves very differently from a web search tool.

Example:

read_file

Raw

2000 lines

LLM

First 150 lines...

...

Last 100 lines...

(1750 lines omitted)
list_directory

Raw

350 files

LLM

Directory contains 350 files.

First 40:

...
grep

Raw

1200 matches

LLM

Found 1200 matches.

Top 30 relevant:

...
HTTP request

Raw

1 MB JSON

LLM

Status: 200

Returned 1542 objects.

Example:

...

Each tool deserves its own processor.

Principle 3: Compress, don't prune

This is the biggest mistake many agent frameworks make.

Bad:

Output truncated.

Now the LLM knows nothing.

Better:

Output too large.

Summary:

- 742 Python files
- 28 Markdown files
- 14 Images

Largest directories:

...

The model still has a mental picture.

Principle 4: Preserve important signals

Don't accidentally remove things like

stack traces
compiler errors
warnings
exit codes
filenames
URLs
line numbers

For example

Compilation failed.

main.cpp:42

error:

missing ';'

Those few lines are extremely valuable.

Principle 5: Semantic compression > character limits

Avoid

output[:5000]

Prefer

Directory listing:

...

200 additional files omitted.

or

JSON response:

Keys:

users
orders
products

First object:

...

This preserves structure.

Principle 6: Only summarize when necessary

Something like

if len(output) < 2000:
    return output

Otherwise

compress()

Most tool outputs are already small.

Principle 7: Keep deterministic

I would avoid using another LLM here (at least initially).

Instead use deterministic processors.

Example

Shell output

↓

keep first 50 lines

keep last 30

insert omission notice

Very predictable.

Later, if you want semantic summaries for huge outputs, you can optionally plug in an LLM.

Principle 8: Make processors composable

Instead of one huge function

process()

I'd lean toward a small pipeline:

OutputProcessingHook

↓

Normalizer

↓

SizePolicy

↓

ToolSpecificProcessor

↓

Formatter

Example:

Raw Output

↓

Normalize newlines

↓

Remove ANSI colors

↓

Limit length

↓

Directory formatter

↓

LLM

Each stage has one responsibility.

Principle 9: Expose metadata

I love when the LLM sees

Output Summary

Original Size:
82,314 characters

Sent:
4,521 characters

Reason:
Exceeded context limit

Now the agent knows there was more information and can decide to request another chunk if needed.

Principle 10: Give the model an escape hatch

Suppose

read_file huge_log.txt

gets compressed.

Tell the model

Output truncated.

You may call read_file again with

offset=...

or

start_line=...

if more detail is required.

Now the agent can explore instead of hallucinating.

What I'd implement for PAT

I'd organize it around processors rather than pruning rules:

OutputProcessingHook
│
├── ShellProcessor
├── FileProcessor
├── DirectoryProcessor
├── SearchProcessor
├── HTTPProcessor
├── JSONProcessor
└── DefaultProcessor

Each processor returns something like:

ProcessedOutput(
    content="...",
    original_size=82431,
    processed_size=3128,
    was_compressed=True,
    strategy="head_tail"
)