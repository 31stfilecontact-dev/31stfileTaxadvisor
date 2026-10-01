# Authority seed files

The section and circular files are intentionally empty until the official
source data is supplied. Do not add guessed section correspondences or legal
authority records.

`scripts/seed.py` accepts JSON arrays with these fields:

- `sections_old.json` / `sections_new.json`: `id` (optional), `chapter`,
  `number`, `title`, `text`, and `parent_id` (optional).
- `section_map.json`: official `relation`, `old_section_number` and/or
  `new_section_number` (or explicit section IDs), `notes`, and `source_ref`.
  `relation` must be explicitly supplied as one of `one_to_one`,
  `one_to_many`, `many_to_one`, `merged`, `omitted`, or `new`.
- `circulars_seed.json`: `id`, `act_year`, `type`, `number`, `date`,
  `section_number`, `issue_id`, `summary`, `effect`, `status`,
  `applicable_from`, and `source_url`.

`issues_seed.json` contains only the two user-requested issue labels. Their
section links are resolved from the imported 1961 section list and official
section-map file at seed time. Their initial Kanoon keywords are the exact
user-provided labels, not model-generated expansions.