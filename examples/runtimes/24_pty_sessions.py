#!/usr/bin/env python3
"""Interactive PTY sessions: create, attach, type, resize, signal, re-attach, exit.

A PTY session is a real terminal inside the runtime. It is owned by the execution
plane rather than by the client that opened it, so the shell keeps running after you
disconnect and you can attach to the same session again later — from another process
or another machine.

`sandbox.pty.handle(session_id)` wraps the stateless calls in a connection-managing
object: it owns one output stream, buffers what it receives, and exposes
`wait_for_connection` / `wait_for_completion`.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/24_pty_sessions.py

Optional: ``GRAVIXLAYER_TEMPLATE`` (default ``base-small``).
"""

import os
import time

from gravixlayer import GravixLayer

client = GravixLayer()
TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

sandbox = client.runtime.create(template=TEMPLATE)
print(f"Runtime    : {sandbox.runtime_id}\n")


def show(chunk: bytes) -> None:
    print(chunk.decode("utf-8", "replace"), end="", flush=True)


# ---------------------------------------------------------------------------
# 1. Create a session
# ---------------------------------------------------------------------------
session = sandbox.pty.create(
    shell="/bin/bash",
    working_dir="/workspace",
    environment={"DEMO": "pty"},
    cols=100,
    rows=30,
)
print(f"Session    : {session.session_id}")
print(f"  pid      : {session.pid}")
print(f"  shell    : {session.shell} in {session.working_dir}")
print(f"  size     : {session.cols}x{session.rows}")
print(f"  status   : {session.status}")

# ---------------------------------------------------------------------------
# 2. Attach a handle and stream the terminal live
# ---------------------------------------------------------------------------
pty = sandbox.pty.handle(session.session_id)
pty.connect(on_data=show, on_exit=lambda code, err: print(f"\n[session exited {code}]"))

if not pty.wait_for_connection(timeout=30):
    raise SystemExit(f"could not attach to the session: {pty.error}")
print("\n--- attached ---")

# ---------------------------------------------------------------------------
# 3. Type into the terminal
# ---------------------------------------------------------------------------
pty.send_input("echo hello from $DEMO\n")
pty.send_input("pwd\n")
time.sleep(2)

# ---------------------------------------------------------------------------
# 4. Resize the terminal (the guest process receives SIGWINCH)
# ---------------------------------------------------------------------------
pty.resize(cols=120, rows=40)
pty.send_input("stty size\n")
time.sleep(2)

# ---------------------------------------------------------------------------
# 5. Interrupt a running foreground command
# ---------------------------------------------------------------------------
# Sending the interrupt character is exactly what pressing Ctrl-C does: the
# terminal turns it into a signal for the job in the foreground, so the shell
# that started it survives.
pty.send_input("sleep 60\n")
time.sleep(1)
pty.send_input("\x03")
time.sleep(2)
print("\n--- interrupted, shell is still alive ---")

# ---------------------------------------------------------------------------
# 6. List the sandbox's sessions
# ---------------------------------------------------------------------------
sessions = sandbox.pty.list()
print(f"\nSessions   : {len(sessions)}")
for s in sessions:
    print(f"  {s.session_id}  pid={s.pid}  {s.status}")

# ---------------------------------------------------------------------------
# 7. Detach — the session outlives the connection
# ---------------------------------------------------------------------------
buffered = pty.output
pty.disconnect()
print(f"\nDetached   : connected={pty.is_connected}, buffered {len(buffered)} bytes")

still_there = sandbox.pty.get(session.session_id)
print(f"Session    : still {still_there.status} after detaching")

# ---------------------------------------------------------------------------
# 8. Re-attach to the same session and let the shell exit
# ---------------------------------------------------------------------------
# Attaching replays the session's retained scrollback first, so everything typed
# above is reprinted before the new output.
with sandbox.pty.handle(session.session_id) as pty2:
    pty2.connect(on_data=show)
    pty2.wait_for_connection(timeout=30)
    print("\n--- re-attached ---")

    pty2.send_input("echo back in the same shell\n")
    time.sleep(1)

    pty2.send_input("exit 7\n")
    final = pty2.wait_for_completion(timeout=60)
    print(f"\nFinished   : status={final.status} exit_code={final.exit_code}")

# ---------------------------------------------------------------------------
# 9. Signals can also be sent out of band, without attaching
# ---------------------------------------------------------------------------
# Signal names are given without the SIG prefix. HUP is the one a terminal sends
# when it goes away, and a shell exits on it.
scratch = sandbox.pty.create(shell="/bin/bash")
sandbox.pty.send_signal(scratch.session_id, "HUP")
time.sleep(1)
print(f"\nScratch    : {scratch.session_id} -> {sandbox.pty.get(scratch.session_id).status}")

# Killing a session ends it if it is still running, and releases it either way.
print(f"Released   : {sandbox.pty.kill(scratch.session_id)}")

# ---------------------------------------------------------------------------
# Clean up — always kill the sandbox when you are done
# ---------------------------------------------------------------------------
sandbox.kill()
print("\nRuntime terminated.")
