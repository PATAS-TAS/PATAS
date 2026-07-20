# PATAS first-customer outreach roster

Status: activation in progress; 4 of 20 first touches sent — 2 on 2026-07-17
and 2 on 2026-07-18. The two email entries are confirmed only as accepted
into Gmail Sent; delivery, reading, and recipient interest remain unknown.

Initial research date: 2026-07-17; current ranking is maintained in the
[thirty-account trigger cohort](PROSPECT-COHORT-30.md)

Owner issue: [#8](https://github.com/PATAS-TAS/PATAS/issues/8)

Reply handling, the minimal paid path, design-partner boundaries, and sender
configuration are defined in the
[outreach response playbook](OUTREACH-RESPONSE-PLAYBOOK.md).

## Bottom line

There is no publicly verified prospect who should receive the $500 offer now.
Every end-user candidate still has at least one decisive unknown: current
volume and staff time, the gap after native controls, operational rule
deployment, retained labeled data, or budget authority.

The first outbound wave is therefore a set of short currentness probes, not a
product pitch. The purpose is to find an A-tier buyer, not to convert old public
spam complaints into fictional leads.

Run two lanes in parallel:

1. five plausible end-user buyers with paid staff or a real operating company;
2. three platform specialists who can identify several customers with the same
   platform contract.

Do not request data, a database dump, credentials, an NDA, or a call in the
first message. Send no more than one follow-up after silence.

## Send order

| Order | Recipient | Channel | Why now | Current class |
| --- | --- | --- | --- | --- |
| 1 | Richard at Communiteq | [Official contact form](https://www.communiteq.com/contact/) | One reusable Discourse path could reach several permissioned customers. | Channel discovery |
| 2 | Bart Veldhuizen, n8n Community Lead | [Professional LinkedIn](https://nl.linkedin.com/in/bartveldhuizen) | A commercial company's growing community has fresh AI-reply abuse evidence, added its first moderator, and plans more coverage. | B-tier currentness probe |
| 3 | PistonHeads Forum Team | `info@pistonheads.com` | Current public controls explicitly exist because moderation is thin overnight. | B-tier currentness probe; sent 2026-07-18 |
| 4 | MSE Forum Team | `forumteam@moneysavingexpert.com` via the [company contact directory](https://www.moneysavingexpert.com/site/site-contacts/) | A company-backed, extremely busy forum has a dedicated team and a current manual spam-busting workflow. | B-tier currentness probe; sent 2026-07-18 |
| 5 | Jim Brandt, Best Practical | Address to Jim via `sales@bestpractical.com` | Named admin, real company, Discourse/PostgreSQL, and a precise human/AI reputation-farming incident. | B-tier currentness probe |
| 6 | David Capello, Aseprite / Igara | [Professional LinkedIn](https://ar.linkedin.com/in/davidcapello); `support@aseprite.org` fallback | Named founder reported edit-after-approval variants bypassing Watched Words. | B/C-tier currentness probe |
| 7 | Angus McLeod at Pavilion | `contact@pavilion.tech` from the [official company site](https://pavilion.tech/) | Discourse implementation partner who can test whether the deployment gap is reusable. | Channel discovery |
| 8 | Robert / gVectors wpForo product team | `info@gvectors.com` or [business contact form](https://gvectors.com/contact-us/) | A forum-platform vendor had a fresh hundred-topic attack and now ships native AI controls. | Platform boundary/channel probe; sent 2026-07-17 |
| 9 | RFJ and wayne, IDM Forums admins | No permitted business channel verified | Small design-partner candidate with recent hands-on spam handling, but forum solicitation is prohibited. | Research only; do not contact |
| 10 | Hugo Gameiro, Masto.host | `info@masto.host` | PostgreSQL-native managed communities; useful channel test beyond Discourse. | Channel interview only |
| 11 | David, ControlBooth founder | [Official contact form](https://www.controlbooth.com/misc/contact) | Non-Discourse counterexample with a public whack-a-mole incident. | Interview only; no pilot offer |
| 12 | Guido Leenders, Invantive | `sales@invantive.eu` | SQL-literate commercial operator and adjacent multilingual support-quality case. | Boundary interview only |
| 13 | NodeBB team | [Official contact form](https://nodebb.org/contact) | A forum-platform and managed-hosting vendor can directly falsify whether the historical campaign-to-rule gap survives bundled controls or is cheaper to build in-house. | Platform boundary/channel probe; sent 2026-07-17 |

Rows 1-8 were the prepared first wave. NodeBB was added as a channel-safe
platform-boundary substitute when Gmail required reauthentication and the n8n
LinkedIn route required a paid subscription. Rows 9-12 should be used only if
the first wave does not produce enough qualified conversations or if a specific
boundary needs testing.

## Exact first-touch messages

The copy is deliberately short. Each message cites one observable fact, asks
one question, and makes it easy to answer `solved` without entering a sales
funnel. Add Nick's normal work signature; do not invent a company title or add
an attachment, calendar link, deck, or tracking link.

### 1. Communiteq — Richard

**Send via:** [Communiteq contact form](https://www.communiteq.com/contact/)

**Subject:** Discourse campaign-level spam gap

```text
Hi Richard — Communiteq manages Discourse hosting and builds plugins and integrations for business customers. I’m validating PATAS, an offline audit that finds recurring campaigns in an authorized history and returns rules for review. Do you see a customer where Discourse AI or Akismet is already enabled, recurring variants still take 5+ staff-hours a week, and a permissioned introduction would be appropriate? “No, native tools cover it” is equally useful.
```

**Why this recipient:** Communiteq says Richard owns its control panel,
plugin/theme development, and integrations; the company provides managed
Discourse hosting and reusable integration work for SMB, mid-market, and
enterprise customers. This is a distribution and platform-fit probe, not a
request for processor-held customer data.

**Advance only if:** Richard can name an opt-in customer meeting the workload
threshold and confirms that one reusable Discourse export/deployment contract
could serve more than that customer.

Sources: [Communiteq team and services](https://www.communiteq.com/about-us/),
[official contact](https://www.communiteq.com/contact/).

### 2. n8n — Bart Veldhuizen

**Send via:** [Bart's professional LinkedIn](https://nl.linkedin.com/in/bartveldhuizen),
not an n8n forum private message

**Subject:** n8n community moderation workload

```text
Hi Bart — your May update says n8n’s first Community Moderator handles spam and AI-answer policy, and that more coverage is planned. Is repeated low-value or abusive content still taking meaningful staff time, or has the new setup handled it? I’m testing whether an offline review of past moderation decisions can reveal reusable patterns. “Still material” or “handled” is enough.
```

**Why this recipient:** n8n is a commercial company with a growing support
community. Bart publicly introduced the first Community Moderator in May 2026,
said more coverage is planned, and named spam removal and AI-answer policy as
part of the role. A January incident shows automated replies creating noise,
but does not prove a continuing campaign or enough spam-specific workload.

**Advance only if:** the remaining job is recurring across messages or
accounts, is not merely ordinary community cleanup, clears the workload gate,
and has an operational output that PATAS can produce without custom moderation
outsourcing.

Sources: [January automated-reply incident](https://community.n8n.io/t/uploading-file-using-onedrive-node-ignores-file-name-field-2/245373),
[May 2026 moderator announcement](https://community.n8n.io/t/meet-anshul-our-new-community-moderator/294876),
[forum solicitation restriction](https://community.n8n.io/tos).

### 3. PistonHeads — Forum Team

**Sent to:** `info@pistonheads.com` on 2026-07-18

**Subject:** PistonHeads forum spam workload

```text
Hi PistonHeads Forum Team — your current guidance says new members cannot post overnight to limit spam when moderation is unavailable. Is recurring spam still consuming at least several staff-hours a week despite your filters and AI checks, or is it now solved? I’m testing PATAS, a small offline review that uses past moderation decisions to find repeated campaigns and suggest rules for staff review. A one-line “solved” or “still material” is enough.
```

**Why this recipient:** PistonHeads is a commercial CarGurus-owned operation,
publishes a forum-specific contact, and still documents a product restriction
introduced to prevent spam during unmoderated hours. This proves an operating
constraint, not the current economic threshold or database fit.

**Advance only if:** the team confirms current recurring variants and at least
five staff-hours per week, then routes the conversation to the person who owns
moderation operations and budget.

Sources: [current forum restriction](https://www.pistonheads.com/faq/forum-faq),
[AI checks and daily volume](https://www.pistonheads.com/rules-of-posting),
[official forum contact](https://www.pistonheads.com/contact/).

### 4. MoneySavingExpert — MSE Forum Team

**Sent to:** `forumteam@moneysavingexpert.com` on 2026-07-18

**Subject:** MSE recurring spam workload

```text
Hi MSE Forum Team — your current Spam-Busting guide still relies on staff, ambassadors, and members to review suspicious accounts and posts. Is recurring spam consuming at least several staff-hours a week after your existing filters, or is that workload now minor? I’m testing PATAS, an offline review of past moderation decisions that looks for repeated campaigns and possible rules. A rough “material” or “minor” is enough.
```

**Why this recipient:** MSE describes the forum as extremely busy, exposes a
dedicated Forum Team contact, and maintains a proactive spam-busting workflow.
Its platform and export/replay path are unknown, so the first message asks only
whether there is an economic problem. The official company contact directory
routes company questions about the forum to this team, but this is not a sales
inbox; stop after the single permitted follow-up if there is no reply.

**Advance only if:** paid staff own a material recurring workload; then qualify
platform, historical labels, export rights, and deployment separately.

Sources: [current Forum Guide](https://www.moneysavingexpert.com/site/forum-faqs/),
[Spam-Busting Guide](https://forums.moneysavingexpert.com/discussion/5906563/spam),
[company contact directory](https://www.moneysavingexpert.com/site/site-contacts/).

### 5. Best Practical — Jim Brandt

**Send to:** `sales@bestpractical.com`, addressed to Jim Brandt

**Subject:** RT forum AI-spam workload

```text
Hi Jim — I found your March 2024 note about plausible AI-written replies being used to build trust before later spam. Did today’s Discourse AI and your added plugin solve that, or are recurring variants still taking staff time? I’m testing PATAS, an offline review that looks for repeated campaigns in past moderation decisions and suggests rules for human review. A one-line “solved” or “still painful” is enough.
```

**Why this recipient:** Jim publicly described the incident and the response.
Best Practical is a real software and services company, and its forum runs on
Discourse. The incident is old, so this is explicitly a currentness test.

**Advance only if:** the problem remains current after the added plugin/native
AI and clears the workload threshold. A PostgreSQL backup is useful for an
offline audit, but read-only SQL alone is not a production control surface.

Sources: [Jim's incident report](https://forum.bestpractical.com/t/too-much-spam-at-forum-bestpractical-com/39322),
[official company contact](https://requesttracker.com/about/),
[forum team](https://forum.bestpractical.com/about).

### 6. Aseprite / Igara — David Capello

**Send via:** [David's professional LinkedIn](https://ar.linkedin.com/in/davidcapello);
use `support@aseprite.org` only as the official fallback

**Subject:** Aseprite edited-post spam

```text
Hi David — I found your September 2024 report about approved posts later being edited to bypass Watched Words. Did current Discourse edit scanning solve it, or are recurring variants still taking staff time? I’m testing PATAS, an offline review that finds repeated campaigns in past moderation decisions and checks possible rules against legitimate posts. A one-line “solved” or “still painful” is enough.
```

**Why this recipient:** David is the named operator who reported a campaign
shape that simple first-post filtering missed, and Aseprite provides an official
business support route. Current volume, staffing, native-AI status, retained
rejected rows, and budget are still unknown.

**Advance only if:** the bypass remains current, repeats across messages or
accounts, and costs paid staff enough time to clear the economic threshold.

Sources: [David's report](https://meta.discourse.org/t/send-edits-of-approved-posts-back-to-approval-queue/231377/9),
[official Aseprite support](https://www.aseprite.org/support/).

### 7. Pavilion — Angus McLeod

**Send to:** `contact@pavilion.tech`, published on the [official Pavilion
site](https://pavilion.tech/)

**Subject:** Reusable Discourse campaign rules

```text
Hi Angus — Pavilion builds Discourse plugins and works with large communities. I’m validating PATAS, an offline audit for recurring spam campaigns with cited counterexamples and PostgreSQL replay. Do you have a client where native AI is already tried, the problem still costs 5+ staff-hours a week, and the result could enter an existing PostgreSQL-backed control workflow? I’m trying to determine whether that gap is real before building it.
```

**Why this recipient:** Pavilion publicly describes itself as a leading
Discourse consultancy and lists Angus as a current member. It can test both
client demand and whether compound PATAS controls can be deployed once through
a reusable plugin rather than customer-specific code.

**Advance only if:** there is an opt-in client and Pavilion sees a reusable
implementation contract. Do not commission a plugin before an end-user buyer
qualifies and pays.

Source: [Pavilion team, clients, and contact](https://pavilion.tech/).

### 8. wpForo / gVectors — Robert and product team

**Sent via:** [official business contact form](https://gvectors.com/contact-us/)
on 2026-07-17, addressed to Robert / the wpForo product team

**Subject:** wpForo historical spam-rule gap

```text
Hi Robert — I saw the December attack that filled the wpForo support forum with hundreds of topics while staff were away. I’m validating PATAS, an offline audit that groups recurring campaigns and tests rule candidates against legitimate history. Would that have added value beyond wpForo 3’s current AI and flood controls, or is historical rule generation now fully covered? A one-line product-boundary answer is enough; I’m not proposing an integration.
```

**Why this recipient:** gVectors owns a forum platform, paid products, a recent
high-volume incident, and new native AI moderation. It is therefore both a
possible channel and a strong substitute threat. wpForo is WordPress/MySQL, so
it is not eligible for the frozen PostgreSQL pilot without a reusable product
decision.

**Advance only if:** gVectors confirms a remaining campaign-level job across
several wpForo operators. Do not start with white-labeling, build a MySQL
adapter, or pitch against their native AI before that proof.

Sources: [December 2025 attack](https://wpforo.com/community/general-discussions/spam-attack-2/),
[wpForo 3 AI controls](https://wpforo.com/community/faq/how-to-stop-spam/),
[gVectors contact](https://gvectors.com/contact-us/).

### 13. NodeBB — product and hosting team

**Sent via:** [official contact form](https://nodebb.org/contact) on 2026-07-17

```text
Hi NodeBB team — I saw Spam-Be-Gone is bundled, while operators still ask how to combine its controls. I’m validating PATAS: an offline audit that groups recurring campaigns in historical abuse reports and tests candidate rules against legitimate history. Is historical campaign-to-rule discovery still a gap for hosted NodeBB operators, or already covered well enough? A one-line answer is enough; no integration pitch.

Nick Dudnichenko — PATAS
https://patas.app
If irrelevant, I won’t follow up.
```

**Why this recipient:** NodeBB both develops the forum platform and sells
managed hosting and enterprise work. It bundles Spam-Be-Gone, and the public
support record contains operator questions about combining the available
controls. A negative answer is valuable: this is a direct build-versus-buy and
native-substitute test, not a request for custom development.

**Advance only if:** the team confirms that multiple hosted operators retain a
campaign-level gap after current controls. Do not offer a NodeBB adapter or
white-label work before a qualified end-user buyer exists.

Sources: [NodeBB product and hosting](https://nodebb.org/),
[official contact form](https://nodebb.org/contact),
[Spam-Be-Gone operator question](https://community.nodebb.org/topic/16163/best-practices-on-stopping-spam-need-advice-on-spam-be-gone-options).

## Second-wave boundary interviews

These contacts are useful to disprove assumptions. They are not substitutes
for the first commercial cohort.

### 9. IDM Forums — no permitted outreach channel

**Do not send:** IDM Forums has a current public admin list and hands-on pain,
but its terms prohibit advertising or other solicitation through the forum.
No separate business channel has been verified, and the published activity and
commercial payer evidence are weak. Keep it as research evidence unless an
admin independently invites contact outside the forum.

Sources: [admin list and current activity](https://idmforums.com/about),
[2025 incident discussion](https://idmforums.com/t/prakash-hinduja-net-worth-booster-what-are-the-rules-for-the-sample-pack-challenges/8337?page=2),
[terms](https://idmforums.com/tos).

### 10. Masto.host — Hugo Gameiro

**Send to:** `info@masto.host`

**Subject:** Recurring text-spam on managed Mastodon

```text
Hi Hugo — Masto.host runs managed Mastodon instances, so you see recurring operational needs across different communities. I’m validating an offline audit that finds repeated spam campaigns in a community’s own history and returns rules for review. Do any instance owners spend 5+ moderator-hours a week on recurring text-spam variants and might welcome a permissioned introduction? If not, “not a recurring problem” is equally useful.
```

**Use:** channel interview beyond Discourse. Mastodon is PostgreSQL-native, but
no current customer pain or common enforcement contract has been verified.
Any data conversation must be directly authorized by the customer controller.

Sources: [Masto.host help and official contact](https://masto.host/help/),
[privacy roles](https://masto.host/privacy/).

### 11. ControlBooth — David

**Send via:** [official contact form](https://www.controlbooth.com/misc/contact)

**Subject:** ControlBooth recurring Temu spam

```text
Hi David — I found the January 2025 XenForo thread describing Temu spam as whack-a-mole despite Cloudflare, Turnstile, and forum rules. Did the later phrase and configuration fixes solve it for ControlBooth, or do recurring variants still return? I’m validating an offline pattern-audit idea, not pitching an integration. “Solved” or “still recurring” is enough.
```

**Use:** negative/non-Discourse interview only. ControlBooth runs XenForo/MySQL,
and the public thread suggests that ordinary configuration or phrase rules may
have solved the incident. Do not build a XenForo adapter or quote the
PostgreSQL pilot for this prospect.

Sources: [public incident](https://xenforo.com/community/threads/temu-spam.228562/),
[ControlBooth contact](https://www.controlbooth.com/misc/contact),
[founder context](https://www.controlbooth.com/threads/how-has-controlbooth-helped-you.51333/).

### 12. Invantive — Guido Leenders

**Send to:** `sales@invantive.eu`, addressed to Guido

**Subject:** Invantive AI-spam review workload

```text
Hi Guido — you previously described roughly one plausible AI-spam account per day on the Invantive support forum. Has that volume or review burden changed materially since Discourse AI became available? I’m validating an offline pattern-audit product and need an honest boundary case. A one-line “still low,” “materially higher,” or “solved” would be very useful.
```

**Use:** boundary interview. The historical spam volume was below the PATAS
gate, while Invantive's newer concern about vague AI-generated support questions
may be a different semantic-triage job rather than spam-rule generation.

Sources: [operator account](https://meta.discourse.org/t/are-you-experiencing-ai-based-spam/292707),
[current AI-question policy](https://forums.invantive.com/t/asking-questions-using-ai/6683),
[official company contact](https://cloud.invantive.com/en/contact).

## What to send after a positive reply

Do not send the $500 offer merely because someone replies `still painful`.
First qualify the economics and operational surface.

```text
Thanks — that may fit. Before I suggest anything, could you share roughly how many suspicious items or staff-hours this cost last week, which filters or AI controls are already enabled, and whether your current system can test and apply a PostgreSQL rule without a new integration? No export yet. If the volume, operational fit, and data authority line up, I’ll send a fixed one-page scope; otherwise PATAS is probably the wrong tool.
```

If the reply confirms the threshold, ask for these facts before mentioning
payment:

- named moderation or support owner and named budget approver;
- at least 50 suspicious events per day or five staff-hours per week;
- a recent recurring cross-message campaign, not just signup bots or one raid;
- native AI, rules, and queues already tried and the exact remaining job;
- retained abuse decisions, representative legitimate rows, timestamps, and a
  future slice;
- authority to provide a minimized export and authority for PATAS to process it;
- an existing PostgreSQL-backed review or control workflow that can consume the
  frozen replay result without a new plugin or platform-specific adapter.

## Paid offer only after qualification

```text
Based on what you shared, I can offer a fixed $500 pilot: one authorized export, one schema, up to 100,000 short-text events, and the agreed PostgreSQL replay format. You receive cited campaign groups, legitimate counterexamples, rule candidates with defined fields, and test results on a later period. No credentials, live connector, custom adapter, or automatic bans. We first agree a metadata-only fit check and processing terms. Would you like the exact one-page scope?
```

The price is a money test, not a discount story. Do not promise accuracy,
percentage savings, or safe production bans before a temporal replay and buyer
review exist.

## One follow-up after silence

Send once after five to seven business days, then stop.

```text
Hi [Name] — one last follow-up on the question below. I’m trying to distinguish a current recurring moderation job from an incident that native tools already solved. A one-line “still material” or “solved” is enough, and I won’t follow up again if this is not relevant.
```

## Explicit skip list

- **Sonar:** native Discourse AI publicly solved its incident at negligible
  marginal cost. Keep it as a competitor/negative-control case, not a paid
  prospect.
- **Screenly / Anthias:** native Discourse AI was enabled after the reported
  flood and the current forum is small. Keep only as a false-positive and
  native-tool counterexample.
- **Zendesk documentation:** product documentation is not a customer lead.
- **Generic OSS forums:** public pain without a legal owner and budget is not a
  first-customer path.

## Recording rule

For every response, record only organization, role, source/date, current pain,
volume or staff time, native-tool status, platform/deployment surface, retained
data shape, processing authority, budget owner, and next status. Do not collect
spam text, usernames, IP addresses, or customer data during qualification.

No external message was sent while preparing the initial roster. Nick
authorized execution of the bounded plan on 2026-07-20; the channel, identity,
legal, rate, qualification, and one-follow-up gates still apply.
