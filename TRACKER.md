# TRACKER

Running log of what exists in this repo, what was done, and what's next. Updated with every change.

## Project
PS Vita (firmware 3.65 + Ensō) homebrew client for a Hermes Agent 0.23 running on a VPS (`nahezepam.fyi`). Full plan: [`docs/vita-hermes-client-plan.md`](docs/vita-hermes-client-plan.md) (v2).

## Decisions
| Topic | Decision |
|---|---|
| Language / stack | C++17, VitaSDK, vita2d, libcurl + mbedTLS (own CA bundle), yyjson |
| Dev machine | Fedora, with a desktop SDL2 build sharing the core code |
| Transport | HTTPS (TLS 1.2) to the VPS; Hermes itself stays on localhost |
| Bridge (auth/scoping on VPS) | **Owner builds it** (Go suggested). Spec: plan section 6. Not part of this repo's work. |
| UI language | English only |
| Customization | JSON config, profiles, themes, macros, input mapping; Lua later (plan section 5) |

## Files
| Path | What it is | Status |
|---|---|---|
| `docs/vita-hermes-client-plan.md` | Obsidian-ready plan: dev env, stack, architecture, customization, security, milestones, risks | v2, awaiting remaining answers |
| `tools/setup-fedora.sh` | Installs Fedora packages, VitaSDK (via vdpm) and required ports; sets `VITASDK` in `~/.bashrc`. Flags: `--all-ports`, `--skip-dnf` | Written, syntax-checked, **not yet run** (vdpm port names unverified) |
| `tools/mock_hermes.py` | Fake Hermes API (`/health`, `/v1/models`, `/v1/chat/completions`, SSE). Options: `--token`, `--replay FILE`, `--delay`, `--fault {unauthorized,server-error,slow,drop,stall,bad-json}` | Tested: health, auth, models, streamed + non-streamed chat. Faults and `--replay` untested |
| `TRACKER.md` | This file | Maintained |

### Quick use
```bash
tools/setup-fedora.sh                       # then open a new shell
tools/mock_hermes.py --token abcdefghijklmnop
curl -N -H 'Authorization: Bearer abcdefghijklmnop' -H 'Content-Type: application/json' \
  -d '{"stream":true,"messages":[{"role":"user","content":"hi"}]}' http://127.0.0.1:8642/v1/chat/completions
```

## Milestones
| ID | Goal | State |
|---|---|---|
| M0 | Spike: real Hermes API + HTTPS streaming proven, samples recorded | **Next, owner action needed** (see below) |
| M1 | Toolchain + hello-world VPK + `tools/deploy.sh` | Not started (setup script ready) |
| M2 | Platform layer + config system | Not started |
| M3 | HTTPS + SSE streaming (MVP) | Not started |
| M4 | IME input + UX basics | Not started |
| M5 | Customization layer | Not started |
| M6 | History, Markdown, hardening | Not started |
| M7 | Voice and media | Not started |
| M8 | Lua scripting, agent features | Not started |

## Log
| Date | Change |
|---|---|
| 2026-11-06 | Plan v1: feasibility, Fedora env, stack, milestones |
| 2026-11-06 | Plan v2: VPS/HTTPS, security model, customization, English-only |
| 2026-11-06 | Firmware confirmed 3.65 + Ensō; domain, Hermes 0.23, bridge ownership recorded |
| 2026-11-06 | Added `tools/setup-fedora.sh` and `tools/mock_hermes.py` |
| 2026-11-06 | Added this tracker |

## Open items
**Owner actions (M0)**
- [ ] Enable the Hermes API server on the VPS (`API_SERVER_ENABLED=true`, `API_SERVER_KEY` of 16+ chars, then `hermes gateway`); keep it on localhost.
- [ ] Save a real streamed reply with `curl -N` into `docs/samples/real.sse`, so the mock can replay it.
- [ ] Put Caddy in front of the bridge for `nahezepam.fyi` (no response buffering, TLS 1.2 allowed).
- [ ] On the Vita: confirm VitaShell FTP (port 1337) and install the vitacompanion plugin.

**Unverified (check before relying on)**
- Hermes API details: port 8642, bearer auth, SSE format, session behavior, tool events.
- vdpm port names used by `setup-fedora.sh`.
- Whether the vdpm mbedTLS port handles TLS 1.2 ECDHE/AES-GCM and the Let's Encrypt chain.
- Vita API specifics from the plan (IME dialog, audio-in, heap symbol, crash-dump tooling).

**Still-open questions** (defaults in the plan): voice timing, customization priorities, default look, C++ vs other, restricted agent toolset, distribution.
