"""A line-delimited JSON pipe to the Swift accessibility bridge.

Taken from open-computer-use (MIT), see NOTICE.md. Only the paths differ: the
bridge is vendored here rather than being the project's own package.
"""

import json
import os
import selectors
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build.sh"




def binary():
    """Build the bridge if needed and return its path."""
    override = os.environ.get("AXBRIDGE_BIN")
    if override:
        return override
    result = subprocess.run(["bash", str(BUILD)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"could not build the accessibility bridge:\n{result.stderr.strip()}")
    return result.stdout.strip()


class StaleWindow(Exception):
    """The window changed between the decision and its execution."""


class BridgeError(RuntimeError):
    """The bridge refused an operation. Nothing was executed."""


class UnknownOutcome(RuntimeError):
    """The request was sent and the window may already have changed.

    These must not be retried. The operation may have run: a press that reached
    the app and then lost its reply looks exactly like a press that never
    arrived. Observe the window and decide from what is there, rather than
    sending it again.
    """


class Executed(UnknownOutcome):
    """The operation ran, changed the window, and could not be confirmed.

    Not a variety of "nothing happened". `TYPE_TEXT` empties the field before
    writing to it, so a read-back that does not match is a failure reported
    about a field this call has already emptied. Treating that as a refusal
    left the step out of the agent's history entirely and offered the model a
    fresh choice over a field it had itself cleared, with no record that
    anything had been done to it. A subclass, so every caller that already
    knows not to retry an uncertain outcome covers this one too.
    """




class Bridge:
    """A line-delimited JSON-RPC pipe to the Swift helper."""

    def __init__(self):
        self.process = subprocess.Popen(
            [binary(), "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.lock = threading.Lock()
        self.counter = 0
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)

    def _readline(self, timeout):
        """One line, or None if it did not arrive in time."""
        if self.selector.select(timeout):
            return self.process.stdout.readline()
        return None

    def call(self, method, timeout=20, mutating=False, **body):
        with self.lock:
            if self.process.poll() is not None:
                raise BridgeError("the accessibility bridge exited before the request was sent")
            self.counter += 1
            request = {"id": self.counter, "method": method, **body}
            try:
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()
            except (OSError, ValueError) as error:
                # Never left this process, so nothing can have happened.
                raise BridgeError(f"the request was not sent: {error}") from None
            # Past this line the operation may have run, whatever comes back.
            line = self._readline(timeout)

        if line is None or line == "":
            lost = "timed out" if line is None else "the bridge closed the pipe"
            if mutating:
                raise UnknownOutcome(
                    f"{method} was sent and {lost} after {timeout}s. It may have run. "
                    "Observe the window rather than sending it again."
                )
            raise BridgeError(f"{method} {lost} after {timeout}s")
        answer = json.loads(line)
        if answer.get("id") != request["id"]:
            # The pipe is one request at a time; a mismatch means it desynced.
            raise UnknownOutcome(
                f"expected a reply to {request['id']} and got {answer.get('id')}; the bridge is out of step"
            )
        if not answer.get("ok"):
            message = answer.get("error", "unknown bridge error")
            # Most bridge failures are pre-flight — a path that no longer
            # resolves, a disabled element, a guard that refused — and nothing
            # ran. The bridge says when that is not true, and it is not true
            # for the one operation that clears a field before filling it.
            if answer.get("acted"):
                raise Executed(message)
            raise BridgeError(message)
        return answer["result"]

    def close(self):
        try:
            self.selector.close()
        except Exception:
            pass
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()


# How long to let the interface settle before the next observation. A menu or a
# sheet animates in; paying for a decision before it exists wastes a round trip.
# TYPE_TEXT needs almost nothing, because setting the accessibility value is
# synchronous and `act` has already read the value back before returning.
