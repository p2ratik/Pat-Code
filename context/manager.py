from dataclasses import dataclass
from utils.text import count_token
from typing import Any

@dataclass
class MessageItem:
    role : str
    content: str
    token_count : int | None = None

    def to_dict(self)->dict[str, Any]:

        result : dict[str, Any] = {'role':self.role}

        if self.content:
            result['content'] = self.content
            # result['token'] = self.token_count

        return result    


class ContextManager:
    def __init__(self)->None:
        self._messages: list[MessageItem] = []
        self._model_name = 'nvidia/nemotron-3-super-120b-a12b:free'
        self._system_prompt = "youre a helpful Muslim Assistant from Iran"
        pass

    def add_user_message(self, content:str)->None:
        item = MessageItem(
            role = 'user',
            content = content,
            token_count = count_token(model=self._model_name, text=content)
        )

        self._messages.append(item)

    def add_assistant_message(self, content:str)->None:
        item = MessageItem(
            role = 'assistant',
            content = content,
            token_count = count_token(model=self._model_name, text=content)
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
        
