# 01 - System Overview

## PoC context

- **Location:** Pethapur Godown, Gandhinagar, Gujarat.
- **Scale (PoC):** ~30 CCTV cameras.
- **Network:** 10 Mbps leased line.
- **Time zone:** Asia/Kolkata (IST).
- **Camera roles:**
  - **GATE_ANPR**: dedicated gate camera for vehicle entry/exit.
  - **SECURITY**: all other cameras for security monitoring.

## Goals

1. **Edge-first detection** to reduce bandwidth and latency.
2. **Evidence-based alerts** for accountability and auditability.
3. **Reliable notification delivery** to Godown Managers (real-time) and HQ (digest only).
4. **Scalable rollout** from PoC to ~7000 cameras statewide.

## Stakeholders

- **Godown Manager:** Receives real-time alerts via WhatsApp + Email.
- **HQ (State/District officials):** Receives scheduled digest reports only.
- **Technical operators:** Maintain edge nodes, backend, and dashboard.

## High-level use cases

- **Gate ANPR:** Track vehicle entry/exit and dispatch movement delays.
- **After-hours detection:** Alert if person/vehicle is present after permitted hours.
- **Animal intrusion:** Detect animals entering storage areas.
- **Fire detection:** Detect fire/smoke and alert immediately.
- **Blacklist (watchlist) match:** Alert when a known blacklisted person is detected.
- **Camera health:** Offline/tamper/low-light events.

## Weighbridge integration status

**Not implemented yet.** The current PoC does not ingest weighbridge readings. A future integration would correlate vehicle weight with dispatch sessions.

## Glossary (with Gujarati cues)

- **Godown (ગોડાઉન):** Storage facility.
- **Alert (અલર્ટ):** Important incident notification.
- **Event (ઇવેન્ટ):** Raw detection record.
- **Gate (ગેટ):** Entry/Exit point.
- **Entry / Exit (પ્રવેશ / બહાર):** Vehicle movement at gate.
- **After-hours (સમય પછી):** Outside allowed operating hours.
- **Watchlist/Blacklist (કાળાસૂચિ):** Restricted persons list.
- **Fire (આગ):** Fire or smoke detection.
- **Animal Intrusion (પ્રાણીઓની ઘુસણખોરી):** Animals detected in restricted zones.
- **Evidence (પુરાવો):** Snapshot/clip for verification.

## What success looks like

- **False positives reduced** with multi-frame confirmation and cooldowns.
- **Critical alerts delivered** in near real-time to the right recipients.
- **Digest reports available** for HQ daily review.
- **Scalable architecture** that supports statewide rollout.
