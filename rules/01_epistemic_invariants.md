---
trigger: always_on
---

# Analytical Invariants, Falsification Gates & Disentanglement Protocols

These rules establish non-negotiable epistemic invariants, evidence validation gates, and linguistic disambiguation standards for analyzing longitudinal chat records. They prevent hallucinations, premature conclusions, and misattribution errors.

> [!IMPORTANT]
> **Universal Epistemic Scope:**
> These invariants (bidirectional context verification $N-5 \dots N+5$, pronoun disambiguation, third-party entity boundary protection, irrealis vs. realis, timeline bridging ban) are **universal and non-negotiable**.
> They apply to **EVERY** task involving chat logs—from answering a single ad-hoc factual question to generating a multi-chapter psychological dossier. Factual rigor, anti-hallucination verification, and strict quote anchoring are required across all operational modes.

---

## 1. Mandatory Bidirectional Context Audit (Unconditional $N-5$ to $N+5$ Rule)

The agent is strictly forbidden from deriving analytical conclusions, biographical traits, or psychodynamic claims from an isolated message in a vacuum.
- **Zero-Loophole Scope:** Applies to EVERY cited message or inference, regardless of length (from 1 word to essays) or domain.
- **Antecedent Traceback (Look Back $N-5 \dots N$):**
  1. *Stimulus & Anchor:* Determine what question, event, or conversational prompt triggered the message.
  2. *Lead-In & Pasted Text Detection:* Check whether preceding turns announced forwarded or pasted third-party content (e.g. *"look what he wrote"*, *"answers"*, *"forwarding"*).
  3. *Sarcasm & Banter:* Actively verify whether the statement is genuine or represents dry humor, mocking mimicry, or inside jokes established in prior turns.
- **Next-Turn Proof Procedure (Look Ahead $N+1 \dots N+5$):**
  1. Inspect how the interlocutor received and treated message $N$. Did they validate it, accept it, laugh it off, or correct/rebut it?
  2. *Immediate Rebuttal Invalidation:* If a proposition in message $N$ is immediately contradicted, corrected, or rejected by the interlocutor in turns $N+1 \dots N+5$ (e.g., *"No"*, *"Who said that"*, *"Nope"*), the agent is strictly forbidden from adopting it as an objective fact.

### 1.1 The Anti-Snippet Ingestion Rule (Triage & Search Previews are Pointers, NEVER Evidence)
- **Zero-Trust for CLI Previews:** Text teasers, search previews, or snippet outputs produced by `triage_threads.py` or `query_chat.py` (e.g. `Teaser: ...` or search match previews) are strictly discovery pointers and preliminary screening hypotheses.
- **Absolute Citation Prohibition:** The agent is unconditionally forbidden from quoting or extracting facts, traits, or conclusions directly from CLI teasers or triage summaries without retrieving and inspecting the complete context (`query_chat.py -t <thread_id>` or `query_chat.py --around <msg_id> -n 5`).
- **Audit Verification Invariant:** Every verbatim quote or factual attribution in any report or thesis must correspond to a verified message whose full contextual window was explicitly audited in the conversation trajectory. Citing a triage snippet without prior contextual retrieval is a critical procedural failure (*Heuristic Shortcut Violation*).

### 1.2 The Thread Boundary & Chronological Fallback Protocol (Boundary $N-5 \dots N+5$ Rule)
- **The Boundary Dilemma:** Thread disentanglement in the database partitions conversations into topical clusters to keep semantic vector embeddings clean and untainted. However, when an audited message $N$ sits near the beginning or end of a thread, the thread boundaries truncate the natural conversational timeline.
- **Mandatory Chronological Fallback:**
  1. **Thread Start Boundary:** If fewer than 5 messages precede message $N$ *within the thread*, the agent is strictly forbidden from concluding antecedent research inside that thread. It MUST invoke `python3 project/scripts/query_chat.py --around <msg_id> -n 5` to inspect preceding chronological turns in the raw chat stream ($N-5 \dots N-1$).
  2. **Thread End Boundary:** If fewer than 5 messages follow message $N$ *within the thread*, the agent MUST invoke `python3 project/scripts/query_chat.py --around <msg_id> -n 5` to inspect subsequent chronological turns in the raw chat stream ($N+1 \dots N+5$) to verify the interlocutor's reaction, counter-arguments, or topic transitions.
  3. **Single-Message Threads:** If a thread contains only 1 message, the agent is strictly prohibited from drawing conclusions without auditing BOTH $\pm 5$ chronological messages around it via `query_chat.py --around <msg_id> -n 5`.
