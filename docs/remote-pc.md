# Remote PC control via paired connection (PLANNED — not built yet)

Captured design so we can build it later. Nothing here is implemented.

## Vision

The robot is **standalone** — it runs entirely on its own (voice, vision, memory,
body) and needs no PC. The PC is an **optional peer** the robot pairs with on
demand, like pairing a phone to a speaker:

> User: "Kel, connect to my PC." → a connection **code** appears on the PC → Kel
> asks for it / the user reads it → paired → Kel can now drive the PC (browser,
> shell, typing) over WiFi. "Kel, disconnect" ends it.

While unpaired, the PC-control tools are dormant (there is no PC to control).

## Topology

```
ROBOT (standalone, battery, WiFi):  Kel brain + voice + vision + memory + body
        │   "Kel, connect to my PC"
        ▼
   ──WiFi──►  PC runs "kel-agent" (small background app)
                 - advertises itself on the LAN (mDNS)
                 - shows a pairing CODE on screen
                 - after pairing, executes commands from the robot
```

## Pairing flow (the connection code)

1. User: "Kel, connect to my PC."
2. Robot discovers the PC agent on the LAN (mDNS), or uses a configured address.
3. The agent shows a short code on the PC screen (e.g. `482-913`).
4. Kel asks the user to read the code, sends it to the agent to authenticate.
5. Code matches → agent issues a token → **paired**. PC tools now route to the PC.
6. Optional: the agent stores the robot's token so future connects skip the code.

The code is the security gate: it stops any device on the network from seizing the
PC. This matters because PC control includes the unrestricted shell.

## Components to build

1. **`kel-agent`** — a small app installed on the PC. A WebSocket server that:
   - advertises via mDNS, shows the pairing code, verifies it, issues a token;
   - on an authenticated message, calls the **existing** system tools and returns
     the result.
   - **Reuses what already exists**: `kel.system.shell.ShellRunner`,
     `kel.system.browser.Browser`, `kel.system.keyboard.Keyboard`,
     `kel.system.launcher.TerminalLauncher`. The agent is mostly transport + auth.
2. **Robot-side `RemoteComputer` client** — connects to a paired agent, runs the
   pairing handshake (asks the user for the code), forwards tool calls, reads
   results.
3. **Tool routing switch** — the realtime tools (`run_command`, `open_url`,
   `type_text`, `run_in_terminal`, `press_key`) gain a target: run **locally** if
   Kel is on the machine, or send to the **paired PC** if connected. Plus
   `connect_to_pc` / `disconnect_from_pc` tools to drive the pairing by voice.

## Security model

- **Pairing code** to authorize a new device; **token** saved after so re-pair is
  optional.
- The **same dangerous-command tripwire** (`is_dangerous`) runs on the PC agent.
- Channel should be encrypted (**WSS/TLS**) since it carries shell commands. On a
  trusted home LAN, code + token over plain WS is an acceptable v1; TLS is the
  hardening step.
- Agent only accepts connections from paired tokens; unpaired devices only get the
  "enter the code" challenge.

## Transport & discovery

- **Transport:** WebSocket (persistent, bidirectional — commands down, results up).
- **Discovery:** mDNS/zeroconf (agent advertises `_kel-agent._tcp`), or a configured
  PC hostname/IP. Robot and PC must be on the same LAN.

## Notes / alternatives

- **Shell-only shortcut:** plain SSH already lets the robot run commands on the PC,
  but it doesn't cover browser/typing or the voice "say the code" pairing UX — so
  the small agent is the right call for the full vision.
- The PC-control tools we already built were deliberately isolated, so they drop
  straight into the agent with no rewrite.

## Build order (when we do it)

1. Finish the standalone robot (voice/vision/memory done; body later).
2. Build `kel-agent` + the pairing/code handshake on the PC.
3. Add the robot-side client + flip the PC tools to "route to the paired PC."
