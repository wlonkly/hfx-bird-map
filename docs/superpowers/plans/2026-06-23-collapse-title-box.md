# Collapse-to-Bird-Badge Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapse control to the title box on the Halifax Bird Parking Nests map so users can collapse it down to just the 🐦 emoji, freeing screen space for the map. Clicking the emoji restores the full title box.

**Architecture:** Single-container approach (Approach A from the design spec). A `bird-badge` span and a `collapse-btn` button are added inside the existing `.title-box`. Toggling a `.collapsed` CSS class on the box hides the title content and reveals the badge. A few lines of vanilla JS wire up click + keyboard handlers. No `localStorage`; state resets on reload.

**Tech Stack:** Vanilla HTML/CSS/JS embedded in a Python triple-quoted string template (`HTML_TEMPLATE` in `fetch_bird_nests.py`). Tests are pytest assertions on the string output of `generate_html(...)`. The template uses doubled braces (`{{` / `}}`) to escape literal `{`/`}` because it is consumed by `str.format`.

**Spec:** `docs/superpowers/specs/2026-06-23-collapse-title-box-design.md`

---

## File Structure

Only two files are touched (plus the gitignored generated HTML for visual confirmation):

- **Modify:** `fetch_bird_nests.py` — the `HTML_TEMPLATE` string only (CSS block, DOM, JS block). No Python data-pipeline logic changes.
- **Modify:** `tests/test_fetch_bird_nests.py` — one new test method added to the existing `TestGenerateHtml` class.
- **Regenerate (do not commit):** `bird_nests.html` — produced by running `python fetch_bird_nests.py`; gitignored.

---

### Task 1: Add the failing test for collapse controls

**Files:**
- Modify: `tests/test_fetch_bird_nests.py` (append a new method to the `TestGenerateHtml` class, after `test_contains_title_box` at line 380)

- [ ] **Step 1: Write the failing test**

Append this method inside the `TestGenerateHtml` class (after the existing `test_contains_title_box` method that ends at line 380):

```python
    def test_contains_collapse_controls(self):
        html = generate_html({"type": "FeatureCollection", "features": []}, TS)
        # Collapsed-state badge (click to expand)
        assert "bird-badge" in html
        assert 'aria-label="Show title"' in html
        # Collapse button in the header (click to collapse)
        assert "collapse-btn" in html
        assert 'aria-label="Collapse title"' in html
        # Toggle JS
        assert "classList.add('collapsed')" in html
        assert "classList.remove('collapsed')" in html
        # Collapsed-state CSS rule that reveals the badge
        assert ".title-box.collapsed .bird-badge" in html
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_fetch_bird_nests.py::TestGenerateHtml::test_contains_collapse_controls -v`
Expected: FAIL with `AssertionError: assert 'bird-badge' in '...'` (or `collapse-btn`), because the template has not been edited yet.

---

### Task 2: Add the collapse controls to HTML_TEMPLATE

**Files:**
- Modify: `fetch_bird_nests.py` — three edits inside `HTML_TEMPLATE`:
  1. CSS additions (inside the `<style>` block, after the `.title-box .disclaimer` rule around line 254)
  2. DOM additions (inside the `.title-box` div, lines 278–283)
  3. JS additions (inside the `<script>` block, after the `map.on('load', ...)` block closes at line 467, before `</script>`)

- [ ] **Step 1: Add the CSS rules**

In `fetch_bird_nests.py`, locate this block inside the `<style>` element:

```
  .title-box .disclaimer {{ color: #888; font-size: 11px; margin-top: 6px; }}
```

Insert these rules immediately after it:

```
  .title-box .disclaimer {{ color: #888; font-size: 11px; margin-top: 6px; }}
  .bird-badge {{
    display: none; cursor: pointer;
    font-size: 20px; line-height: 1;
  }}
  .collapse-btn {{
    float: right; margin-left: 8px;
    padding: 0; border: none; background: transparent;
    cursor: pointer; font-size: 14px; line-height: 1; color: #666;
  }}
  .title-box.collapsed {{ padding: 6px 8px; }}
  .title-box.collapsed h1,
  .title-box.collapsed p,
  .title-box.collapsed .updated,
  .title-box.collapsed .disclaimer,
  .title-box.collapsed .collapse-btn {{ display: none; }}
  .title-box.collapsed .bird-badge {{ display: inline; }}
```

Note: braces are doubled (`{{` / `}}`) because `HTML_TEMPLATE` is a `str.format` template.

- [ ] **Step 2: Add the DOM elements**

In `fetch_bird_nests.py`, locate the existing `.title-box` div:

