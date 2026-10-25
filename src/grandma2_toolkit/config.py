"""Environment-only credentials and explicit write policy; no embedded passwords."""

from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass(frozen=True)
class Config:
    host: str = "127.0.0.1"
    ports: tuple[int, ...] = (30000, 30001)
    user: str = "administrator"
    password: str = field(default="", repr=False)
    timeout: float = 15.0
    allow_write: bool = False
    output_dir: Path = field(default_factory=lambda: Path.cwd() / ".data")

    @classmethod
    def from_env(cls) -> "Config":
        """Resolve paths at startup so MCP hosts need not share the repository cwd."""
        root = Path(__file__).resolve().parents[2]
        return cls(
            host=os.getenv("MA2_HOST", "127.0.0.1"),
            ports=tuple(int(p.strip()) for p in os.getenv("MA2_PORTS", os.getenv("MA2_PORT", "30000,30001")).split(",")),
            user=os.getenv("MA2_USER", "administrator"),
            password=os.getenv("MA2_PASSWORD", ""),
            timeout=float(os.getenv("MA2_TIMEOUT", "15")),
            allow_write=os.getenv("MA2_ALLOW_WRITE", "0") == "1",
            output_dir=Path(os.getenv("MA2_OUTPUT_DIR", str(root / ".data"))).resolve(),
        )

    def validate(self) -> None:
        """Reject credentials that could escape the console Login command."""
        if not self.password:
            raise ValueError("Set MA2_PASSWORD in the server/CLI process environment")
        for value in (self.user, self.password):
            if not value or any(c in value for c in '\"\r\n;\\') or any(ord(c) < 32 for c in value):
                raise ValueError("Credentials contain unsupported console characters")
        if not self.ports or any(not 1 <= p <= 65535 for p in self.ports):
            raise ValueError("Invalid MA2_PORTS")
        if not 1 <= self.timeout <= 120:
            raise ValueError("MA2_TIMEOUT must be between 1 and 120 seconds")
