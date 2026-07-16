# Market, buyers, economics, and data access

Research date: 2026-07-17

## Buyer job

The buyer does not purchase semantic search. The payable job, if it exists, is:

> Inspect an authorized moderation history, find recurring campaigns that current
> controls miss, and return bounded controls that can be replayed before they
> are enabled.

The buyer-visible outcome is lower review volume without an unacceptable rise
in legitimate-user harm. A report that merely names themes is not sufficient.

## Segment qualification matrix

This is a desk-research routing judgment, not measured demand. `Export path`
means an official path exists; it does not imply that deleted spam, outcomes,
edits, representative legitimate traffic, or campaign labels are retained.

| Segment | Public pain evidence | Likely paid operator | Export path | Native/DIY pressure | PATAS WTP | Research disposition |
| --- | --- | --- | --- | --- | --- | --- |
| Company-backed support/community forum | Yes | Plausible | Known on self-hosted platforms | High | Unknown | First-cohort hypothesis |
| Zendesk/Intercom support operation | Yes | Yes | Known | Very high | Unknown | Qualify only after forum cohort |
| Monetized independent forum | Yes | Variable | Usually known when self-hosted | High and cheap | Unknown, probably weak | Secondary |
| Forum host or agency | Indirect | Yes | Depends on client authorization | High | Unknown | Possible later channel, not data owner by default |
| OSS or nonprofit community | Yes | Often no | Usually known | High and cheap | Unknown, probably weak | Negative/control interviews |
| Self-hosted business chat | Some | Plausible | Product-specific | High | Unknown | Later research |
| Large marketplace or messenger | Strong | Yes | Internally known but externally gated | Very high enterprise coverage | Unknown | Bad first access path |
| Ordinary Slack, Discord, or Telegram community | Yes | Often volunteer | Restricted or product-specific | High | Unknown | Poor first-pilot fit |

### Recommended first profile

The first commercial search should target a small company, not a hobby forum:

- it operates a company-backed UGC/support service or self-hosted community;
- support or community work is performed by paid staff;
- at least 50 suspicious events arrive per day or the queue consumes at least
  five staff-hours per week;
- campaigns recur across accounts, messages, or edits;
- the operator can export historical spam and legitimate controls;
- an existing PostgreSQL-backed review or control surface can consume the
  first cohort's replay predicate;
- a founder, Head of Support, or Head of Community can approve a small fixed
  purchase.

This profile is an **inference** from data access, buyer speed, and platform
spend. It is not validated willingness to pay.

Self-hosted Discourse is the easiest public path to an export, not necessarily
the easiest path to deployment: Data Explorer is read-only. A vanilla
Discourse or XenForo operator is an interview candidate, but it passes the first
paid-offer gate only if the PostgreSQL replay artifact is operationally useful.
Watched Words, MySQL/XenForo, and custom platform imports are separate cohorts,
not free adapter variation.

### Why ordinary forums and messengers rank lower

