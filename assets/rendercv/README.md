# Editing and generating the CV

- Edit education, experience, awards, skills, and languages in `_data/cv.yml`.
- Edit publications in `_bibliography/papers.bib`. Academic entries such as `@article` and `@inproceedings` are copied into the CV's `Publications` section automatically. Entries whose `additional_info` is `Preprint` are copied into `Preprints`. Do not edit the generated publication sections in `_data/cv.yml` by hand.

Install [Pixi](https://pixi.sh/) once. Pixi creates and updates the CV environment automatically, so no virtual environment or manual `pip install` is needed.

After editing, synchronize BibTeX without rendering:

```bash
pixi run sync-cv
```

Synchronize and regenerate the PDF:

```bash
pixi run render-cv
```

Render the PDF and validate its contents and links:

```bash
pixi run check-cv
```

The PDF is written to `assets/rendercv/rendercv_output/Haruto_Suzuki_CV.pdf`. Dependency versions are recorded in `pixi.lock`. Pushing a relevant CV, BibTeX, Pixi, or rendering-script change to GitHub runs `pixi run check-cv` automatically.
