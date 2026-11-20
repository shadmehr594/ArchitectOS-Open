# Contributing to ArchitectOS

Thanks for your interest. ArchitectOS is a research-grade platform, and the most useful contributions are the ones that make its behaviour **measurable and reproducible**.

## Development setup

```bash
git clone https://github.com/<your-account>/ArchitectOS.git
cd ArchitectOS
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Optional local services: Ollama (`127.0.0.1:11434`) for chat/vision, ComfyUI (`127.0.0.1:8188`) for rendering. Neither is needed to work on the plan engine or the CAD/BIM exporters.

## Open engineering priorities

These are the areas where help is most valuable right now.

### 1. Fix the hanging and failing pytest suites

The test tree is large and not uniformly green. Two modules are known to hang:

- `tests/test_vision_image_registry_04.py`
- `tests/test_design_continuation_v1.py`

Known pre-existing failures:

- `tests/chat/test_design_approval_render_contract.py` (3 failures)
- `tests/test_precise_edit_route_v1.py` (2 failures)

Useful work: make the hanging suites time-bounded and deterministic, fix the failures, and record a reproducible baseline (command + pass/fail counts) in the PR.

### 2. Replace the denylist "latest render" selector

`_find_latest_project_render_png()` in `core/planning/multifloor_v1/engine/comfyui_bridge.py` chooses the previous render for iterative day/night and material edits. It currently **excludes** a fixed set of filename fragments (`_depth`, `_lineart`, `_comfy_input`, `_comfy_`, `_scaffold`, `_preview`).

That denylist is incomplete: `renders/` also contains `plan_rev_*.png`, `plan_facade_cond.png`, and `source_day_*.png`. A replay of the exact filter over 64 project render directories mis-selected a 2D plan or a source photo in **6** of them.

Preferred fix: a positive selection rule — e.g. an explicit manifest of render outputs, or a `render_*` naming contract enforced at write time — rather than extending the denylist.

### 3. Add GPU VRAM and latency benchmarks

The repository has no measured performance benchmarks. The "16 GB VRAM" figure is a design target from a docstring, not a measurement.

Useful work: a benchmark harness that records, per workflow tier:

- peak VRAM (MiB)
- wall-clock latency per stage (conditioning, sampling, decode)
- output resolution and file size
- GPU model and driver version

Run it on at least two hardware configurations if possible, and commit the harness plus raw results — not just a summary table.

### 4. UI improvements

The served UI is `ui/templates/index.html` plus the `ui/routes/` blueprints. Areas that would benefit from work:

- accessibility (keyboard navigation, contrast, focus states)
- Persian RTL layout consistency across panels
- clearer progress and failure states for long render jobs
- replacing inline styles with a maintainable stylesheet

Please include before/after screenshots in UI pull requests.

## Engineering expectations

This project follows a strict evidence discipline, and contributions are reviewed the same way:

1. **Root cause or stop.** Avoid symptom patches, prompt hacks, and hardcoded exceptions.
2. **State the evidence class.** Source inspection, unit instantiation, and live execution are different levels of proof. A passing syntax check is not a passing runtime check.
3. **Do not weaken a gate to make a test pass.** If a check is wrong, explain why with evidence.
4. **Keep the engine boundary intact.** `engine/` is the 2.5D render pipeline; `core/planning/multifloor_v1/engine/` is the plan engine. Do not merge or copy one over the other.
5. **No personal data in commits.** Project folders, render caches, conversation memory, and regulatory PDFs are git-ignored. Do not force-add them.

## Pull request checklist

- [ ] The change is scoped to one concern.
- [ ] Tests were run and the exact command + result is in the description.
- [ ] New behaviour has a test that fails without the change.
- [ ] No secrets, absolute personal paths, model weights, or regulatory PDFs are included.
- [ ] If rendering changed, at least one before/after image is attached and the GPU model is stated.

## Reporting bugs

Please include:

- the exact command or UI action,
- the relevant log excerpt (not a paraphrase),
- the version (`v79.0` or commit SHA),
- whether ComfyUI and Ollama were running,
- and, for rendering issues, the input plan/model and the output image.

## License

By contributing, you agree that your contribution is licensed under the GNU Affero General Public License v3.0.
