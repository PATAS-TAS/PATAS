---
type: Verified Completion
title: Customer-validation route refresh without unsafe outbound action
description: McNeel now has a verified B2B routing surface, BleepingComputer is correctly CAPTCHA-blocked, and no send occurred without the required Gmail scan.
resource: https://github.com/PATAS-TAS/PATAS/issues/8
tags: [completion, hq-sync]
timestamp: 2026-07-27T21:45:29Z
project: patas
hq_project_status: In Progress
---

# Outcome

The first-customer queue now has one additional actionable end-user route:
McNeel Europe's official sales inbox can route the existing Rhino Community
currentness probe. BleepingComputer is no longer represented as directly
reachable because its relevant public form requires reCAPTCHA.

# Evidence

- McNeel's official Europe contact page identifies `sales.eu@mcneel.com` for
  sales and business routing, separately from technical support.
- BleepingComputer's official contact page exposes reCAPTCHA on the relevant
  form.
- The Gmail connector exposed no mailbox-search, thread-read, or send tools in
  this run. No browser workaround, follow-up, duplicate-prone first touch, or
  data request was attempted.

# Remaining

The funnel remains at six first touches, one substantive platform-boundary
reply, zero qualified buyers, zero offers, and zero paid pilots. Several
follow-up windows are open, but they remain held until All Mail, Spam, and Sent
can be checked.

# Next Trigger

The Gmail connector exposes mailbox tools. Scan every contacted recipient,
classify replies and bounces, then use only still-valid follow-up windows before
the verified McNeel first touch.
