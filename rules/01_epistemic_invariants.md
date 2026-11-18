---
trigger: always_on
---

# Analytical Invariants, Falsification Gates & Disentanglement Protocols

These rules establish universal, non-negotiable epistemic invariants, evidence validation gates, and linguistic disambiguation standards across all analytical tasks. They prevent hallucinations, premature conclusions, and misattribution errors.

---

## 1. Mandatory Bidirectional Context Audit (Unconditional $N-5$ to $N+5$ Rule)

Deriving analytical conclusions, biographical traits, or psychodynamic claims from an isolated message in a vacuum is strictly prohibited.
- **Antecedent Traceback (Look Back $N-5 \dots N$):**
  1. *Stimulus & Anchor:* Determine what conversational prompt or event triggered the turn.
  2. *Lead-In & Pasted Text:* Check whether preceding turns announced forwarded or pasted third-party content (*"look what he wrote"*).
  3. *Sarcasm & Banter:* Verify whether the statement represents dry humor, mocking mimicry, or inside jokes.
- **Next-Turn Proof Procedure (Look Ahead $N+1 \dots N+5$):**
  1. Inspect interlocutor reception (validation, mockery, or challenge).
  2. *Immediate Rebuttal Invalidation:* If a proposition in turn $N$ is contradicted or rejected in turns $N+1 \dots N+5$ (*"No"*, *"Who said that"*), it is disqualified from being adopted as fact.

### 1.1 Anti-Snippet Ingestion Rule
- Text teasers or bare search match previews from CLI outputs are discovery pointers ONLY, NEVER admissible evidence.
- Quoting or extracting claims directly from search previews without inspecting dialogue context is unconditionally forbidden.

### 1.1a System-1 Extraction & `locate` Span Invariant
- Spans and quotes extracted by System-1 models (e.g., the `locate` primitive in OpenRouter Decisions API or regex matchers) are discovery pointers / candidate spotters ONLY.
- Under NO circumstances may an extracted `locate` span or single-turn snippet be committed directly into `discovered_facts` or cited as validated psychological proof without an unconditional System-2 contextual audit ($N-5 \dots N+5$, sender vs. author verification, conversational tone, and actuation checks).

### 1.2 Bare-Pronoun Attribution Ban & Sender != Author
- **Bare-Pronoun Ban:** When search hits contain bare third-person pronouns (*"He works at"*, *"On ma"*), attributing traits based on conversational inertia is strictly forbidden. The proper noun antecedent in $N-5 \dots N$ must be verified.
- **Sender != Author:** The `sender` field denotes the transport account, NOT intellectual authorship. Forwarded emails, articles, or partner text sent from the subject's account must never be attributed to the subject's inner psychology without antecedent audit.

### 1.3 Zero-Unverified-Quote Invariant
Every verbatim quote and biographical claim cited in profiles or fact snapshots MUST undergo a 3-point contextual audit:
1. *Authorship Origin:* Personally authored vs. pasted/forwarded text.
2. *Conversational Tone:* Sincere disclosure vs. sarcasm, playful exaggeration, or banter.
3. *Interlocutor Reception:* Verified reception in turns $N+1 \dots N+5$.

---

## 2. Medical & Somatic Grounding Gate

- **Ban on Third-Party Hearsay:** Chronic illnesses (diabetes, epilepsy, heart disease) or formal psychiatric diagnoses must NEVER be attributed to a subject based on interlocutor jokes, teasing, or passing remarks.
- **First-Person Self-Declaration:** Attributable only via direct, serious first-person self-declaration by the subject (`sender == subject`).

---

## 3. Third-Party Entity Boundary & Trait Isolation

- When chat participants discuss third parties (coworkers, bosses, acquaintances, suitors, family members), all nicknames, physical traits, occupations, and medical/demographic descriptors belong strictly to the external entity.
- Traits of discussed third parties must never leak onto conversation participants (Subject or Interlocutor).

---

## 4. The Actuation Gate (Modality & Irrealis vs. Realis)

- Verbs of modality, aspirations, job offers, or desires (*"offered"*, *"wanted to"*, *"applied"*, *"planned"*, *"dreamed"*, *"chciał"*) must NEVER be converted into established biographical facts or completed professions.
- An event or title is a biographical fact only if verified by evidence of execution or duration (*"worked there 2 years"*, *"graduated"*).