- **Vectorization vs. Epistemic Separation Principle:**
  Unrelated chronological messages must **NEVER** be concatenated into database thread objects (`dialogue_text` / `threads` table), as doing so would pollute vector embeddings and cluster unrelated topics together. The chronological inspection is an **epistemic reasoning protocol executed by the agent at query time**, not a persistent mutation of the database threads.

### 1.3 The Bare-Pronoun Search Attribution Ban (Zakaz Atrybucji z Wyników Zaimkowych)
- **The Heuristic Trap:** When a lexical keyword search (`-s`, `-st`) returns a matching message describing a biographical trait, habit, medical condition, hobby, pet, or lifestyle fact starting with or dominated by a bare third-person pronoun (*"He farm mushroom"*, *"She works at"*, *"On ma kota"*, *"Ona studiuje"*), the agent is **STRICTLY PROHIBITED** from attributing that trait to an established character based on conversational inertia.
- **Mandatory Antecedent Audit:** The agent MUST invoke `query_chat.py -f <msg_id> -w 5` or `query_chat.py --around <msg_id> -n 5` to locate the explicit grammatical antecedent (proper noun or role descriptor) in preceding turns ($N-5 \dots N$). Attribution without an audited proper noun antecedent is a critical protocol breach.

---

## 2. The Vocative & Left-Dislocation Protocol (Chat Syntax Disambiguation)

In informal chat transcripts and non-native English (especially ESL influenced by topic-prominent Asian languages like Indonesian), utterances beginning with a proper name followed by a noun phrase:
`"[Name], [descriptor/noun phrase], [clause with pronoun/predicate]"`
MUST NOT be automatically parsed as an apposition (e.g. misinterpreting *"Szymon, the diabetic guy, he is so kind..."* as *"Szymon, who is the diabetic guy"*).

### Mandatory Parsing Rules:
1. **Default Assumption (Vocative + Left-Dislocation):**
   In informal messaging, this syntax represents direct address followed by a topicalized subject:
   $$\text{[Vocative Salutation: Name]} + \text{[Topic NP: Descriptor]} + \text{[Comment: he/she is \dots]}$$
   *(e.g., "Szymon [salutation], [about] the diabetic guy [topic], he is so kind [comment]...")*.
2. **Mandatory Next-Turn Proof:**
   The agent MUST inspect the interlocutor's subsequent turns ($N+1 \dots N+3$). If the named interlocutor refers to the subject in the third person (*"Why do you like him so much?"*, *"Is he okay?"*), treating the descriptor as an attribute of the interlocutor is strictly prohibited.
3. **Punctuation Blindness Warning:**
   Commas in chat logs frequently represent conversational breathing pauses or mobile swipe delimiters, NOT formal syntactic parenthetical clauses.

---

## 3. The Medical & Somatic Grounding Gate (Chronic Illness & Diagnosis Ban)

Chronic illnesses (e.g., Type 1/2 diabetes, epilepsy, autoimmune disorders, heart disease), somatic conditions, or formal psychiatric diagnoses drastically alter a psychological profile.
1. **Absolute Ban on Third-Party Hearsay:**
   An agent MUST NEVER assign a chronic illness or medical condition to the Primary Subject based on ambiguous references, jokes, or passing remarks made by an interlocutor.
2. **First-Person Self-Declaration Requirement:**
   A medical condition can only be attributed to a subject if there is a direct first-person self-declaration by the subject (`sender == subject`).

---

## 4. Third-Party Entity Boundary (Disentanglement of Discussed Third Parties from Conversation Participants)

When participants in a conversation discuss external third parties (e.g. coworkers, bosses, acquaintances, romantic prospects/suitors, family members, or rivals), the agent must actively verify and ensure that traits, attributes, and events belonging to the discussed third party are NEVER accidentally attributed to either of the conversation participants:
1. **Third-Party Attribute Isolation:**
   All nicknames, physical traits, occupations, behaviors, life events, and medical/demographic descriptors (*"the diabetic guy"*, *"the boss who yelled"*, *"the police guy"*, *"the short guy"*) belong strictly to the external entity being discussed.
2. **Participant Attribution Protection & Verification:**
   Before assigning any trait, condition, or narrative to a conversation participant, the agent MUST explicitly verify whether the text is merely discussing or gossiping about an external third party.

---

## 5. The Actuation Gate (Modality & Irrealis vs. Realis)

Verbs of modality, aspirations, job offers, proposals, or desires (*"offered"*, *"wanted to"*, *"insisted on accepting"*, *"applied"*, *"planned"*, *"dreamed"*, *"almost"*, *"chciał"*, *"miał zamiar"*) must **NEVER** be converted into established biographical facts, professions, degrees, or marital statuses.
- A status is an objective biographical fact **only** if supported by verifiable evidence of execution, duration, or ongoing practice (*"worked there for 2 years"*, *"signed the contract"*, *"graduated"*).
- **Resolution Check Protocol:** Whenever an episodic life offer or intention appears (job offer, engagement, planned relocation), the agent MUST audit the aftermath: Did it actually take place, or was it rejected, abandoned, or derailed?

