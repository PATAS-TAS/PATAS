# PATAS trigger-based prospect cohort

Status: ranked research cohort; not a mailing list

Research refresh: 2026-07-20

Owner issue: [#8](https://github.com/PATAS-TAS/PATAS/issues/8)

## Decision

The public evidence supports a narrow first-customer search, not a product
build. Several operated communities still spend real human time on recurring
spam, but public posts do not establish export authority, a PostgreSQL rule
path, or a budget owner. Those remain qualification gates.

The activation queue is ten possible end-user buyers plus two channel probes.
The other eighteen accounts are useful negative controls, deployment
boundaries, or substitute vendors. They must not be rescued with custom
adapters.

Current funnel:

```text
30 researched accounts
13 activation targets
6 first touches sent
2 automated acknowledgements
1 human platform-boundary reply
0 qualified prospects
0 fixed paid offers
0 paid pilots
```

Gmail inspection on 2026-07-20 independently confirmed the two sent end-user
emails, the two automated acknowledgements, and one human platform-boundary
reply found in Spam. The reply supports a distinct historical-analysis layer
but clears none of the buyer qualification gates. No matching NodeBB reply was
found. A same-day self-test then confirmed from
the raw MIME header that the visible sender name still fails the identity gate
in the response playbook. Pavilion's official `contact@pavilion.tech` route was
verified and the single plain-text channel probe was sent from the authenticated
Gmail account on 2026-07-20 with Nick's full PATAS signature and an explicit
no-follow-up opt-out. Communiteq's official form still requires a controllable
browser session. On 2026-07-22, Gmail's sender identity was corrected and
verified by self-test. The official Mumsnet all-other-queries route was then
re-verified and one bounded end-user currentness probe was accepted into Sent;
this proves neither delivery nor interest.

## Scoring contract

Each factor is scored `0`, `1`, or `2` from public evidence:

- `P`: recurring pain and measurable human cost;
- `T`: timing or incident recency;
- `D`: plausible authorized history plus PostgreSQL replay path;
- `B`: identifiable operating company and plausible budget;
- `R`: permitted, relevant business contact route;
- `U`: fit with the frozen reusable PATAS input/output contract.

The total ranks research attention only. It never upgrades an unknown into a
fact. A pilot offer still requires current pain, workload, native-tool gap,
abuse and legitimate history, processing authority, PostgreSQL deployment,
and a budget owner.

## Activation queue

| Rank | Account | Role | P/T/D/B/R/U | Total | Public trigger | Contact state | Next action |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | Bambu Lab / MakerWorld | End user | 2/2/2/2/1/2 | 11 | A moderator reported a couple of hours of daily work, much of it spam bots and flags, in June 2026. | Channel not yet approved | Find a relevant company/community business route; do not use a forum DM or generic support ticket. |
| 2 | McNeel / Rhino | End user | 2/1/2/2/2/2 | 11 | Staff manually removed an Italian-forum attack and separately described active removal of AI foothold accounts. | EMEA company directory verified | Address a currentness probe to the community operator through an appropriate McNeel business contact, not technical support. |
| 3 | Home Assistant / Nabu Casa | End user | 2/1/2/2/1/2 | 10 | More than 300 posts in one night caused registration/first-post restrictions and 20-30 reviews per hour. | Relevant business route not yet verified | Verify the community owner's business contact and whether the 2025 wave became recurring work. |
| 4 | n8n | End user | 1/2/2/2/2/1 | 10 | A 2026 moderator announcement names spam and AI-answer policy as staffed work. | LinkedIn route blocked; not sent | Find an official non-forum route to the named community lead or close as unreachable. |
| 5 | Arduino | End user | 1/1/2/2/1/2 | 9 | A named admin described AI-written foothold spam and an ongoing manual detection policy. | Relevant company route not yet verified | Ask whether the job is material after current Discourse controls; no forum solicitation. |
| 6 | MoneySavingExpert | End user | 1/2/1/2/2/1 | 9 | A large commercial forum maintains a staff/member spam-busting workflow. | Sent 2026-07-18; automated acknowledgement | Wait for the stated two-working-day handling window, then at most one follow-up. |
| 7 | PistonHeads | End user | 1/2/1/2/2/1 | 9 | Current rules restrict overnight posting when moderation is unavailable. | Sent 2026-07-18; automated acknowledgement | Wait ten working days as requested; one follow-up only if appropriate. |
| 8 | Best Practical | End user | 1/1/2/2/2/1 | 9 | Named admin reported plausible AI replies used to build reputation before spam. | US commercial-email legal gate | Do not send until a compliant postal-address and opt-out footer exist; first ask whether native Discourse AI solved it. |
| 9 | Aseprite / Igara | End user | 1/1/2/1/2/2 | 9 | Founder reported posts edited after approval to bypass Watched Words. | Professional route identified; not sent | Verify country-specific outreach rules, then send the existing one-question currentness probe. |
| 10 | BleepingComputer | End user boundary | 2/1/0/2/2/1 | 8 | An admin reported removing 30+ spammers and 40+ posts in one day amid a daily stream. | Official general/product-evaluation form | Ask only whether the workload remains material; disqualify if a non-PostgreSQL adapter would be required. |
| 11 | Communiteq | Channel | 0/2/2/2/2/2 | 10 | Managed Discourse host can identify a permissioned customer and test one reusable deployment contract. | Prepared; not confirmed sent | Send the existing channel question through the official form. No processor-held customer data. |
| 12 | Pavilion | Channel | 0/2/2/2/2/2 | 10 | Discourse consultancy can test whether the gap repeats across paying communities. | Sent 2026-07-20 from authenticated Gmail; delivery, reading, and interest unknown | Wait for a human reply. Do not follow up before 2026-07-27, and do not commission a plugin before a buyer pays. |
| 13 | Mumsnet | End user | 1/2/1/2/2/1 | 9 | A commercial forum has an active company moderation surface and current public discussion of deceptive AI-assisted participation. | Sent 2026-07-22 from authenticated Gmail; delivery, reading, and interest unknown | Wait for a human reply. Do not follow up before 2026-07-29. |

### Evidence for new activation targets

- Bambu Lab: [June 2026 moderation workload](https://forum.bambulab.com/t/does-this-forum-have-any-moderators/254608).
- McNeel: [September 2025 spam attack](https://discourse.mcneel.com/t/italian-mcneel-discours-under-spam-attack/209689), [AI foothold removal](https://discourse.mcneel.com/t/i-would-rather-not-have-ai-on-rhinos-forum/206687), and [official EMEA company directory](https://www.rhino3d.com/en/mcneel/contact/emea/).
- Home Assistant: [May 2025 attack and review load](https://community.home-assistant.io/t/spam-maybe-time-to-change-the-forum-rules/891040).
- Arduino: [admin account of AI-assisted foothold spam](https://forum.arduino.cc/t/use-of-ai-generated-content-by-forum-helpers/1353366).
- BleepingComputer: [operator account](https://www.bleepingcomputer.com/forums/t/801438/spambots-on-the-forum/) and [official contact form](https://www.bleepingcomputer.com/contact/).
- Mumsnet: [official company contact](https://www.mumsnet.com/i/contact) and [company/controller identity](https://www.mumsnet.com/i/privacy-policy).

### Prepared copy for new activation targets

These are held until the route in the activation table is verified. Add the
normal founder signature and `If this isn't relevant, I won't follow up.` Do
not add a deck, tracking link, attachment, or calendar link.

**Bambu Lab / MakerWorld — subject: `Bambu community spam workload`**

```text
Hi Bambu Lab Community team — a forum moderator said in June that keeping the forum clean takes a couple of hours a day and a good chunk is spam bots and user flags. Is recurring cross-post spam still material after current Discourse controls, or is most of that time ordinary moderation? I’m validating PATAS, an offline audit of past decisions that returns cited campaign patterns and rule candidates for staff review. “Mostly spam” or “mostly other moderation” is enough.
```

**McNeel / Rhino — subject: `Rhino forum campaign-spam workload`**

```text
Hi McNeel Community team — McNeel staff handled an Italian-forum spam attack and separately described removing AI-generated foothold accounts. Is that now a recurring paid-staff job, or did current Discourse controls solve it? I’m validating PATAS, an offline audit of past moderation decisions that finds recurring campaigns and proposes reviewable PostgreSQL rules. A one-line “recurring” or “solved” is enough.
```

**Home Assistant / Nabu Casa — subject: `Home Assistant recurring spam workload`**

```text
Hi Nabu Casa Community team — during the May 2025 wave, more than 300 posts led to temporary registration and first-post restrictions plus 20-30 reviews per hour. Did current Discourse controls make that exceptional, or do recurring variants still cost at least five staff-hours a week? I’m validating PATAS, an offline audit of past moderation decisions that returns cited campaigns and reviewable rule candidates. “Exceptional” or “still recurring” is enough.
```

**Arduino — subject: `Arduino forum AI-spam workload`**

```text
Hi Arduino Community team — a forum admin described AI-written foothold posts used to hide later spam, while noting they had become easier to spot. Is this still a meaningful staff workload after current Discourse controls, or mostly handled? I’m validating PATAS, an offline audit of past moderation decisions that finds recurring campaigns and proposes rules for staff review. A one-line “material” or “handled” is enough.
```

**BleepingComputer — subject: `BleepingComputer recurring forum spam`**

```text
Hi BleepingComputer team — an admin previously described removing more than 30 spammers and 40 posts in one day against a steady daily stream. Is recurring content spam still taking several staff-hours a week, or is it now handled by current controls? I’m validating PATAS, an offline historical pattern-audit idea, not proposing an integration. A one-line “still material” or “handled” is enough.
```

## Follow-up calendar

These are earliest permitted windows, not automatic sends:

| Account | Current state | Earliest action |
| --- | --- | --- |
| gVectors / wpForo | Human platform-boundary reply received; no buyer gate cleared | No silence follow-up. Retain as substitute/channel evidence unless an opt-in end-user independently appears. |
| NodeBB | First form submitted 2026-07-17; no matching reply in connected Gmail | One final form follow-up from 2026-07-24 through 2026-07-28, then close silent. |
| MoneySavingExpert | Email sent; automated acknowledgement promises handling within two working days | Do not follow up before 2026-07-22; then one final reply in the existing thread if no human response. |
| PistonHeads | Email sent; automated acknowledgement asks for up to ten working days | Do not follow up before 2026-08-03; then one final reply in the existing thread if no human response. |

Every follow-up is cancelled by a human response, an opt-out, a solved answer,
or evidence that the original channel was inappropriate.

## Research and boundary queue

| # | Account | Role | P/T/D/B/R/U | Total | Why it is not in the activation twelve |
| ---: | --- | --- | --- | ---: | --- |
| 13 | wpForo / gVectors | Platform/channel | 1/2/0/2/2/0 | 7 | Sent 2026-07-17. WordPress/MySQL and native AI make this a substitute test, not the frozen pilot. |
| 14 | NodeBB | Platform/channel | 1/2/0/2/2/0 | 7 | Sent 2026-07-17. Native controls and a non-PostgreSQL product path; useful only if several hosted buyers share a gap. |
| 15 | Masto.host | Channel | 0/1/2/1/2/2 | 8 | PostgreSQL-native, but no current customer pain or common enforcement contract is public. |
| 16 | ControlBooth | End-user boundary | 1/1/0/1/2/0 | 5 | XenForo/MySQL incident may have been solved by configuration and phrase rules. |
| 17 | Invantive | End-user boundary | 0/1/2/2/2/1 | 8 | Public volume was about one account per day, below the economic gate. |
| 18 | IDM Forums | Research only | 1/2/2/0/0/2 | 7 | Forum solicitation is prohibited and no separate payer/business route is verified. |
| 19 | Epic Developer Community | Enterprise boundary | 2/1/2/2/1/1 | 9 | Strong delayed-edit/LLM pattern, but procurement and internal-build risk are too high for the first pilot. |
| 20 | MacRumors | End-user boundary | 2/1/0/2/1/1 | 7 | Hundreds of removals and reports, but likely XenForo/MySQL and no relevant business route verified. |
| 21 | Shopify Community | Enterprise boundary | 1/1/0/2/1/1 | 6 | Subtle app-promotion spam is real, but the likely internal platform and procurement path violate the minimum pilot. |
| 22 | Grafana Labs Community | Negative control | 0/1/2/2/1/1 | 7 | Public evidence is mainly false-positive holding, not recurring paid spam work. |
| 23 | Atlassian Community | Negative control | 0/2/0/2/2/0 | 6 | Dedicated internal team and internal reporting surface; likely build internally. |
| 24 | Docker Community | Negative control | 0/1/2/2/1/1 | 7 | One legitimate post was held; no evidence of a material recurring operator job. |
| 25 | Bettermode | Substitute vendor | 1/2/0/2/2/0 | 7 | Customers report filter gaps, but Bettermode is shipping its own AI moderation agent. |
| 26 | Higher Logic Vanilla | Substitute vendor | 0/1/0/2/2/0 | 5 | Its own moderation/pre-moderation suite addresses the job; no end-user trigger was qualified. |
| 27 | Khoros | Substitute vendor | 1/1/0/2/2/0 | 6 | Native quarantine workflow and enterprise platform make it a benchmark, not an early buyer. |
| 28 | XenForo Ltd | Substitute/channel | 2/2/0/2/2/0 | 8 | Customers publicly report manual queues despite add-ons, but the platform is MySQL and sells native controls. |
| 29 | Discourse Inc | Substitute/channel | 1/2/2/2/2/0 | 9 | Native AI spam detection is the central substitute; use it to falsify PATAS, not as a first customer. |
| 30 | OzzModz / Xon add-ons | Substitute vendor | 1/2/0/1/2/0 | 6 | Existing paid XenForo add-ons may be the cheaper answer for that platform. |

### Boundary evidence

- Epic: [LLM-written posts later edited to malware links](https://forums.unrealengine.com/t/something-really-strange-is-happening-to-this-forum/2656570).
- MacRumors: [hundreds of spam removals and more than 100 reports](https://forums.macrumors.com/threads/why-do-we-need-to-wait-5-minutes-between-two-reports.2450513/).
- Shopify: [repeated app promotion across old threads](https://community.shopify.com/t/ongoing-issue-with-app-promotion-on-old-threads/408136).
- Grafana: [legitimate community post held as spam](https://community.grafana.com/t/why-my-thread-is-not-showing-live/149206).
- Atlassian: [valid posts repeatedly marked for moderation](https://community.atlassian.com/forums/Jira-questions/My-post-keeps-being-marked-for-moderation/qaq-p/2936271) and [dedicated team feedback loop](https://community.atlassian.com/forums/Community-Announcements-articles/How-your-2025-feedback-shaped-the-Atlassian-Community-forums/ba-p/3183717).
- Docker: [legitimate non-English post flagged as spam](https://forums.docker.com/t/unexpected-eof-when-pulling-an-image-in-docker-desktop/149684).
- Bettermode: [spam getting through AI filters](https://bettermode.com/hub/community/ask-for-help/post/spam-posts-getting-through-ai-filters-228nfRPokgKzNgy) and [vendor mitigation update](https://bettermode.com/hub/product-updates/post/october-2025-update-faster-cleaner-events-on-deck-GkjdUOAFryoCtuP).
- Higher Logic: [pre-moderation guidance for large communities](https://success.vanillaforums.com/kb/articles/304-pre-moderate-content).
- XenForo: [32 casino profiles per day despite multiple controls](https://xenforo.com/community/threads/spam-and-new-member-issues.232532/), [large approval queue](https://xenforo.com/community/threads/prevent-user-from-posting-after-x-post-sent-to-moderation-queue-for-approval.233364/), and [native spam tools](https://xenforo.com/features/spam/).
- Discourse: [native AI spam detection replaces Akismet](https://meta.discourse.org/t/discourse-ai-spam-detection-replaces-akismet-plugin/354602) and [bulk deletion added after spam waves](https://meta.discourse.org/t/bulk-user-deletion-for-staff-now-available/345786).

## Daily execution rules

1. Work only down the activation queue, at no more than two first touches per
   weekday and one follow-up after the recipient's stated response window.
2. Use an official business channel or a named professional route. Do not use
   forum posts, forum private messages, scraped personal addresses, enrichment,
   mail merge, or multiple mailboxes.
3. First touch is a currentness probe with one question. Do not attach the
   sample card, ask for data, request a call, or mention a bespoke feature.
4. After a positive reply, use the metadata-only qualification in
   [OUTREACH-RESPONSE-PLAYBOOK.md](OUTREACH-RESPONSE-PLAYBOOK.md).
5. Send the identical [$500 pilot](../sales/FOUNDING-PILOT.md) only after every
   buyer gate is answered. No adapter, dashboard, connector, or free audit.

## Cohort kill and continuation rules

- After 20 compliant first touches: if fewer than three human conversations or
  no prospect reaches qualification, stop this cohort and change the segment or
  channel. Do not build from silence.
- After five identical paid offers to qualified buyers: if none pays, stop the
  offer and revisit the job, price, or buyer. Do not discount or add custom work
  to force a conversion.
- A negative reply naming a cheaper native solution is evidence. Record it and
  close the lead instead of inventing another PATAS use case.
- A paid pilot authorizes the disposable benchmark only after metadata,
  processing terms, payment, and minimized data transfer are complete.
