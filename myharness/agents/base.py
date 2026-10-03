from pathlib import Path

from myharness.tools.base import BaseTool
from dataclasses import dataclass, field

@dataclass
class SkillDefinition:
    name: str
    description: str
    path: Path

@dataclass
class AgentDefinition:
    name: str
    model: str
    provider: str
    temperature: float = 0.7
    max_tokens: int = 4096
    enable_thinking: bool = False
    instructions: str = ""
    skills: list[SkillDefinition] = field(default_factory=list)
    tools: list[BaseTool] = field(default_factory=list)
    raw_config: dict = None

