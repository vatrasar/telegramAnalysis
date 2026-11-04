# Analysis Agent Operating Rules: Large-Scale Chat Ingestion

## 1. Architectural Boundary: Agent Package vs. Workspace State
- The `project/` directory is strictly the **Agent Package** (skills, rules, scripts, and static templates).
- **NEVER create runtime databases, user state, or configuration files inside `project/`.**
- All runtime user configuration lives above `project/` in `config/` (e.g. `config/embeddings_config.json`).
- All analytical databases and runtime data live above `project/` (e.g. `chat.db` or `data/chat.db`).

---

## 2. Pre-Flight Configuration & User Handshake (Mandatory Startup)
Before performing any ingestion, indexing, or chat analysis, the agent **MUST** run the pre-flight configuration script:
```bash
python3 project/scripts/setup_config.py
```

### Action Protocols Based on Pre-Flight Result:
1. **If Exit Code 2 (`ACTION_REQUIRED`):**
   - The config file was either just generated or still contains placeholder credentials (`YOUR_OPENROUTER_API_KEY_HERE`).
   - **DO NOT proceed.** Pause execution and ask the user directly:
     > *"I have initialized your configuration file at `config/embeddings_config.json` (outside the agent package and protected by `.gitignore`). Please open it, enter your OpenRouter API key and preferred embedding model, and let me know when you're done so I can proceed."*
   - Wait for user confirmation before calling any indexing scripts.
2. **If Exit Code 3, 4, 5, or 6 (`ERROR`):**
   - **DO NOT guess or proceed silently.** Report the exact diagnostic error directly to the user:
     - **Code 3 (HTTP 401):** *"Authentication failed (HTTP 401). Your OpenRouter API key in `config/embeddings_config.json` appears to be invalid or expired. Please check your key at openrouter.ai/keys."*
     - **Code 4 (HTTP 402):** *"Insufficient credits (HTTP 402). Your OpenRouter account balance is empty or your key's spending limit has been reached. Please check openrouter.ai/credits."*
     - **Code 5 (HTTP 404):** *"Model not found (HTTP 404). The embedding model specified in `config/embeddings_config.json` does not exist on OpenRouter."*
     - **Code 6 (Network Error):** *"Network failure. Unable to reach `openrouter.ai`. Please check internet/proxy connectivity."*
   - Ask the user to resolve the specific issue and let you know when ready.
3. **If Exit Code 0 (`SUCCESS`):**
   - Credentials and connectivity verified. Proceed immediately to Step 3.

---

## 3. Context Protection & Database Mandate
- **NEVER load raw chat logs (>1,000 messages) directly into the model context.**
- When handed a chat export (e.g. in `rozmowy/` or as a JSON file):
  1. Verify if `chat.db` (or `data/chat.db`) exists in workspace root.
  2. If not, build it immediately: `python3 project/scripts/db_builder.py <path_to_json> -o chat.db`.
  3. All data exploration and quote retrieval must be performed through `project/scripts/query_chat.py` or direct SQL queries against `chat.db`.

---

## 4. Multi-Stage Investigative Protocol (Profiler Mindset)

### Stage 1: Macro-Reconnaissance & Anomaly Detection
Before reading individual quotes or forming premature psychological conclusions:
1. Run `query_chat.py --stats` to establish communication volume, balance of participation, and message verbosity.
2. Run `query_chat.py --gaps` to examine silences $>24$h and identify who maintains the relationship vs. who withdraws.
3. Run `query_chat.py --timeline` to detect phases of closeness, conflict, or emotional detachment across years.
4. Run `query_chat.py --burning-days` to isolate statistically anomalous peak intensity days ($\mu + 2\sigma$).
5. Run `query_chat.py --intensive-threads` to retrieve substantive dialogue threads ranked by volume, eliminating small-talk noise.

### Stage 2: Biographical Dossier & Cast of Characters
1. **Origin Story Reconstruction:** Search for autobiographical fragments across school, university, past relationships, career pivots, and formative crucibles.
2. **Relational Constellation:** Identify all key third parties (family, friends, romantic prospects/exes, authorities, rivals), their roles, recurring themes, and the subject's emotional stance and boundary setting toward them.

