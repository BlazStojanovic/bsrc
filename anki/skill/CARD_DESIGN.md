# Card Design

Conventions and rubric the agent applies when authoring Anki cards in
this stack. Linked from `anki/skill/SKILL.md`. Read this whenever you
are about to draft cards.

The orientation is borrowed from SuperMemo's *Twenty rules of
formulating knowledge*; the rules below are the subset that actually
move quality on technical/research material in this user's collection.

---

## 1. Atomicity (hard rule)

**One concept per card.** The answer covers exactly one mechanism,
fact, definition, or contrast. If the answer is "X, plus also Y, plus
also Z", split into three cards.

**The atomicity test:** can a stranger answer this card without
remembering five other cards? If no, decompose.

| ✗ Reject                                                 | ✓ Replace with                                                                  |
|----------------------------------------------------------|---------------------------------------------------------------------------------|
| Q: Describe the Transformer architecture.                 | Three cards: one on attention, one on positional encoding, one on the FFN block. |
| Q: What's the difference between Adam and SGD?            | Two cards. Card A: "What does Adam add over SGD?" Card B: "When does SGD outperform Adam?" |
| Q: List the four components of a TCP segment header.      | Four cards, one per component, plus optionally a fifth Cloze card on the order. |

If the source material is dense (a paper, a chapter), expect to
generate **8–20 atomic cards**, not three sprawling ones. Volume of
*atomic* cards is fine; volume of *bad* cards is not.

---

## 2. No leak in the prompt

The question must not contain the answer or telegraph it. If the front
includes the term being defined, restructure as Cloze.

| ✗ Leaks                                                       | ✓ Doesn't                                                |
|---------------------------------------------------------------|----------------------------------------------------------|
| Q: What does **stride** mean in a non-contiguous tensor?      | Q: What property of a tensor changes when you `.transpose()` it without copying memory? |
| Q: What is a **monad** in Haskell?                            | Cloze: A {{c1::monad}} is a type with `return` and `>>=` operations satisfying… |

---

## 3. Specific, not vague

Reject "explain X", "describe Y", "tell me about Z". Replace with a
specific fact, contrast, or scenario. The card should test recall, not
prompt for an essay.

| ✗ Vague                              | ✓ Specific                                                              |
|--------------------------------------|--------------------------------------------------------------------------|
| Q: Tell me about RAG.                | Q: At inference time, what step does RAG add before the LLM call?        |
| Q: Describe FSRS.                    | Q: In FSRS, what does the *stability* parameter measure?                 |
| Q: How does attention work?          | Q: In scaled dot-product attention, what is the divisor in the softmax?  |

---

## 4. Basic vs Cloze

Default rules:

- **Basic** for prompts that are naturally a question with one answer
  ("what is X?", "when does Y fail?", "what's the runtime of Z?")
