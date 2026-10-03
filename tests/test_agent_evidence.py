import json
import tempfile
import unittest
from pathlib import Path
from typing import Optional

from support import Transcript, at
from evidence import Messaged, Pgrep, Spawned, load_ledger


def spawn(t: Transcript, when: str, msg: str, prompt: str = "do the thing", agent_id: str = "a0000000000000001",
          tool_id: Optional[str] = None, result: bool = True) -> None:
    t.tool("Agent", {"subagent_type": "general-purpose", "description": "d", "prompt": prompt}, when,
           f"Async agent launched successfully.\nagentId: {agent_id} (internal ID)" if result else None, tool_id=tool_id)
    t.records[-2 if result else -1]["message"]["id"] = msg


def send(t: Transcript, to: str, when: str, resumed: Optional[str] = None) -> None:
    reply = {"success": True, "message": f"Message queued for delivery to {to}.", "pin": {"id": resumed or to, "name": to}}
    if resumed:
        reply["resumedAgentId"] = resumed
    t.tool("SendMessage", {"to": to, "message": "keep going"}, when, json.dumps(reply))


class AgentLedger(unittest.TestCase):
    def test_spawns_carry_the_agent_id_and_messages_carry_the_recipient(self):
        t = Transcript()
        spawn(t, at(1), "msg_1", agent_id="a1234567890abcdef")
        send(t, "a1234567890abcdef", at(2))
        send(t, "worker", at(3), resumed="a1234567890abcdef")
        t.bash("pgrep -fl /w/tree", at(4))
        with tempfile.TemporaryDirectory() as tmp:
            led = load_ledger(t.write(Path(tmp) / "s.jsonl"), drop_sidechain=True, cut_at_tool_use=None)
        (s,) = led.of(Spawned)
        self.assertEqual((s.agent_id, s.stamp.msg_id), ("a1234567890abcdef", "msg_1"))
        self.assertEqual([(m.to, m.resumed) for m in led.of(Messaged)],
                         [("a1234567890abcdef", "a1234567890abcdef"), ("worker", "a1234567890abcdef")])
        self.assertEqual([p.args for p in led.of(Pgrep)], [("-fl", "/w/tree")])


if __name__ == "__main__":
    unittest.main()
