# PATAS outreach response and paid design-partner playbook

Status: active; 5 first touches sent, 2 automated acknowledgements, 1 human
platform-boundary reply, 0 qualified prospects, and 0 paid offers as of
2026-07-20

Research date: 2026-07-17

Owner issue: [#8](https://github.com/PATAS-TAS/PATAS/issues/8)

## Bottom line

The first email should not ask a cold prospect to become a design partner. It
should test whether the public problem is still current and economically
material. `Design partner` becomes useful only after the operator clears the
qualification gates and agrees to contribute money, bounded staff time,
authorized data, and a real deploy-or-reject decision.

The shortest path from a positive reply to cash has three buyer moves:

1. answer a short asynchronous qualification and metadata-only fit check;
2. accept one fixed one-page scope, processing terms, and invoice;
3. pay the $500 pilot price before customer data is transferred.

A call, deck, custom demo, free analysis, live integration, and feature
workshop are not required. Payment is first revenue, not yet profit. The pilot
becomes a plausible gross-profit result only if delivery stays within the
existing one-analyst-day cap and requires no customer-specific code.

## Likely answers and what PATAS does next

| Reply | Meaning | Next action | Stop condition |
| --- | --- | --- | --- |
| No reply | Unknown, not rejection | Send the one approved follow-up after 5-7 business days. | Close after that; do not start a sequence. |
| `Solved`, `native AI handles it`, or `not material` | Useful negative control | Thank them and record the tool or process that solved it. | Do not rescue the lead with a new use case. |
| `Still painful` | Pain is current, but fit and willingness to pay remain unknown | Ask asynchronously for last week's suspicious volume or staff time, tools already tried, recurring campaign shape, data authority, operational rule destination, and budget owner. | Close or park if any decisive gate fails. |
| `Send information` or `send a deck` | Low-effort curiosity | Send the one-paragraph fixed scope and ask for the same numeric qualification facts. | Do not build a deck or proposal for an unqualified lead. |
| `Show me a demo` | They want proof before effort | Link the existing generic demo or a sanitized sample artifact, then qualify. | No customer-specific demo before payment. |
| `Can it ban automatically?` or `Can you integrate with our stack?` | They are asking for TAS, an adapter, or outsourcing | State that the first cohort is an offline audit with a frozen output contract and human review. | If live action or custom integration is mandatory, disqualify. |
| `We do not use PostgreSQL` | Current first-cohort contract does not fit | Record the platform as boundary evidence. | Do not build an adapter to win this pilot. |
| `Can we try it free?` or `No budget` | No money proof | Offer a short research interview only, with no analysis or deliverable. | A free audit is not a design partnership. |
| `What accuracy do you guarantee?` | Legitimate risk question | Explain temporal replay, legitimate counterexamples, and the buyer-defined false-positive ceiling. | Do not invent a universal accuracy or savings claim. |
| `We can send the data now` | Premature data risk | Ask them not to send it. Complete the metadata-only preflight, processing terms, minimization, transfer, retention, and deletion plan first. | Do not download or ingest an unsolicited export. |
| `Security/legal needs to review` | Possible buyer, slower path | Send the bounded data flow, fields, processor purpose, retention/deletion terms, and no-credentials/no-production-access scope. | No bespoke procurement project for a $500 test. |
| `Yes, let's do it` | Still not complete until fit, scope, and money are explicit | Run the metadata-only preflight, then send the one-page scope, processing terms, and invoice together. | No raw data before fit, authority, terms, and payment are accepted. |

### Minimal reply to `still painful`

```text
Thanks — that may fit. Before I suggest a pilot, could you share roughly how many suspicious items or staff-hours this cost last week, which filters or AI controls are already enabled, whether the problem repeats across messages or accounts, and whether your current workflow can test a PostgreSQL rule without a new integration? No export yet. If those facts line up, I’ll send one fixed scope; otherwise PATAS is probably the wrong tool.
```

### Minimal reply to `send information`

```text
Happy to. The current test is deliberately narrow: one authorized historical export, one schema, up to 100,000 short-text events, cited campaign groups, legitimate counterexamples, candidate rules, and a later-period PostgreSQL replay. No credentials, connector, dashboard, or automatic bans. Before I send the one-page scope, what did the workload cost last week and which native controls have already been tried?
```

### Minimal reply when data is offered too early

```text
Please don't send an export yet. I first need a metadata-only description of the schema, row counts, date range, moderation labels, legitimate comparison rows, and SQL dialect, plus confirmation that your organization can authorize this processing. If that fits, we will agree the transfer, retention, and deletion terms before any customer data moves.
```

## What the first-wave prospects are most likely to say

These are forecasts, not evidence of current buyer intent. They make the next
action predictable before a reply arrives.

| Prospect | Plausible answer | PATAS decision |
| --- | --- | --- |
| Communiteq | Native Discourse controls are enough, no current customer has the threshold, or they want a plugin/partner arrangement first. | Advance only with an opt-in end customer and a reusable export/deployment contract; do not commission a plugin. |
| n8n | The remaining job is moderator policy and low-value AI replies rather than repeated spam campaigns. | Close unless a current campaign-shaped job clears the workload gate. |
| PistonHeads | The restriction and AI checks already contain the problem, or the internal platform/data cannot enter the frozen SQL path. | Qualify the paid operator and rule destination; no internal-platform integration. |
| MoneySavingExpert | No vendor response, a procurement/privacy boundary, or a material manual workflow without a usable export. | One follow-up only; advance only with a named operator, data authority, and operational destination. |
| Best Practical | The 2024 incident was solved by the plugin or current Discourse AI. | Treat `solved` as a strong negative control; qualify only if a new recurring variant remains material. |
| Aseprite | The edit-after-approval case is solved, too rare, or has no budget. | Close unless current paid staff time clears the threshold. |
| Pavilion | They can build a plugin but ask who the buyer is or who will pay for integration. | Correct response: no plugin before a qualified end-user pilot pays. |
| gVectors / wpForo | Native wpForo AI now covers it, or they want MySQL/OEM support. | Keep as substitute/channel evidence; do not bend the PostgreSQL cohort around it. |

## Minimal path to first revenue and first profit

### Before a positive reply

- Send the approved currentness probe manually.
- Record only organization, role, public source, date, and response status.
- Do not request data, a call, an NDA, or a budget in the first touch.

### After a positive reply

1. **Asynchronous fit and metadata-only check.** Confirm the numeric workload,
   repeated campaign shape, native-tool gap, abuse plus legitimate history,
   processing authority, PostgreSQL rule path, operator, and budget owner. Also
   inspect field names, types, counts, label coverage, time range,
   deleted-content retention, and SQL dialect without receiving customer rows.
2. **Optional 20-minute evidence call.** Use it only if the operator cannot
   answer the facts in writing. Review one recent incident; do not run a feature
   wishlist workshop.
3. **One-page scope, processing terms, and full $500 invoice.** Keep the frozen
   dataset, row, artifact, time, and integration limits. Record
   controller/processor roles, purpose, fields, minimization, transfer,
   retention, deletion, incident contact, and ownership of generated controls.
   An NDA does not replace these terms. Payment is due before customer data is
   transferred.
4. **Bounded delivery.** Run the frozen audit, return the existing artifact
   contract, and spend no more than one analyst-day after accepted input.
5. **Deploy-or-reject review.** The operator reviews all proposed controls and
   either tests at least one in shadow/production under its own authority or
   records why none is safe.
6. **Commercial verdict.** Ask for a second paid audit or a clearly priced
   recurring job. Praise without deployment or repeat willingness is not
   product validation.

No product build is a prerequisite to the first invoice. Existing manual or
concierge work is acceptable behind the frozen artifact contract. A feature
requested by the first buyer enters the product backlog only if it preserves
the common input/output contract and would plausibly serve at least three
customers in the target segment. Otherwise it is declined as custom work.

## Paid design-partner contract

Use `founding paid pilot partner` in the scope if `design partner` would be
unclear. The label does not matter; reciprocal commitment does.

### Partner contributes

- one named moderation operator;
- one named budget approver and one data-processing approver, which may be the
  same person;
- the full $500 pilot payment before data transfer;
- one metadata-only preflight and one minimized authorized export;
- a 30-minute kickoff only if asynchronous answers are insufficient;
- review of every proposed control and at most 25 uncertain pair judgments;
- one 30-minute result review and a deploy-or-reject decision;
- permission to retain only explicitly agreed de-identified product-learning
  metadata, not raw customer data by default.

### PATAS contributes

- one fixed artifact contract: `campaigns.csv`, `evidence.json`,
  `counterexamples.csv`, `rules.json`, `replay.sql`, `shadow_report.json`, and
  `manifest.json`;
- one schema mapping and the predeclared PostgreSQL replay path;
- no production credentials or direct moderation actions;
- a stated retention/deletion date;
- no public logo, quote, or case study without separate permission;
- no promise that a candidate rule is safe until the buyer's replay and review
  satisfy its own false-positive ceiling.

### One-page agreement fields

1. exact recurring-spam problem and current weekly cost;
2. named operator, budget owner, and data approver;
3. asynchronous check-ins and at most two short meetings;
4. metadata, authorized data fields, transfer, retention, and deletion;
5. pilot start/end and the accepted-input condition;
6. success: usable campaign evidence, temporal replay, buyer review, and a
   deploy-or-reject decision — not an invented accuracy percentage;
7. $500 pilot price and the separately agreed post-pilot price or decision
   date;
8. explicit exclusions: connector, dashboard, custom adapter, model training,
   automatic ban, ongoing moderation, and customer-specific feature work.

`Interesting, keep us posted`, a free dataset, or periodic feedback without a
budget owner is a lead, not a design partner.

## Which sender to use

No address prevents spam classification or account suspension. Authentication,
recipient relevance, complaint rate, legal compliance, and sending behavior
matter more than the mailbox label.

### Current domain evidence

Public DNS checked on 2026-07-17 shows:

- `patas.app` has Cloudflare Email Routing MX, root SPF, and the routing DKIM
  selector, but no public DMARC record and no Cloudflare outbound-sending
  `cf-bounce` records;
- `kikuai.dev` has routing records plus DMARC and Brevo DKIM, but Brevo requires
  consent or an existing business relationship for campaigns and prohibits
  lists copied from public websites or social networks;
- Cloudflare Email Routing is inbound forwarding, not proof of an authenticated
  human outbound mailbox; Cloudflare's outbound Email Service is currently
  intended only for transactional email.

Therefore the first direct emails should be sent manually from Nick's existing
authenticated human Gmail account, with the display name `Nick Dudnichenko —
PATAS`. Use the same Gmail address for `From` and replies. Do not republish the
personal address in this public playbook and do not spoof `support@patas.app`
through Gmail's alias feature.

Live connector inspection on 2026-07-20 confirmed mailbox access but found that
the account's current sender display name does not match the required founder
identity. Do not send another cold email from that account until the display
name is corrected and a self-test confirms the visible `From` identity. This is
an identity/trust gate, not a reason to rotate mailboxes.

This is a first-wave decision, not the desired permanent brand mailbox. The
long-term address should be a real human mailbox such as `nick@patas.app` on a
provider that signs outgoing mail for `patas.app`. Before it is used, the
domain must have aligned SPF, 2048-bit DKIM, and DMARC starting at `p=none`, and
a test message's original headers must show `SPF=PASS`, `DKIM=PASS`, and
`DMARC=PASS`. `support@patas.app` remains for support, not founder outreach.

### First-wave sending rules

- Use the listed contact form or professional LinkedIn route when that is the
  verified channel; email only the rows with an official business address.
- Send one recipient at a time, manually, at one or two messages per day. No
  BCC, automation, mail merge, purchased/enriched list, or mailbox rotation.
- Plain text only; no attachment, tracking pixel, link shortener, fake `Re:`,
  or calendar link. Use at most one normal product/source link when needed.
- Use an accurate, boring subject and one low-friction question.
- Add a human signature, product URL, and `If this isn't relevant, I won't
  follow up.` Maintain a suppression list for objections and opt-outs.
- For a commercial message to a US recipient, include a valid business postal
  address and a working opt-out. If Nick does not have a safe valid postal
  address for the signature, do not send the Best Practical email yet.
- UK corporate subscribers generally do not require prior PECR consent for B2B
  email, but personal data still needs a lawful basis and privacy notice; sole
  traders and some partnerships require consent. Other countries must be
  checked before adding new recipients.
- Stop after the single follow-up. The generic advice to send three to five
  touches is inappropriate for this tiny validation wave.

Google requires all senders to authenticate mail and recommends SPF, DKIM, and
DMARC even below bulk volume. Its current guidance also ties spam complaints to
future filtering. The FTC applies CAN-SPAM to B2B commercial email as well as
bulk campaigns and requires accurate headers, a truthful subject, a postal
address, and an honored opt-out.

Sources: [Google sender requirements](https://support.google.com/mail/answer/81126),
[Google Gmail program policies](https://support.google.com/mail/answer/16734397),
[Cloudflare sending versus routing DNS](https://developers.cloudflare.com/email-service/configuration/domains/),
[Cloudflare transactional-only boundary](https://developers.cloudflare.com/email-service/reference/faq/),
[Brevo anti-spam policy](https://help.brevo.com/hc/en-us/articles/209405205-What-is-the-anti-spam-policy-of-Brevo),
[FTC CAN-SPAM guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business),
[UK ICO B2B marketing guidance](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/).

## Verdict on the two external skill repositories

### `coreyhaines31/marketingskills`

Useful as a reference, not as a 47-skill installation for this phase. Its
`product-marketing` and `cold-email` guidance correctly emphasizes shared
product context, source-connected personalization, plain text, brevity, and one
low-friction ask. PATAS already has stronger project-specific context in this
research pack. Its generic recommendation of three to five follow-ups conflicts
with the one-follow-up boundary required here.

Do not install the whole repository now. Reuse only the few principles that
survive PATAS's qualification, permission, and anti-outsourcing gates.

Source: [Marketing Skills README](https://github.com/coreyhaines31/marketingskills),
[cold-email skill](https://github.com/coreyhaines31/marketingskills/blob/main/skills/cold-email/SKILL.md).

### `Kappaemme-git/codex-first-customer-finder-skill`

Useful later as a read-only second-wave challenger. Greg Brockman did share the
author's post on 2026-07-13, and the repository explicitly keeps outreach
manual, avoids private enrichment, links public evidence, and labels prospects
as hypotheses. The installer only copies the bundled skill, although it
deletes any existing `first-customer-finder` installation before replacing it;
the HTML generator is local Python with no third-party dependency and escapes
text and URLs.

It is not a buyer validator. Its generic weighted score can rank a public pain
signal highly without proving PATAS's decisive gates: paid staff time, native
tool failure, abuse plus legitimate rows, processing authority, SQL deployment,
and a budget owner. Its `design-partners` mode changes prospect priority but
does not require money, data rights, bounded review work, or a deploy decision.

Do not install or rerun it over the completed first wave. After the eight
current probes have real outcomes, it can be run in an isolated read-only
second-wave exercise and must beat the existing roster by finding candidates
that clear the PATAS gates. It must never send messages or write to a CRM.

Sources: [repository and stated boundaries](https://github.com/Kappaemme-git/codex-first-customer-finder-skill),
[Greg Brockman's share](https://x.com/gdb/status/2076686329686171666).

## Recording and decision states

Use only these states:

```text
uncontacted
sent
no_reply_followup_due
closed_silent
solved_negative_control
qualifying
disqualified_problem
disqualified_data_or_rights
disqualified_deployment
disqualified_budget
scope_sent
paid_design_partner
delivered
deployed_or_shadowed
closed_no_repeat_value
repeat_paid
```

Record facts, not sales optimism. `Qualifying` is not a design partner,
`scope_sent` is not revenue, `paid_design_partner` is not a successful product,
and `delivered` is not repeatable value until a control is reviewed and the
buyer makes a second commercial decision.