- **Cloze** for definitions, formulas, and any fill-in where the
  surrounding context is part of the recall ("In MapReduce, the
  {{c1::shuffle}} step groups by key after Map.")
- **Cloze** for cards that would otherwise leak the answer in the
  prompt (rule 2 above)

You can have multiple cloze deletions in one Cloze note (`{{c1::...}}`,
`{{c2::...}}`); each becomes its own card. This is fine for tightly-
related fill-ins (e.g. all parts of a single formula) but counts as
multiple cards under the atomicity rule — one *concept* per card, not
one cloze per card.

The Anki MCP `add_note` model name is `Basic` or `Cloze`. For Cloze,
the body goes in field `Text`; explanation in `Back Extra`.

---

## 5. Mathematical notation

Anki renders LaTeX through MathJax. Always use MathJax delimiters; do
not use ASCII-only math when the source has real notation.

- **Inline:** `\(...\)`
- **Display:** `\[...\]`

Examples:

```
Q: For a matrix \(A \in \mathbb{R}^{m \times n}\), what shape does \(A^\top A\) have?
A: \(n \times n\).

Q: State Bayes' rule.
A: \[ P(A \mid B) = \frac{P(B \mid A)\, P(A)}{P(B)} \]
```

Conventions:

- Define every symbol on first use within the card. The card is
  self-contained — don't assume notation set up on a different card.
- Use `\mathbb{R}`, `\mathbb{Z}`, `\mathbb{N}` for number sets, not
  Unicode glyphs.
- Use `\top` for transpose, not the `T` superscript.
- For multi-line derivations, prefer `align*` inside `\[...\]`:
  ```
  \[
  \begin{align*}
  L &= \sum_i \ell(y_i, \hat{y}_i) \\
    &= \sum_i (y_i - \hat{y}_i)^2
  \end{align*}
  \]
  ```
- Never embed math in the question that gives away the answer (rule 2
  applies to math too). If the question is "what is the trace of an
  identity matrix?", the answer is `n`, not `\mathrm{tr}(I_n) = n`.

The dump preserves MathJax verbatim — it survives in markdown and
renders cleanly in Anki and on GitHub (with MathJax extensions).

---

## 6. Figures and diagrams

When the source material has a figure that *carries the explanation*
(architecture diagrams, anatomical schematics, geometric proofs),
attach it. When the figure is decorative, don't.

Workflow:

1. Save the image somewhere accessible (e.g. the user's KS vault's
   `raw/papers/<id>/` or a downloaded file path).
2. Call `store_media_file` via the MCP. Pass the file path; it
   validates the MIME type and copies the file into Anki's
   `collection.media/` folder. Returns the canonical filename.
3. Reference the image in the card field as
   `<img src="<filename>" alt="<short description>">`.
4. Always set a meaningful `alt`. The alt text should answer "what
   does this figure show?" in one sentence — useful for accessibility,
   useful when the image fails to load, useful to a future you reading
   the markdown.

After authoring cards with new images, run `ank_sync.sh` — the dump
copies any newly-referenced images from Anki's `collection.media/`
into the cards repo's `media/` folder, so the GitHub-rendered markdown
stays self-contained.

When *not* to attach a figure:

- If a clearer text answer exists. A card asking "what's the order of
  the layer-norm in pre-LN vs post-LN?" doesn't need the diagram from
  the paper; words are enough and they survive on phones.
- If the figure is a screenshot of a code block or a table with text
  content. Re-author as text — searchable, copyable, accessible.

---

## 7. Drafting workflow

Never bulk-insert cards in one shot. The pattern:

1. **Read the source.** If the source is a knowledge-smith note, read
   the note + the underlying paper/article from `<vault>/raw/...`. If
   it's a free-form snippet from the user, ask whether they want
   coverage of the whole snippet or specific concepts.
2. **Pick the deck.** Use `list_decks` to see existing decks. Prefer
   reusing an existing deck (e.g. "ML Basics") over creating a new
   one. Confirm with the user when in doubt.
3. **Draft 8–20 candidates** (depends on source density). Present
   them as a numbered list, each with model (Basic/Cloze), proposed
   tags, the front and back. No insertion yet.
4. **Self-check pass.** Before showing the list, re-read this
   document and apply the checklist (§9). Strike through cards that
   fail any test; you can either drop them or fix them.
5. **Wait for the user.** They approve, edit, or reject per-card.
   Common edits: shorten back, swap Basic↔Cloze, fix math notation.
6. **Insert the approved batch** via `add_notes` (single MCP call,
   atomic up to 100). Pass `tags` per the convention in §8.
7. **Suggest the snapshot.** After successful insertion, suggest
   `bash ~/.claude/skills/anki/scripts/ank_sync.sh --remote`.

Don't combine drafting and inserting in one turn. The review step is
load-bearing — it's where most quality wins.

---

## 8. Tag conventions

Tags double as provenance and as filters for spaced-rep sessions.
Pin these conventions:

- **Source pointer.** When extracting cards from a knowledge-smith
  source, include `ks:<slug>` where `<slug>` matches the note filename
  in the vault (without the year prefix or `.md`). Example:
  `ks:attention-is-all-you-need`.
- **Type pointer.** For arXiv papers, also tag `paper:<arxiv-id>`
  (e.g. `paper:1706.03762`). For non-arXiv articles, omit.
- **Topic.** Lowercase kebab-case nouns. Reuse the
  knowledge-smith vocabulary (`transformer`, `attention`,
  `optimization`, etc.) so KS tags and Anki tags share a namespace.
  See `knowledge-smith/skill/scripts/_ks_common.py:DEFAULT_TAG_VOCAB`.
- **Avoid:** session-specific tags (`agent:test`, dates, "to-review").
  These pollute the deck. If you need a temporary marker, use Anki's
  flag system (red/orange/green) via `card_management:set_flag`,
  not tags.

A typical card on attention from the Transformer paper:

```
tags: ["paper:1706.03762", "ks:attention-is-all-you-need", "transformer", "attention"]
```

---

## 9. Self-check checklist

Before submitting a draft batch, run each card through this list.
Reject or fix any failure.

- [ ] **Atomicity:** does the answer cover exactly one concept?
- [ ] **No leak:** does the prompt avoid containing the answer?
- [ ] **Specific:** is the prompt a recall test, not an essay prompt?
- [ ] **Self-contained:** is every symbol/term defined within this card?
- [ ] **Math notation:** are MathJax delimiters used; symbols introduced?
- [ ] **Figures:** if present, does the image earn its place; is alt
      text meaningful?
- [ ] **Tag provenance:** does the tag set encode source and topic?
- [ ] **Length:** is the answer < ~5 short lines or one short list?

If a card fails any of these, decide: drop, decompose, or rewrite.
Never paper over a vague prompt by tightening just the answer.

---

## 10. Knowledge-smith bridge

When you're acting on a source the user has already captured in their
KS vault:

- The note path is `<vault>/notes/<kind>/<slug>.md`. Read it first.
- The slug becomes the `ks:<slug>` tag.
- For papers, the arxiv id (if any) is in the note frontmatter under
  `arxiv` or derivable from the filename. Tag `paper:<id>`.
- The deck is *not* automatically inferred — propose one based on the
  note's topic and confirm with the user. Default mappings the user
  has used in practice:
  - ML/AI papers → "ML Basics"
  - Systems / OS / networking → "CS Basics"
  - PyTorch internals or library mechanics → "Torch"
  - Fresh topic with no obvious home → ask before creating

After the batch lands, the agent can also flip the source's
`read: true` in the KS frontmatter (if not already), since cards
are evidence the user actually read it.

---

## 11. Examples (full Q/A pairs)

### Good — atomic, specific, no leak

**Basic.** Tagged `transformer`, `attention`, `paper:1706.03762`.

> **Front:** In scaled dot-product attention, what is divided by `\(\sqrt{d_k}\)` and why?
>
> **Back:** The dot product `\(QK^\top\)`. The division keeps the
> softmax inputs at moderate magnitude as `\(d_k\)` grows; without
> it, gradients on the softmax saturate.

### Good — Cloze on a definition that would leak as Basic

> **Text:** A {{c1::pure function}} is one whose output depends only
> on its inputs and whose evaluation produces no side effects.
>
> **Back Extra:** Both conditions must hold; logging is a side
> effect even if the return value is deterministic.

### Bad — multi-concept, paragraph answer

> **Front:** Describe the Transformer architecture.
>
> **Back:** The Transformer is a sequence-to-sequence model… (300
> words follow)

Why bad: violates atomicity, specificity, length budget. Decompose
into 8–12 cards on attention, FFN, residuals, layer norm, positional
encoding, masking, training objective, etc.

### Bad — leak

> **Front:** What is the **stability** parameter in FSRS?
>
> **Back:** The number of days for a card's retrievability to drop
> from 100% to 90%.

Why bad: the term is in the prompt. Recast as Cloze:

> **Text:** In FSRS, the {{c1::stability}} parameter measures how
> long it takes a card's retrievability to drop from 100% to 90%.

---

## What this doc is not

- Not exhaustive. Edge cases (audio, image occlusion, FSRS
  optimization workflows, daily review automation) are out of scope.
- Not a rewrite of SuperMemo's twenty rules. Read the source if you
  want the full theory:
  https://www.supermemo.com/en/blog/twenty-rules-of-formulating-knowledge

When the user asks for a kind of card not covered here (e.g. image
occlusion), ask before improvising — those models bring their own
conventions and aren't part of this document yet.
