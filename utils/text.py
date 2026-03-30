import tiktoken

def get_tokenizer(model:str):
    try:
        # tokenizing for the specific model
        encoding = tiktoken.get_encoding(model)
        return encoding.encode
    except:
        encoding = tiktoken.get_encoding('cl100k_base') # Gpt 4 fallback
        return encoding.encode 

def estimate_tokens(text:str):
    return max(1, len(text) // 4) 
   
def count_token(text: str, model:str):
    tokenizer = get_tokenizer(model=model)

    if tokenizer and text:
        return len(tokenizer(text))    
    
    return estimate_tokens(text=text)

def truncate_text(
    text: str,
    model: str,
    max_tokens: int,
    suffix: str = "\n... [truncated]",
    preserve_lines: bool = True,
):
    current_tokens = count_token(text, model)
    if current_tokens <= max_tokens:
        return text

    suffix_tokens = count_token(suffix, model)
    target_tokens = max_tokens - suffix_tokens

    if target_tokens <= 0:
        return suffix.strip()

    if preserve_lines:
        return _truncate_by_lines(text, target_tokens, suffix, model)
    else:
        return _truncate_by_chars(text, target_tokens, suffix, model)


def _truncate_by_lines(text: str, target_tokens: int, suffix: str, model: str) -> str:
    lines = text.split("\n")
    result_lines: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_token(line + "\n", model)
        if current_tokens + line_tokens > target_tokens:
            break
        result_lines.append(line)
        current_tokens += line_tokens

    if not result_lines:
        # Fall back to character truncation if no complete lines fit
        return _truncate_by_chars(text, target_tokens, suffix, model)

    return "\n".join(result_lines) + suffix


def _truncate_by_chars(text: str, target_tokens: int, suffix: str, model: str) -> str:
    # Binary search for the right length
    low, high = 0, len(text)

    while low < high:
        mid = (low + high + 1) // 2
        if count_token(text[:mid], model) <= target_tokens:
            low = mid
        else:
            high = mid - 1

    return text[:low] + suffix
