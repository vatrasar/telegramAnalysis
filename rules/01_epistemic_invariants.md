---
trigger: always_on
---

# Analytical Invariants, Falsification Gates & Disentanglement Protocols

These rules establish non-negotiable epistemic invariants, evidence validation gates, and linguistic disambiguation standards for analyzing longitudinal chat records. They prevent hallucinations, premature conclusions, and misattribution errors.

> [!IMPORTANT]
> **Universal Epistemic Scope:**
> These invariants (bidirectional context verification $N-5 \dots N+5$, pronoun disambiguation, third-party entity boundary protection, irrealis vs. realis, timeline bridging ban, and cardinality audits) are universal and non-negotiable across ALL tasks.

---

## 1. Mandatory Bidirectional Context Audit (Unconditional $N-5$ to $N+5$ Rule)

The agent is strictly forbidden from deriving analytical conclusions, biographical traits, or psychodynamic claims from an isolated message in a vacuum.
- **Antecedent Traceback (Look Back $N-5 \dots N$):**
  1. *Stimulus & Anchor:* Determine what question, event, or conversational prompt triggered the message.
  2. *Lead-In & Pasted Text:* Check whether preceding turns announced forwarded or pasted third-party content (*"look what he wrote"*, *"forwarding"*).
  3. *Sarcasm & Banter:* Verify whether the statement represents dry humor, mocking mimicry, or inside jokes.
- **Next-Turn Proof Procedure (Look Ahead $N+1 \dots N+5$):**
  1. Inspect how the interlocutor received message $N$ (validation, mockery, or challenge).
  2. *Immediate Rebuttal Invalidation:* If a proposition in message $N$ is contradicted or rejected in turns $N+1 \dots N+5$ (*"No"*, *"Who said that"*), the agent is strictly forbidden from adopting it as fact.

### 1.1 Anti-Snippet Ingestion Rule
- Text teasers or search match previews from CLI outputs are discovery pointers, NEVER admissible evidence.
- The agent is unconditionally forbidden from quoting or extracting facts directly from search previews without inspecting full context via `query_chat.py --around <msg_id> -n 5` or `-t <thread_id>`.

### 1.2 Thread Boundary & Parent-Child Lineage Protocol
- Dialogue threads are partitioned at 50 messages (`MAX_THREAD_MESSAGES = 50`) and linked via `parent_thread_id`.
- If an analyzed message carries analytical weight and is within the first 5 or last 5 messages of a thread, the agent MUST audit adjacent turns across the boundary using `query_chat.py --around <msg_id> -n 5` or traversing parent/child threads (`-t <parent_or_child_thread_id>`).
- Single-message threads require auditing $\pm 5$ chronological messages around them via `--around <msg_id> -n 5`.

### 1.3 Bare-Pronoun Search Attribution Ban
- When a keyword search returns a message dominated by a bare third-person pronoun (*"He works at"*, *"On ma kota"*, *"Ona studiuje"*), the agent is STRICTLY PROHIBITED from attributing that trait to a subject based on conversational inertia.
- The agent MUST inspect $N-5 \dots N$ via `--around <msg_id> -n 5` to locate the explicit proper noun antecedent.

### 1.4 Sender-vs-Author Disambiguation Principle
- The `sender` field indicates the transport account, NOT intellectual authorship.
- Pasted external questionnaires, forwarded emails, articles, or partner text sent from the subject's account must never be attributed to the subject's inner psychology without antecedent audit ($N-5 \dots N$).

### 1.5 Zero-Unverified-Quote Invariant
- Every verbatim quote and biographical claim in reports or dossiers MUST undergo a 3-point contextual audit ($N-5 \dots N+5$):
  1. *Authorship Origin:* Personally authored vs. pasted/forwarded text.
  2. *Conversational Tone:* Sincere vs. sarcasm, playful exaggeration, or banter.
  3. *Interlocutor Reception:* Verified reception in turns $N+1 \dots N+5$.

---

## 2. Vocative & Left-Dislocation Protocol (Chat Syntax Disambiguation)

In informal chats and ESL communication, utterances beginning with a proper name followed by a descriptor:
`"[Name], [descriptor/noun phrase], [predicate]"` (e.g. *"Szymon, the diabetic guy, he is so kind..."*)
MUST NOT be parsed as an appositive clause attributing the descriptor to the named person.
1. **Default Parse:** Direct address followed by a topicalized third party:
   $$\text{[Vocative: Name]} + \text{[Topic NP: Descriptor]} + \text{[Comment: he/she is \dots]}$$
2. **Next-Turn Lookahead:** Inspect interlocutor turns ($N+1 \dots N+3$). If the named interlocutor refers to the subject in the third person (*"Why do you like him?"*), the descriptor belongs strictly to the third party.

