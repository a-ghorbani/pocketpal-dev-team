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
