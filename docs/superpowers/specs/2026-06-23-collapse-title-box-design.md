# Collapse-to-Bird-Badge Button

**Date:** 2026-06-23
**Status:** Approved (pending spec review)
**Topic:** Add a collapse control to the title box on the Halifax Bird Parking Nests map.

## Goal

Let users collapse the title box (top-left panel) down to just the 🐦 emoji, freeing screen space for the map. Clicking the emoji restores the full title box.

## Context

- Source of truth for the map UI is `HTML_TEMPLATE` in `fetch_bird_nests.py`.
- The title box (`.title-box`) is an absolutely-positioned panel containing four elements: `<h1>`, a description `<p>`, a last-updated `<p class="updated">`, and a disclaimer `<p class="disclaimer">`.
- Generated `bird_nests.html` is gitignored; never edited directly.
- Tests live in `tests/test_fetch_bird_nests.py` and assert on the string output of `generate_html(...)`.

## User Experience

1. **Default state on load:** expanded — full title box visible (so the last-refresh date is immediately readable).
2. **Collapse:** User clicks a small ▾ button in the title box. The box collapses to just the 🐦 emoji, anchored top-left.
3. **Expand:** User clicks the 🐦 emoji. Full title box returns.
4. **State persistence:** None. Resets to expanded on every load. Matches the existing `no-cache` regeneration philosophy and keeps v1 simple.
5. **Accessibility:** Collapse button and bird badge are keyboard-activatable (Enter/Space) with `aria-label`s. Badge has `role="button"` and `tabindex="0"`.

## Implementation (Approach A: single container + CSS class toggle)

### DOM changes (inside `.title-box` in `HTML_TEMPLATE`)

```html
<div class="title-box" id="titleBox">
  <span class="bird-badge" role="button" tabindex="0" aria-label="Show title">🐦</span>
  <h1>Halifax Bird Map 🐦 <button class="collapse-btn" type="button" aria-label="Collapse title">▾</button></h1>
  <p>Nests show available vehicles at this parking zone. Empty nests are valid parking — they just have no vehicles right now.</p>
  <p class="updated">Last updated: {generated_at}</p>
  <p class="disclaimer">Not affiliated with Bird Canada. <a href="https://github.com/wlonkly/hfx-bird-map">Source</a></p>
</div>
```

Notes:
- `bird-badge` is the first child so it anchors top-left when the box is collapsed.
- The h1 retains its existing emoji (unchanged test expectations); `collapse-btn` is appended inside the h1 and floated right.
- An `id="titleBox"` is added so the toggle JS can grab it without ambiguity.

### CSS additions (inside the existing `<style>` block)

```css
.bird-badge {
  display: none;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
}
.collapse-btn {
  float: right;
  margin-left: 8px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  color: #666;
}
.title-box.collapsed {
  padding: 6px 8px;
}
.title-box.collapsed h1,
.title-box.collapsed p,
.title-box.collapsed .updated,
.title-box.collapsed .disclaimer,
.title-box.collapsed .collapse-btn {
  display: none;
}
.title-box.collapsed .bird-badge {
  display: inline;
}
```

### JS additions (inside the existing `<script>` block, after map setup)

```js
var titleBox = document.getElementById('titleBox');
var collapseBtn = titleBox.querySelector('.collapse-btn');
var birdBadge = titleBox.querySelector('.bird-badge');

function collapseTitle() { titleBox.classList.add('collapsed'); }
function expandTitle() { titleBox.classList.remove('collapsed'); }

collapseBtn.addEventListener('click', collapseTitle);
birdBadge.addEventListener('click', expandTitle);
birdBadge.addEventListener('keydown', function (e) {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); expandTitle(); }
});
```

## Testing

New test in `TestGenerateHtml`:

- `test_contains_collapse_controls` — asserts the generated HTML contains:
  - `bird-badge` class
  - `collapse-btn` class
  - `classList.add('collapsed')` and `classList.remove('collapsed')` toggle JS
  - `aria-label="Collapse title"` and `aria-label="Show title"`

Existing `test_contains_title_box` remains green: the h1 text (`Halifax Bird Map`), disclaimer text, source URL, and `{generated_at}` timestamp are all still present in the template — only wrapped differently.

No data-pipeline Python changes, so `TestMergeStationData`, `TestStationsToGeoJSON`, etc. are untouched.

## Scope & Files Touched

1. `fetch_bird_nests.py` — `HTML_TEMPLATE` only (CSS block, DOM, JS block). No Python logic changes.
2. `tests/test_fetch_bird_nests.py` — one new test method in `TestGenerateHtml`.
3. `bird_nests.html` — regenerated only to visually confirm the result (gitignored, never committed).

## Out of Scope (v1)

- `localStorage` persistence of collapse state.
- Animated transitions on collapse/expand.
- Collapsing the legend (bottom-right) — separate feature.
- Touch-specific behavior beyond the existing click handlers.

## Risks

- **Low:** CSS `.collapsed` selector specificity is plain class-level; no conflicts expected with existing `.title-box` rules.
- **Low:** `bird-badge` and the h1's emoji are visually similar; intentional — the badge is the collapsed-state affordance.
- **None:** No Python data logic touched; no network or schema changes.
