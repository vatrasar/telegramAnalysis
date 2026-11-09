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
3. **Principle C: Cardinality State Machine ($K=1$ vs. $K \ge 2$):**
   - If multiple individuals hold the same role simultaneously (e.g., multiple sisters), a bare mention (*"my sister"*) CANNOT be mapped to an individual without a distinguishing anchor. Route to a collective container (e.g. `Sister_Unresolved`).
4. **Principle D: Proportional Verification (The Materiality Principle):**
   - *Low-Stakes:* Ambient background activities (*"watching a movie with friend"*). If identity has zero bearing on the psychological insight, do not launch identity searches.
   - *High-Stakes (Mandatory Verification Gate):* Required for biographical milestones, relationship spans, crimes/violence, major financial transactions, and core relational pathology/trauma.
5. **Principle E: Strict Multi-Entity Pronoun & Anaphora Resolution:**
   - In threads where two or more third parties are discussed, personal pronouns (*he*, *she*, *they*, *on*, *ona*) must NEVER be attributed to a character without verifying the antecedent noun/proper name in preceding turns ($N-5 \dots N$).
6. **Principle F: Collective-to-Individual Attribute Leakage Ban:**
   - Political alignments, religious beliefs, or pathologies of a social unit (family, ethnic group, partner circle) must NEVER be transposed onto an individual character without explicit personal affirmation.

---

## 8. Thesis Corroboration & Anti-"Eureka!" Sanity Check

- **Prohibition of Premature Closure:** Discovering a single matching quote that aligns with a desired trait or diagnosis is merely a preliminary hypothesis, never a proven conclusion.
- **Baseline Consistency Audit:** The agent must actively search for corroborating evidence across the archive and verify that the thesis does not contradict the subject's overall documented lifestyle and baseline demeanor.

---

## 9. Epistemic Authority & Anti-Bothsidesism

- **Primary Witness vs. External Spectator:** For external events occurring outside the chat (dating encounters, third-party conflicts), the direct participant holds primary epistemic authority.
- **No False Symmetry:** When an external observer makes a speculative claim about a third party and the direct participant refutes it with specific facts, do NOT present this as an unresolved dispute. Mark the observer's claim as an unverified stimulus refuted by the primary witness.

---

## 10. Evidentiary Pruning Rule & Ban on Placeholder Boilerplate

- If a life sphere, lifestyle habit, or sub-topic (e.g. sports, pets, domestic cleaning habits, vacation style) was never mentioned in the chat archive, the agent MUST completely omit that topic from the report.
- **Strict Prohibition on Placeholder Disclaimers:** NEVER write placeholder sections or disclaimers such as *"Brak danych na temat sportu"*, *"Temat ten nie był poruszany"*, or *"No information available"*.

---

## 11. Fact-Pinning & Atomic Attribute Grounding

- In dossiers and Cast of Characters tables, every factual descriptor, biographical milestone, occupation, or ideological label MUST be pinned to a verifiable message ID (`[#ID | YYYY-MM-DD]`).
- Synthetic filler, narrative embellishments, or unverified guesswork are strictly forbidden. If an attribute lacks direct primary proof, omit it entirely.