### Stage 3: Intensive Discussions & Life Spheres Audit
1. Audit all intensive discussions using the **3-Point Thread Inspection Method** (Trigger $\to$ Core Stances $\to$ Resolution/Exit).
2. Systematically examine the 6 core life spheres:
   - **A:** Social circle & friends (loyalty, door-slams, envy vs. pride).
   - **B:** Work, ambition & stance toward authorities (rebellion vs. perfectionist approval-seeking).
   - **C:** Socio-political worldview & debate conduct (empirical logic vs. emotional moralism).
   - **D:** Family roots & parental imprints (discipline, parentification, commitment trauma).
   - **E:** Romantic attachment & deactivating strategies.
   - **F:** Passions, aesthetic sensibilities & solitude.

### Stage 4: Forensic Dimensions & Behavioral MBTI
1. **Behavioral MBTI:** Classify strictly based on communicative habits (bursts/live thinking vs. delayed synthesis; concrete details vs. abstract modeling; logic vs. relational harmony; closure vs. flexibility).
2. **Forensic Probing:** Check for conspicuous absences, linguistic code-switching, temporal evolution, declared vs. actual fractures, accountability (genuine apologies vs. non-apologies), boundary testing, and late-night prefrontal fatigue ("Nighttime Truth" 23:00–04:00).

---

## 5. Disentanglement & Contextual Integrity
- Always respect the **thread anchor**: When analyzing a quote, check whether it was an answer to an explicit question or an unquoted continuation of a thought burst.
- **Never cite an isolated message in a vacuum:** Always inspect surrounding context using `query_chat.py --thread <thread_id>` or `--from-msg <id> -w 5`. Verify the stimulus, the reaction, and the aftermath.

---

## 6. Modular Drafting & Assembly Protocol
- To prevent context saturation, degradation, and file editing corruptions during deep analyses:
  1. Draft chapters in separate modular section files (e.g. `reports/<subject>_sections/01_dossier.md`, `02_cast.md`).
  2. Assemble the final unified report using the automated assembly script:
     ```bash
     python3 project/scripts/assemble_report.py --sections-dir reports/<subject>_sections/ -o reports/<subject>_profile.md
     ```
  3. The script verifies code fence closure and automatically generates the Table of Contents.

---

## 7. Report Standards & Delivery
- Follow the **Thesis-First Framework** defined in the personality profiling guidelines:
  - Every chapter must contain:
    - `### 📌 The Core Thesis` (2–3 bold, definitive sentences stating the insight upfront)
    - `### 🧠 In-Depth Psychological Analysis` (explicit forensic mechanisms)
    - `### 🔍 Verbatim Evidence & Case Studies` (verbatim quotes with exact `YYYY-MM-DD` dates in blockquotes)
    - `### 💡 Key Takeaway` (concise operational takeaway)
  - Mandatory Biographical Dossier & Life Timeline.
  - Mandatory Cast of Characters table and commentary.
  - Mandatory Attachment Style classification (Secure, Anxious-Preoccupied, Dismissive-Avoidant, Fearful-Avoidant).
  - Mandatory Behavioral MBTI classification.
  - Mandatory **Operational User Manual** (Blind spots, triggers, unspoken need, communication protocols, statement reliability).
  - Conclude with the standard **Summary Matrix** table.
- Benchmark quality against reference profiles in `przykłądoweAnalizy/`.

---

## 8. Output Language Standard (Default Polish Delivery)
- **Mandatory Default Output Language:** All generated personality profile reports (including intermediate modular sections) **MUST be written in Polish by default**, matching the user's primary analytical language and benchmark examples in `przykłądoweAnalizy/`.
- **On-Demand Translation:** Only if the user explicitly requests another language (e.g., *"translate this profile to English"* or *"produce in English"*) should the agent output the report in that language.
- **Specification Integrity:** All rules, skills, prompts, and technical scripts inside `project/` must remain in English.
