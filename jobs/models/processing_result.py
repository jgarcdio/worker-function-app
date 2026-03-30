from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class JobProcessingResult:
    job_name: str
    status: str
    paragraphs: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
