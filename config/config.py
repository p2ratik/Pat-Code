from pydantic import BaseModel, Field
from pathlib import Path
import os

class ModelConfig(BaseModel):
    # All The model related stuffs
    name: str = "nvidia/nemotron-3-super-120b-a12b:free"
    temperature: float = Field(default=1, ge=0.0, le=2.0)
    context_window: int = 256_000   

class Config(BaseModel):
    model : ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)
    max_turns : int = 100

    @property
    def api_key(self) -> str | None:
        return os.environ.get("API_KEY") 
    
    @property
    def base_url(self) -> str | None:
        return os.environ.get("BASE_URL")

    @property
    def model_name(self) -> str:
        return self.model.name

    @property
    def temperature(self) -> float:
        return self.model.temperature

    # Note that the function name of property and setter function must be same 

    @temperature.setter  # Using setters to chanwge the parametes of the private function
    def temperature(self, value: str) -> None:
        self.model.temperature = value        

    @model_name.setter
    def model_name(self, value: str) -> None:
        self.model.name = value

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.api_key:
            errors.append("No API key found. Set API_KEY environment variable")

        if not self.cwd.exists():
            errors.append(f"Working directory does not exist: {self.cwd}")

        return errors