Many independent forums use volunteer moderation and compare software against
very low price anchors. XenForo itself costs [$195 self-hosted or from $60 per
month hosted](https://xenforo.com/purchase/); Akismet currently displays Pro at
[CHF 8.95 per month billed yearly](https://akismet.com/pricing/); OOPSpam starts at [$23 per month for
25,000 checks](https://www.oopspam.com/). A real annoyance can therefore coexist
with almost no software budget.

Discourse also launched a [$0 hosted Free plan](https://blog.discourse.org/2026/07/introducing-the-discourse-free-plan/)
on 2026-07-14 with core moderation and admin tools. This new low-end price
anchor makes paid staff time and measurable queue cost more important than
forum size.

Messenger communities have a second problem: data access. Discord requires the
privileged Message Content intent and channel history permission for content
access ([Discord Message resource](https://docs.discord.com/developers/resources/message)).
Slack exports private channels and direct messages only under plan, owner,
approval, and legal constraints ([Slack export documentation](https://slack.com/help/articles/201658943-Export-your-workspace-data)).
Whether an ordinary Telegram or Discord administrator wants a live bot rather
than an offline audit is an **interview hypothesis**, not a fact. Restricted
history access and weak SQL deployment fit are enough to make these poor
first-pilot conditions.

## Observed problem shapes

Public operator accounts show several distinct jobs. PATAS fits only some of
them.

| Problem shape | Public evidence | PATAS fit |
| --- | --- | --- |
| Repeated commercial variants bypass several controls | A XenForo operator described a Temu wave despite Cloudflare Pro, Turnstile, ASN/country blocks, manual rules, and platform controls ([thread](https://xenforo.com/community/threads/temu-spam.228562/)). | Medium, if more than one obvious keyword is needed. |
| Plausible AI-written reputation farming | Discourse operators described generic but relevant posts, dormant accounts, VPN and temporary-email checks, and cases requiring two reviewers ([thread](https://meta.discourse.org/t/are-you-experiencing-ai-based-spam/292707)). | High for historical multi-signal grouping; low for one-post classification. |
| Safe-looking post edited later to add spam | Several Discourse communities reported that approval-style Watched Words could be bypassed by later edits ([thread](https://meta.discourse.org/t/send-edits-of-approved-posts-back-to-approval-queue/231377)). | Medium if revisions are exported. Platform fixes may be better. |
| Large review-queue burst | XenForo operators reported tens to thousands of bots and manual queue work ([approval-queue thread](https://xenforo.com/community/threads/approval-queue-will-this-thing-ever-improve.230153/)). | Medium for cleanup and control discovery; low for stopping the active raid. |
| Registration and CAPTCHA bypass only | XenForo already combines CAPTCHA, reputation sources, flood controls, Akismet, and a spam cleaner ([official features](https://xenforo.com/features/spam/)). | Low. PATAS should not build bot prevention. |
| A native classifier solves the incident | Sonar reports that Discourse AI made a spam wave disappear with about $0.25 of model API usage in its busiest month ([vendor case study](https://blog.discourse.org/2025/01/sonars-25-cent-solution-to-spam-detection/)); that figure is not total operating cost. | Negative control. Do not sell PATAS here unless a separate historical-rule job remains. |

Public cases are qualification inputs, not current leads. For example, the
Temu thread also contains reports that a simple phrase or a corrected XenForo
setting resolved some instances. Every target requires a fresh pain and volume
check before it is treated as a prospect.

## Public cases worth qualifying

No outreach has been sent. These are public evidence cases, not endorsements or
confirmed buyers.

| Case | Why it is useful | Source status | Main unknown |
| --- | --- | --- | --- |
| [ControlBooth / XenForo Temu incident](https://xenforo.com/community/threads/temu-spam.228562/) | Owner-operated, monetized forum and multiple existing controls. | Historical thread includes simple phrase/configuration fixes for some operators. | Whether any current semantic-pattern job remains; current volume and budget. |
| [Best Practical / Request Tracker](https://meta.discourse.org/t/are-you-experiencing-ai-based-spam/292707/5) | Company-backed support community; daily cleanup and ambiguous AI posts were reported. | Historical operator report; current status unknown. | Whether current Discourse AI already solved it. |
| [Aseprite / Igara](https://meta.discourse.org/t/send-edits-of-approved-posts-back-to-approval-queue/231377/9) | Small commercial software company and a concrete edit-spam pattern. | Historical operator report; current status unknown. | Current recurrence and payer priority. |
| [IDM Forums burst](https://meta.discourse.org/t/just-had-about-38-bot-accounts-and-posts-sign-up-and-spam-in-the-space-of-30-mins/375297) | A concrete Discourse burst and likely export path. | Point-in-time incident; current recurrence unknown. | Recurrence and commercial budget. |
| [Invantive support forum](https://meta.discourse.org/t/are-you-experiencing-ai-based-spam/292707/13) | B2B software support context and difficult-to-detect posts. | Historical report at about one event per day. | Whether volume clears a paid-pilot gate. |
| [Zendesk bulk-spam workflow](https://support.zendesk.com/hc/en-us/articles/4408884016410-How-can-I-bulk-delete-spam-tickets-in-Zendesk) | Official workflow acknowledges 100-ticket UI limits and a 1,000-ticket hourly automation limit; 30,000 tickets require at least 30 cycles. | Current documentation of a platform workflow, not a buyer incident. | A named buyer with recurring rather than one-off incidents. |

The first qualification list should include a negative control such as Sonar:
an operator for whom cheap native AI is already sufficient. Understanding why
PATAS is unnecessary is more valuable than collecting polite interest.

## Moderation-cost model

The model must be populated by the buyer. Public research does not provide a
reliable universal review time or cost per spam item.

```text
monthly_manual_cost =
  candidates_per_month * seconds_per_candidate / 3600 * loaded_hourly_cost
  + escalation_cost
  + expected_false_positive_loss

monthly_gross_saving =
  monthly_manual_cost * safely_removed_review_share
  - added_shadow_and_QA_cost

maximum_rational_audit_price =
  monthly_gross_saving * acceptable_payback_months
```

Illustrative sensitivity only:

| Scenario | Assumptions | Manual cost/month | Gross saving before QA |
| --- | --- | ---: | ---: |
| Small forum | 1,000 candidates, 20 seconds, $25/hour | $139 | $42 at 30% reduction |
| Paid community team | 10,000 candidates, 20 seconds, $30/hour | $1,667 | $500 at 30% reduction |
| High-volume operation | 100,000 candidates, 15 seconds, $35/hour | $14,583 | $2,917 at 20% reduction |

These are explicit assumptions, not market facts. They show why a small forum
cannot justify a $1,500 audit from labor savings alone, while a paid operation
with a recurring queue might.

False-positive loss must stay separate from handling cost. Three wrongly
blocked B2B prospects can matter more than thousands of cheap spam decisions.
PATAS therefore needs legitimate counterexamples and a buyer-defined error
ceiling; a generic accuracy number is not an ROI model.

## What the buyer must receive

One fixed pilot should return the same artifact set for every customer:

1. `campaigns.csv`: cluster IDs, row IDs, size, time range, and signal
   provenance.
2. `evidence.json`: representative rows and the exact edges or features that
   support each relationship.
3. `counterexamples.csv`: nearest legitimate examples and unsafe overlap.
4. `rules.json`: typed, reviewable candidate controls.
5. `replay.sql`: the cohort-wide PostgreSQL replay/query predicate compiled
   from the typed control. It is not automatically executed in production.
6. `shadow_report.json`: coverage, spam hits, legitimate hits, temporal slice,
   and the buyer-defined promotion gate.
7. `manifest.json`: dataset fingerprint, provenance, processing authority,
   de-identification state, versions, settings, and reproducibility metadata.

The first pilot excludes production credentials, live integration, custom
dashboards, ongoing moderation, and a connector built only for one customer.
Allowed variation is schema mapping and language selection. A XenForo/MySQL or
platform-specific import is a later cohort decision, not an included custom
adapter.

## Data-access matrix

| Platform | Current official path | Benchmark readiness |
| --- | --- | --- |
| Discourse | Data Explorer runs read-only SQL and exports CSV/JSON; self-hosted data lives in PostgreSQL with full schema access ([Data Explorer](https://www.discourse.org/plugins/data-explorer), [open-source/data ownership](https://www.discourse.org/open-source)). | Export path known. Spam retention, review outcomes, edit history, representative ham, and campaign labels remain buyer checks. |
| XenForo | Self-hosted customers control the database. Cloud includes an API and promises a complete customer-data copy on cancellation, but no direct server access ([pricing](https://xenforo.com/purchase)). | Export path plausible, not confirmed for moderation labels/history. It also falls outside the first PostgreSQL adapter cohort. |
| Zendesk | Ticket, user, and organization exports and APIs exist ([export documentation](https://support.zendesk.com/hc/en-us/articles/4408886165402-Exporting-ticket-user-or-organization-data-from-your-account)). | Export path known; label completeness, PII, deleted spam, and support secrets remain checks. |
| Intercom | Conversation APIs and bulk export paths exist ([conversation export](https://www.intercom.com/help/en/articles/2046229-export-your-conversations-data)). | Export path known; safe redaction, labels, and temporal coverage unknown. |
| Slack | Public-channel JSON is broadly exportable; private channels and DMs need higher plans and approval ([docs](https://slack.com/help/articles/201658943-Export-your-workspace-data)). | Weak first pilot; benchmark fields and authority unknown. |
| Discord | Historical content requires an authorized app, permissions, and privileged content access ([docs](https://docs.discord.com/developers/resources/message)). | Weak first pilot; benchmark fields and authority unknown. |
| Telegram group | No clean universal organization-wide historical SQL contract for this product; contract-era data is excluded. | Exclude from the first pilot. |

Every data-fit preflight must verify retention of removed spam, outcome labels,
edit history, timestamps, representative legitimate traffic, stable IDs, and
enough future coverage for replay. Export availability alone does not pass the
gate.

Minimum pilot fields:

```text
event_id
timestamp
text
moderation_outcome: spam | legitimate | unknown
event_type: post | edit | signup | ticket
optional pseudonymous_actor_id
optional source_or_channel
optional trust_level_or_account_age
optional extracted_url_or_domain
```

Email addresses, IP addresses, names, direct messages, private staff content,
attachments, raw user IDs, and secrets are excluded by default. Pseudonymized
data can still be personal data.

The privacy contract needs purpose limitation, minimization, a defined
retention period, deletion or return, security controls, subprocessor terms,
and processing only on the buyer's instructions. These are not optional trust
copy; they follow GDPR principles and processor-contract requirements
([European Commission](https://commission.europa.eu/law/law-topic/data-protection/rules-business-and-organisations/principles-gdpr/overview-principles/what-data-can-we-process-and-under-which-conditions_en),
[ICO Article 28 guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/contracts-and-liabilities-between-controllers-and-processors-multi/what-needs-to-be-included-in-the-contract/)).

## Price and distribution hypotheses

No PATAS willingness-to-pay evidence exists yet. Public price anchors support
testing, not publishing, these ranges:

- monetized independent forum: $49-$199 self-serve/offline audit;
- small company-backed support community: $500-$1,500 fixed pilot;
- high-volume support or community operation: $2,000-$5,000 only when measured
  monthly savings and risk justify it.

The cleanest first money probe is a **$500 fixed founding pilot**, offered only
after a metadata-only data-fit preflight fixes the row count, label coverage,
date range, retention, and output schema. It uses one standard export mapping,
the predeclared PostgreSQL replay adapter, and no integration. It proves payment
intent, not the final market price. The buyer must provide existing
spam/legitimate decisions and perform a bounded set of requested adjudications;
creating a labeled corpus is not included.

One analyst-day is a delivery target after the reusable path exists, not an
excuse to ignore acquisition, data preflight, privacy/legal work, support, and
buyer annotation. Track all of those costs. If the cohort cannot produce
positive contribution margin at a plausible later price, the offer is not a
business even when the analysis itself is fast.

The first channel is approval-gated direct outreach to 10-20 operators with a
specific public incident and the qualification triggers above. After one case,
Discourse hosting partners and the XenForo resource ecosystem can become
distribution channels. They should not be asked to authorize processing of a
client's data without that client's documented permission.

## Prospect disqualifiers

Reject or defer one prospect when:

- current pain or volume does not pass the qualification threshold;
- native tools solve its stated job in under two hours with acceptable errors;
- it cannot provide both abuse and legitimate history with adequate retention;
- it requires credentials, private messages, raw PII, a custom adapter, or
  direct live enforcement for the first proof;
- it wants general moderation outsourcing rather than the fixed audit.

One disqualified prospect does not kill the market hypothesis.

## Cohort-level market kill criteria

The numeric thresholds below are owner-set falsifiers, not external statistics.
Stay in validation or park the wedge if any of these occur across the cohort:

1. Fewer than five of 15 qualified operator interviews report at least five
   manual hours per week or 50 suspicious events per day.
2. Fewer than three of ten data-qualified prospects can lawfully provide a
   minimized export containing both spam and legitimate controls.
3. No buyer accepts any of five concrete $500 fixed-pilot offers.
4. Three buyer datasets produce no rule that reduces review work by at least
   20% under the buyer's false-positive ceiling.
5. More than 30% of delivery effort is customer-specific ingestion,
   integration, or policy work.
6. Controls repeatedly decay before buyers can deploy them.
7. Acquisition, data preflight, legal/privacy, support, and delivery cost make
   plausible pricing uneconomic.
8. Buyers praise reports but do not deploy a control or measure review-time
   change.
9. No customer wants a second audit after deploying the first controls.
10. Failure to find an anti-spam payer is explained away by renaming PATAS a
    universal semantic platform.