---

## 6. The Span Claim Gate & Timeline Bridging Ban

The agent is strictly prohibited from synthesizing continuous multi-year spans (e.g. *"2020–2023"*) from disjointed mentions across distant years.
- When claiming a relationship duration or start year in a dossier, the agent MUST run targeted queries to verify continuity across intervening years or cite a direct duration quote.
- Distinguish between *"known casually since [Year]"* vs. *"actively dated during [Year]"*.
- Isolated mentions of distant years in later logs are potential retrospective flashbacks (*Outliers*), requiring inspection of that specific anchor message before linking it to an ongoing entity.

---

## 7. Entity Disambiguation Engine (Anti-Conflation Rules)

1. **Principle A: Relational Roles vs. Demographic Attributes (The NPC Filter):**
   - Relational roles (*"sister"*, *"ex"*, *"boss"*) denote verified bonds with the subject.
   - Demographic attributes (*"indian guy"*, *"policeman"*, *"blonde girl"*) are surface descriptors. Never promote an episodic demographic encounter to the Cast of Characters. Categorize as **Episodic Bystander / NPC**.
2. **Principle B: Action/Behavioral Signature & Conversational Inertia:**
   - Within an active relational era, generic labels sharing a romantic/partner behavioral signature inherit the dominant partner via Conversational Inertia. Interactions lacking this signature constitute Lack of Evidentiary Proof.
3. **Principle C: Generalized Role & Descriptor Cardinality ($K=1$ vs. $K \ge 2$):**
   - **Scope:** Applies universally to ANY relational role, kinship label, demographic container, or geographic tag (*"sister"*, *"brother"*, *"ex"*, *"US guy"*, *"Oregon"*, *"doctor"*, *"boss"*, *"roommate"*).
   - **Lazy On-Demand Cardinality Audit:** When the agent first encounters a role or descriptor during investigation, it is strictly forbidden from assuming uniqueness ($K=1$). The agent MUST execute a targeted lexical query (e.g. `query_chat.py -C <chat_id> -s "sister OR sisters OR siblings"`) to establish cardinality within this specific conversation:
     - **$K=1$ (Singleton):** Proven single entity across the entire chat (e.g. father, mother). Direct role mapping is permitted.
     - **$K \ge 2$ (Polysemous / Multi-Entity):** Plural mentions, multiple individuals, or ambiguous references detected (e.g. multiple sisters, two distinct US contacts). A bare role mention (*"my sister"*, *"the US guy"*) CANNOT be mapped to any entity without an audited distinguishing anchor (e.g. `Sister_2_Epilepsy`, `US_Caleb_Ex`, `US_Dustin_ChatFriend`).
   - **One-Time Registry Persistence:** Once audited for a specific `chat_id`, the cardinality status is recorded in `chat_descriptors` or the research scratchpad so it is never re-audited redundantly.
4. **Principle D: Proportional Verification (The Materiality Principle):**
   - *Low-Stakes:* Ambient background activities (*"watching a movie with friend"*). If identity has zero bearing on the psychological insight, do not launch identity searches.
   - *High-Stakes (Mandatory Verification Gate):* Required for biographical milestones, relationship spans, crimes/violence, major financial transactions, and core relational pathology/trauma.
5. **Principle E: Strict Multi-Entity Pronoun & Anaphora Resolution:**
   - In threads where two or more third parties are discussed, personal pronouns (*he*, *she*, *they*, *on*, *ona*) must NEVER be attributed to a character without verifying the antecedent noun/proper name in preceding turns ($N-5 \dots N$).
6. **Principle F: Collective-to-Individual Attribute Leakage Ban:**
   - Political alignments, religious beliefs, or pathologies of a social unit (family, ethnic group, partner circle) must NEVER be transposed onto an individual character without explicit personal affirmation.
7. **Principle G: Hermetic Chat-Level Scoping (`chat_id` Boundary Protection):**
   - Every role descriptor, cardinality mapping, and third-party entity is strictly scoped to its individual conversation (`chat_id` / source file).
   - Descriptors and entities must **NEVER leak across chat boundaries**: *„sister”* or *„ex”* in `ismi.json` has zero relation to *„sister”* or *„ex”* in `silvi.json` or `katia.json`. Cross-chat pollution is a critical architectural violation.
