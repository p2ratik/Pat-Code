from dataclasses import dataclass, field
from utils.text import count_tokens
from typing import Any

@dataclass
class MessageItem:
    role : str
    content: str
    token_count : int | None = None
    tool_call_id : str | None = None
    tool_calls : list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self)->dict[str, Any]:

        result : dict[str, Any] = {'role':self.role}

        if self.tool_call_id:
            result['tool_call_id'] = self.tool_call_id

        if self.tool_calls:
            result['tool_calls'] = self.tool_calls    
        if self.content:
            result['content'] = self.content
            # result['token'] = self.token_count

        return result    


class ContextManager:
    def __init__(self)->None:
        self._messages: list[MessageItem] = []
        self._model_name = 'nvidia/nemotron-3-super-120b-a12b:free'
        self._system_prompt = "youre a helpful AI agent that can use tools . When calling a tool , you must provide valid JSON arguments matching the schema."
        pass

    def add_user_message(self, content:str)->None:
        item = MessageItem(
            role = 'user',
            content = content,
            token_count = count_tokens(model=self._model_name, text=content)
        )

        self._messages.append(item)

    def add_assistant_message(self, content:str)->None:
        item = MessageItem(
            role = 'assistant',
            content = content,
            token_count = count_tokens(model=self._model_name, text=content)
        )

        self._messages.append(item)

    def add_tool_result(self, tool_call_id, content)->None:
        item = MessageItem(
            role = 'tool',
            content=content,
            tool_call_id=tool_call_id,
            token_count = count_tokens(content, self._model_name)
        )
        self._messages.append(item)

    def get_messages(self):
        messages = []

        if self._system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": self._system_prompt,
                }
            )

        for messsage in self._messages:
            messages.append(messsage.to_dict())

        return messages
        
