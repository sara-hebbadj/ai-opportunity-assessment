# Risk screen for the top use cases

> **General information, not legal advice.** A structured first screen for a portfolio project about a
> fictional company, written with help from a coding agent on 8 October 2026 and to be reviewed by Sara.
> A qualified lawyer must review any real deployment. It reuses the templates and the sources of the AI
> governance pack in this portfolio (P8), checked there on 8 October 2026; laws change, so check them again.

**Client:** Falcon Bay Services LLC (fictional), a 600-person services firm on the Dubai mainland.
**Process:** domestic travel-expense claims by its own employees.
**Use cases screened:** UC01 receipt and policy pre-check, UC02 approver assistant (the top 2), plus the two
use cases whose risk drove their low scores: UC08 straight-through approval and UC18 fraud-risk score per employee.

## 1. Which rules could apply

| Rule set | Applies to Falcon Bay? | Why |
|---|---|---|
| **UAE Federal Decree-Law No. 45 of 2021 on the Protection of Personal Data (PDPL)** | **Yes** | Mainland Dubai company processing employees' personal data (names, trips, amounts, receipts). In force since 2 January 2022; Executive Regulations still pending as of the P8 sources [UAE-1, UAE-3, UAE-4]. |
| DIFC Data Protection Law 2020 + Regulation 10 (autonomous systems) | No, unless the firm sits in the DIFC | The PDPL does not apply in free zones with their own data-protection law (PDPL Art. 2). |
| **EU AI Act (Regulation (EU) 2024/1689)** | **Probably not** today | It applies to providers placing AI on the EU market and to deployers in the EU, or where the output is used in the EU (Art. 2). Falcon Bay has no EU operations. We still classify the use cases with it, because group clients and auditors use it as a benchmark, and because the firm may later serve EU clients. |
| **NIST AI RMF 1.0** | Voluntary | Used as a checklist for managing the risks, not as law [NIST-1]. |

## 2. EU AI Act classification (as a benchmark)

The question for each use case: is it a prohibited practice (Art. 5), high-risk (Art. 6 with Annex III),
a transparency case (Art. 50), or minimal risk?

The Annex III area that matters here is **point 4, employment and workers' management**: AI systems
"intended to be used to make decisions affecting terms of work-related relationships, … or to monitor
and evaluate the performance and behaviour of persons in such relationships" [EU-2, Annex III]. After the
Digital Omnibus, the high-risk rules for Annex III systems apply from **2 December 2027** [EU-2, Art. 113; EU-4].
The AI-literacy duty (Art. 4) already applies to staff who run and supervise an AI system.

| Use case | What the AI does | Classification (reasoning) |
|---|---|---|
| **UC01 receipt and policy pre-check** | Reads the employee's own claim before submission and **warns** them about likely policy problems. It does not reject, approve, score the person or report to the manager. | **Minimal risk, if it stays advisory.** It does not make or materially shape a decision about the employee: the employee decides whether to fix the claim, and the finance clerk still makes the decision. Keep it that way: if its flags were sent to managers or used to rank employees, it would start to "monitor and evaluate the behaviour" of workers (Annex III 4(b)) and need a new screen. If it chats with the employee, say clearly that it is an AI (Art. 50(1) applies to systems that interact directly with people). |
| **UC02 approver assistant** | Reminds approvers and gives a one-line summary of the claim. | **Minimal risk.** It supports the approver, who still decides. Risk to watch: automation bias (approving because the summary looks fine). The summary must never say "approve"; it shows facts and the pre-check flags. |
| UC08 straight-through approval | Pays small, compliant claims without a human approver; a human samples some. | **Borderline.** Approving or not approving an employee's reimbursement is a decision that affects them. With rules only (no AI model) it is not an "AI system" decision; with an ML risk score it could fall under Annex III 4(b). This is why it scored 2 on risk. |
| UC18 fraud-risk score per employee | Scores each employee's history for fraud risk. | **Likely high-risk (Annex III 4(b))** if EU law applied: it evaluates the behaviour of workers. It also conflicts with what staff asked for ("flag the claim, not the person"). Scored 1 on risk; **not recommended**. |

## 3. UAE PDPL notes (employees' data)

- **Lawful basis.** Processing claims is needed to perform the employment contract and to meet the
  employer's legal duties (PDPL Art. 4 exceptions to consent). Using the same data to *train* or *tune* a
  model is a new purpose: document it, minimise it, and do not reuse claims for anything else without a fresh
  assessment.
- **Automated decisions (Art. 18).** Employees can object to decisions based on automated processing that
  have legal consequences or seriously affect them [UAE-1]. UC01 and UC02 keep a human decision, which is the
  simplest way to stay clear of this. UC08 would need a clear objection route and human review on request.
- **Data minimisation.** The pre-check needs the claim lines and the receipts, not the employee's name or
  bank details. Send the model a claim with the employee ID only.
- **Cross-border transfer.** A cloud model behind OpenRouter probably runs outside the UAE. IT already said
  that "any AI tool must stay inside our cloud tenancy in the UAE" (interview I11). Options: a model hosted in a
  UAE region, or a transfer assessment and data-processing terms with every company in the chain. The
  Executive Regulations that will set the transfer rules are still pending.
- **Security and retention.** Receipts can show card digits, hotel guest names and locations. Mask card
  numbers before sending, log prompts without receipt images, and keep traces no longer than the claim
  records themselves.
- **Transparency to staff.** Tell employees what the pre-check reads, that it only warns, and who sees its output.

## 4. NIST AI RMF quick map (UC01, the pilot)

| Function | What it means here | Pilot action |
|---|---|---|
| **Govern** | Who owns the pre-check, who may change the prompt or the rules, who can stop it | Owner: finance operations lead. Change log for prompts and policy text. Kill criteria in `pilot_plan.md`. 30-minute AI-literacy briefing for clerks and the pilot group (EU Art. 4 as good practice). |
| **Map** | Context and harms: false flags annoy staff and waste time; missed problems pass to the clerk as today; personal data leaves the UAE | Write the intended use ("advisory, before submission") and the uses that are out of scope (ranking staff, auto-rejecting). |
| **Measure** | Precision and recall on planted problems, false-flag rate on real claims, cost per claim, latency | The prototype already measures these on 50 synthetic claims; the pilot adds clerk-reviewed real claims. |
| **Manage** | Monitor, respond, retire | Weekly review of a sample of flags; a switch to turn the model off and keep the rules; the kill criteria. |

Generative-AI risks from NIST AI 600-1 that matter most here: **confabulation** (inventing a problem that is
not on the receipt), **data privacy** (receipts sent to a third party), **information security** (a receipt
or a claim text that tries to instruct the model; the prompt treats the claim as data) and **human-AI
configuration** (approvers trusting flags too much) [NIST-2].

## Sources

The source IDs refer to the AI governance pack's `governance/sources.md` (P8), checked on 8 October 2026:
EU-1 Regulation (EU) 2024/1689 (EUR-Lex); EU-2 AI Act Service Desk article pages and Annex III
(consolidated text of 27 July 2026); EU-4 Council press release of 7 May 2026 on the Digital Omnibus;
NIST-1 AI RMF 1.0 (NIST AI 100-1); NIST-2 Generative AI Profile (NIST AI 600-1); UAE-1 Federal Decree-Law
No. 45 of 2021 (UAE Legislation portal); UAE-3 Al Tamimi & Co., 1 September 2026; UAE-4 Ashurst Perkins Coie,
Data Bytes 67, July 2026.