8. **Principle H: Anti-Interlocutor Memory Bias & Speculative Prompt Invalidation:**
   - Interlocutors in longitudinal chats frequently confuse third parties, misremember names, or conflate distinct individuals across distant months.
   - Statements or questions made by the interlocutor (e.g. *"I thought it was the US guy"*, *"Is Caleb your ex?"*, *"Didn't your sister have that job?"*) have **ZERO evidentiary authority**. They are treated strictly as unverified stimuli.
   - The Subject's next-turn reaction ($N+1 \dots N+5$) holds primary authority. If the subject corrects, refutes, or clarifies (*"not my ex"*, *"to nie ten"*, *"different guy"*), the agent is unconditionally prohibited from adopting the interlocutor's conflation.

---

## 8. Thesis Corroboration & Anti-"Eureka!" Sanity Check

- **Prohibition of Premature Closure:** Discovering a single matching quote that aligns with a desired trait or diagnosis is merely a preliminary hypothesis, never a proven conclusion.
- **Baseline Consistency Audit:** The agent must actively search for corroborating evidence across the archive and verify that the thesis does not contradict the subject's overall documented lifestyle and baseline demeanor.

---

## 9. Epistemic Authority & Anti-Bothsidesism

- **Primary Witness vs. External Spectator:** For external events occurring outside the chat (dating encounters, third-party conflicts), the direct participant holds primary epistemic authority.
- **No False Symmetry:** When an external observer makes a speculative claim about a third party and the direct participant refutes it with specific facts, do NOT present this as an unresolved dispute. Mark the observer's claim as an unverified stimulus refuted by the primary witness.

---

## 10. Evidentiary Pruning & Stimulus Rejection Protocol

### 10.1 Absolute Void vs. Stimulus Rejection (Crucial Distinction)
The agent must strictly distinguish between two fundamentally different evidentiary states:
1. **True Non-Existence / Absence of Mention:**
   - If a specific life sphere or lifestyle dimension (e.g. domestic cleaning habits, extreme sports, financial investments) was **never mentioned or introduced anywhere in the chat archive**, the agent MUST completely omit that sub-topic from the report.
   - **Strict Prohibition on Placeholder Disclaimers:** NEVER write placeholder sections or disclaimers such as *"Brak danych na temat sportu"*, *"Temat ten nie był poruszany"*, or *"No information available"*.
2. **Stimulus Exposure vs. Simple Disinterest (Grounding Analytical Inferences):**
   - When an interlocutor introduces a topic, tool, lifestyle activity, political dilemma, or cultural phenomenon, and the primary subject demonstrates disengagement, changes the subject, or reacts with indifference:
   - This should not be automatically dismissed as "no data", but the agent must also avoid forcing far-fetched or over-pathologized interpretations.
   - Often the most realistic, objective analytical finding is simply that the subject is **uninterested in, indifferent to, or unenthusiastic about that particular topic or tool** (e.g. lack of interest in sports, indifference toward new digital tools, disengagement from partisan debates).
   - Where relevant to the life sphere under investigation, record this disinterest or low priority as an empirical finding, rather than omitting the area under the pretext that "nothing was discussed".

---

## 11. Fact-Pinning & Atomic Attribute Grounding

- In dossiers and Cast of Characters tables, every factual descriptor, biographical milestone, occupation, or ideological label MUST be pinned to a verifiable message ID (`[#ID | YYYY-MM-DD]`).
- Synthetic filler, narrative embellishments, or unverified guesswork are strictly forbidden. If an attribute lacks direct primary proof, omit it entirely.

---

## 12. The System-1 Watchdog Entity Verification Loop (Adversarial Double-Check Gate)

To prevent Single-Entity Blindness (stopping entity search after finding the first obvious character in a thread), the pipeline employs an adversarial double-check loop between the Agent (System-2) and the Decision Router (System-1):

1. **Third-Party Radar Hit:** In threads flagged with `mentions_third_party_person = 1`, the Agent examines the dialogue and extracts the initial set of third-party names/entities: $S = \{\text{Name}_1, \dots\}$.
2. **Adversarial Watchdog Query:** System-1 evaluates the thread binarially (`type: noul` via Decisions API):
   - *"Does this dialogue mention, discuss, or quote any external third-party person, suitor, friend, or coworker other than the known entities: S?"*
3. **Loop Convergence:**
   - **Odpowiedź NIE (0):** 100% coverage achieved. Thread investigation completes cleanly.
   - **Odpowiedź TAK (1):** Alert raised: an uncaptured third-party entity is present. The Agent is forced to re-examine the thread turn-by-turn to locate the omitted entity (e.g. spotting `CJ` after initially recording only `Dustin`).
   - If after strict re-examination the Agent confirms no other entity exists (System-1 false positive), the Agent logs the verification and closes the loop without infinite recursion.