---

## 3. Medical & Somatic Grounding Gate

- **Ban on Third-Party Hearsay:** Chronic illnesses (diabetes, epilepsy, heart disease) or formal psychiatric diagnoses must NEVER be attributed to a subject based on interlocutor jokes, teasing, or passing remarks.
- **First-Person Self-Declaration:** Attributable only via direct, serious first-person self-declaration by the subject (`sender == subject`).

---

## 4. Third-Party Entity Boundary

- When chat participants discuss coworkers, bosses, acquaintances, suitors, or family members, all nicknames, physical traits, occupations, and medical/demographic descriptors belong strictly to the external entity.
- The agent must actively verify that traits of discussed third parties never leak onto conversation participants.

---

## 5. The Actuation Gate (Modality & Irrealis vs. Realis)

- Verbs of modality, aspirations, job offers, or desires (*"offered"*, *"wanted to"*, *"applied"*, *"planned"*, *"dreamed"*, *"chciał"*) must NEVER be converted into established biographical facts or completed professions.
- An event or title is a biographical fact only if verified by evidence of execution or duration (*"worked there 2 years"*, *"graduated"*).
- Always audit the resolution: Was the offer accepted, rejected, or abandoned?

---

## 6. Span Claim Gate & Timeline Bridging Ban

- Strictly prohibited from synthesizing continuous multi-year spans (e.g. *"2020–2023"*) from disjointed mentions in distant years.
- Verify continuity across intervening years or cite a direct statement of duration. Distinguish between *"known casually since [Year]"* vs. *"actively dated during [Year]"*.

---

## 7. Entity Disambiguation Engine & Cardinality Invariants

1. **Relational Roles vs. NPC Filter:** Distinct relational roles (*"sister"*, *"ex"*, *"boss"*) denote verified bonds. Generic demographic labels (*"indian guy"*, *"policeman"*) are surface descriptors; categorize as Episodic Bystander / NPC.
2. **Cardinality Protocol ($K=1$ vs. $K \ge 2$):**
   - Applies to ANY relational role, kinship label, or geographic tag (*"sister"*, *"brother"*, *"ex"*, *"US guy"*, *"boss"*).
   - Never assume uniqueness ($K=1$). Execute a targeted query (e.g. `query_chat.py -C <chat_id> -s "sister OR sisters"`) to determine cardinality:
     - **$K=1$ (Singleton):** Proven single entity across entire chat. Direct mapping permitted.
     - **$K \ge 2$ (Multi-Entity):** Plural mentions or distinct individuals exist. A bare role mention CANNOT be mapped without an audited distinguishing anchor (e.g. `Sister_Epilepsy` vs. `Sister_Older`).
   - Cardinality status must be recorded in descriptors to avoid redundant auditing.
3. **Proportional Verification:** Ambient low-stakes activities need no identity resolution. Mandatory identity verification is required for biographical milestones, relationship spans, violence, financial deals, and core trauma.
4. **Pronoun Resolution in Multi-Entity Threads:** In threads discussing multiple third parties, personal pronouns (*he*, *she*, *on*, *ona*) must never be mapped to a character without verifying the antecedent proper name in $N-5 \dots N$.
5. **No Collective-to-Individual Leakage:** Beliefs or traits of a social unit (family, ethnic group) must never be attributed to an individual without explicit personal affirmation.
6. **Hermetic Chat-Level Scoping:** Role descriptors and third-party entities are strictly scoped to their conversation (`chat_id`). Entities never cross chat boundaries (*"sister"* in chat A has zero relation to *"sister"* in chat B).
7. **Anti-Interlocutor Memory Bias:** Interlocutor misremembering or speculation has ZERO evidentiary authority. If the subject clarifies or refutes (*"not my ex"*, *"to nie ten"*), the interlocutor's statement is invalid.

---

## 8. Evidentiary Pruning & Anti-Eureka Checks

- **Anti-"Eureka!" Check:** A single matching quote is merely a preliminary hypothesis. Check baseline consistency across the archive before concluding.
- **Evidentiary Pruning Rule:** If a life sphere or habit (sports, pets, cleaning) was never mentioned, omit it entirely from reports. NEVER write placeholder disclaimers (*"Brak danych"*, *"No information available"*).
- **Fact-Pinning:** Every factual descriptor, milestone, or occupation in profiles and character tables must be pinned to a message anchor (`[#ID | YYYY-MM-DD]`).

---

## 9. Multi-Party Entity Audit & Watchdog Loop Gate

When auditing multi-party chat archives for third parties, suitors, and acquaintances, the agent must prevent Single-Entity Blindness. Activate the `entity-watchdog-audit` skill to execute the sequential System-1 gatekeeper check and double-check cursor protocol before concluding entity identification.