---

## 5. Span Claim Gate & Timeline Bridging Ban

- Synthesizing continuous multi-year spans (e.g. *"2020–2023"*) from disjointed mentions across distant years is strictly prohibited.
- Verify continuity across intervening years or cite a direct statement of duration. Distinguish between *"known casually since [Year]"* vs. *"actively dated during [Year]"*.

---

## 6. Entity Disambiguation & Cardinality Invariants

1. **Relational Roles vs. NPC Filter:** Distinct relational roles (*"sister"*, *"ex"*, *"boss"*) denote verified bonds. Generic demographic labels (*"indian guy"*, *"policeman"*) are surface descriptors; categorize as Episodic Bystander / NPC.
2. **Cardinality Awareness ($K=1$ vs. $K \ge 2$):** Never assume uniqueness of kinship or role labels without verification. If multiple individuals share a role, distinct distinguishing anchors must be maintained.
3. **No Collective-to-Individual Leakage:** Beliefs or traits of a social unit (family, ethnic group) must never be attributed to an individual without explicit personal affirmation.
4. **Hermetic Chat-Level Scoping:** Role descriptors and third-party entities are strictly scoped to their conversation (`chat_id`). Entities never cross chat boundaries.
5. **Anti-Interlocutor Memory Bias & Rebuttal as Law:** Interlocutor misremembering or speculation has ZERO evidentiary authority. If the subject clarifies or refutes (*"not my ex"*, *"to nie ten"*), the proposition is permanently invalidated.

---

## 7. Evidentiary Pruning & Anti-Eureka Checks

- **Anti-"Eureka!" Check:** A single matching quote is merely a preliminary hypothesis. Check baseline consistency across the archive before concluding.
- **Evidentiary Pruning Rule:** If a life sphere or habit was never mentioned, omit it entirely. NEVER write placeholder disclaimers (*"Brak danych"*, *"No information available"*).
- **Fact-Pinning:** Every factual descriptor, milestone, or occupation in profiles and character tables must be pinned to a message anchor (`[#ID | YYYY-MM-DD]`).

---

## 8. Multi-Party Entity Audit & Watchdog Gate

- **Zero Entity Blindness Invariant:** Interpreting interpersonal dynamics, motives, or relationship patterns in threads mentioning third parties is strictly prohibited until every third-party reference has been sequentially audited and cleared via the Entity Watchdog (`--check-watchdog-gate` exits 0).
- **Prerequisite Enforcement:** Initializing downstream checklists (`checklist.py` and `thread_checklist.py`) is programmatically blocked until the Entity Watchdog scan achieves 100% resolution.

---

## 9. Thread Delta Triage & Anti-Fraud Bypass Invariant

- **Mandatory Subagent Delta Evaluation:** Resolving, closing, or marking pending dialogue threads as redundant without evaluating them through `thread-delta-triage` under the supervision of `thread-supervisor` is strictly prohibited.
- **Evidentiary Legitimacy of Negative Findings:** It is 100% scientifically valid and expected if delta triage determines that remaining threads merely corroborate the established baseline without novel dynamics. A clean run where zero threads require forensic deep dives is entirely legitimate.
- **Investigative Fraud & Evidentiary Tampering Definition:**
  It is classified as **Investigative Fraud** if any agent:
  1. Resolves threads as redundant without exporting the delta manifest and submitting it to `thread-delta-triage`, OR
  2. Bypasses triage by inventing thematic saturation labels on its own, OR
  3. Executes direct database tampering (`sqlite3 chat.db "UPDATE thread_audit_checklist..."`).

---

## 10. Universal Serendipitous Discovery Protocol (Cross-Domain By-Catch)

When any subagent encounters high-salience revelations belonging to a DIFFERENT analytical domain:
1. **Do NOT Discard Out-of-Scope Evidence:** Deep psychological and biographical evidence is rare, distributed, and expensive to rediscover.
2. **Anchor and Capture:** Record the finding with an exact anchored timestamp (`[#ID | YYYY-MM-DD]`) and verbatim quote.
3. **Route to Destination:** Route the finding directly into the evidence repository (`query_chat.py --record-facts-batch`) or forward it to the coordinator so it can be routed to the appropriate life sphere, entity dossier, or report chapter.
