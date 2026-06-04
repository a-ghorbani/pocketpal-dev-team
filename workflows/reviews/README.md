# Review Artifacts

Durable code-review artifacts live here.

Use one folder per review target and round:

```text
workflows/reviews/
  PR-705/
    round-1/
      review-map.md
      architect.md
      qa.md
      security.md
      performance.md
      mobile.md
      data.md
      ux.md
      local-invariants.md
      verification.md
      final.md
```

These files are review process records. Do not store secrets, `.env` contents,
build artifacts, screenshots, or large logs here. Summarize verification output
and link to artifact locations when needed.

When a review returns `REQUEST_CHANGES`, the top-level delivery session normalizes mandatory findings into the related story folder:

```text
workflows/stories/<TASK-ID>/review-feedback-round-<N>.md
```

That feedback file is the PR-fix pipeline input. The original `final.md` remains the independent review record.