```html
<div class="title-box">
  <h1>Halifax Bird Map 🐦</h1>
  <p>Nests show available vehicles at this parking zone. Empty nests are valid parking — they just have no vehicles right now.</p>
  <p class="updated">Last updated: {generated_at}</p>
  <p class="disclaimer">Not affiliated with Bird Canada. <a href="https://github.com/wlonkly/hfx-bird-map">Source</a></p>
</div>
```

Replace it with:

```html
<div class="title-box" id="titleBox">
  <span class="bird-badge" role="button" tabindex="0" aria-label="Show title">🐦</span>
  <h1>Halifax Bird Map 🐦 <button class="collapse-btn" type="button" aria-label="Collapse title">▾</button></h1>
  <p>Nests show available vehicles at this parking zone. Empty nests are valid parking — they just have no vehicles right now.</p>
  <p class="updated">Last updated: {generated_at}</p>
  <p class="disclaimer">Not affiliated with Bird Canada. <a href="https://github.com/wlonkly/hfx-bird-map">Source</a></p>
</div>
```

Keep the h1 text and emoji exactly as-is (the existing `test_contains_title_box` asserts on `"Halifax Bird Map"` and `"Empty nests are valid parking"` and the source URL — all must remain).

- [ ] **Step 3: Add the toggle JS**

In `fetch_bird_nests.py`, locate the close of the `map.on('load', function () {{ ... }});` block. It ends with:

```js
    map.fitBounds(bounds, {{ padding: 60, maxZoom: 16 }});
  }});
</script>
```

Insert the toggle code between `}});` and `</script>`, so it reads:

```js
    map.fitBounds(bounds, {{ padding: 60, maxZoom: 16 }});
  }});

  var titleBox = document.getElementById('titleBox');
  var collapseBtn = titleBox.querySelector('.collapse-btn');
  var birdBadge = titleBox.querySelector('.bird-badge');
  function collapseTitle() {{ titleBox.classList.add('collapsed'); }}
  function expandTitle() {{ titleBox.classList.remove('collapsed'); }}
  collapseBtn.addEventListener('click', collapseTitle);
  birdBadge.addEventListener('click', expandTitle);
  birdBadge.addEventListener('keydown', function (e) {{
    if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); expandTitle(); }}
  }});
</script>
```

Again, all `{`/`}` are doubled for the `str.format` template.

- [ ] **Step 4: Run the new test to verify it passes**

Run: `pytest tests/test_fetch_bird_nests.py::TestGenerateHtml::test_contains_collapse_controls -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite to verify no regressions**

Run: `pytest -v`
Expected: all tests PASS, including the existing `test_contains_title_box`.

- [ ] **Step 6: Regenerate the map for a visual sanity check**

Run: `python fetch_bird_nests.py`
Expected: prints `Fetching GBFS feed discovery...` and ends with `Wrote map to bird_nests.html`. Open `bird_nests.html` in a browser and confirm:
- Title box loads expanded (full panel visible, including "Last updated").
- A small ▾ button sits at the right of the `Halifax Bird Map 🐦` header.
- Clicking ▾ collapses the box to just the 🐦 emoji at top-left.
- Clicking the 🐦 emoji restores the full box.
- Tab/Enter/Space on the emoji also expands (keyboard a11y).

Do not commit `bird_nests.html` (it is gitignored).

- [ ] **Step 7: Commit**

```bash
git add fetch_bird_nests.py tests/test_fetch_bird_nests.py
git commit -m "feat: collapse title box to bird emoji badge

Add a ▾ button in the title box header and a 🐦 badge. Clicking ▾
collapses the panel to just the emoji; clicking the emoji restores it.
Default state on load is expanded so the last-refresh date stays visible.
No localStorage; state resets on reload."
```

---

## Self-Review

**Spec coverage:**
- DOM `bird-badge` + `collapse-btn` + `id="titleBox"` → Task 2 Step 2 ✓
- CSS rules (default-hidden badge, float-right button, `.collapsed` hide/show) → Task 2 Step 1 ✓
- JS click handlers + keyboard a11y (Enter/Space) → Task 2 Step 3 ✓
- Default expanded state → no `.collapsed` class in template initially ✓
- No `localStorage` → not added (by omission, matches spec) ✓
- Test `test_contains_collapse_controls` asserting badge, button, aria-labels, toggle JS, collapsed CSS → Task 1 Step 1 ✓
- Existing `test_contains_title_box` stays green → Task 2 Step 5 verifies ✓
- Only `fetch_bird_nests.py` + test file touched; `bird_nests.html` regenerated but not committed → File Structure section ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases". All steps show exact code.

**Type/name consistency:** `bird-badge`, `collapse-btn`, `titleBox`, `collapsed`, `collapseTitle`, `expandTitle`, aria-labels `"Show title"` / `"Collapse title"` — identical across CSS, DOM, JS, and test assertions. ✓

No issues found.
