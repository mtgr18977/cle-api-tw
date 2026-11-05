# Case-study specifications (milestone M0)

Three public OpenAPI descriptions from different domains, fetched at **pinned commits** with
verified SHA-256 (`python specs/fetch.py`). The specs are not stored in this repository.

| | Stripe | GitHub | Kubernetes |
|---|---|---|---|
| Domain | payments | code hosting / versioning | infrastructure |
| Source | `stripe/openapi` `latest/openapi.spec3.yaml` | `github/rest-api-description` `descriptions/api.github.com/api.github.com.yaml` | `kubernetes/kubernetes` `api/openapi-spec/swagger.json` |
| Commit | `3376b56` | `8726703` | `ca39c8c` |
| Spec version | 2026-10-28.endive (OpenAPI 3.0.0) | 1.1.4 (OpenAPI 3.0.3) | unversioned (Swagger 2.0) |
| Licence (repository) | MIT, (c) 2011- Stripe, Inc. | MIT, (c) 2020 GitHub | Apache-2.0 (LICENSE read at the pinned commit) |
| File size | 7.9 MB | 10.9 MB | 4.3 MB |
| Operations (distinct method+path) | 703 | 1,260 | 1,172 |
| Operations with `summary` | 687 | 1,260 | **0** |
| Operations with `description` | 703 | 1,260 | 1,172 |
| `operationId` style | `PostAccountLinks` | `meta/root`, `security-advisories/list-global-advisories` | `listCoreV1ComponentStatus` |
| Domain-text items (description/summary/title) | 21,988 | 18,433 | 9,384 |
| Unique after deduplication | 9,872 | 7,587 | 3,711 |
| Removed by deduplication | 55.1% | 58.8% | 60.5% |

Measured with `apiterm.extract` and `apiterm.clean.deduplicate` on 2026-11-04.

## Why these three

* They meet the plan's size criterion (hundreds to thousands of operations, all with descriptions) and cover the three
  domains the plan asked for.
* Deduplication removes 55-60% of the texts in every spec, which confirms why plan section 4.2 calls it the most critical step.
* They differ in writing style, which makes the comparison informative: Stripe and GitHub write short imperative
  summaries (*Create an account link*); Kubernetes has no summaries and long descriptions derived from Go doc comments.

## Consequences for the method

* Kubernetes has no `summary`, so the operationId-vs-description verb comparison (RQ4) uses the description's first sentence there.
* Its `operationId`s are camelCase with API-group tokens (`CoreV1`) and GitHub's contain `/` and `-`; both are split by
  `split_identifier`, but group/version tokens will show up as terms in the operationId corpus and need review.
* GitHub has 1,534 `operationId` items against 1,260 distinct method+path operations. I did not investigate the difference
  (probably webhook definitions); check before comparing counts.

## Licences and what is not verified

* MIT and Apache-2.0 permit use and redistribution of the files with the licence notice. This project does not redistribute
  the specs; the report may quote short excerpts and must credit the three sources and keep the notices above.
* The specs' own `info.license` field is set only in GitHub's (MIT); Stripe and Kubernetes rely on the repository licence.
* Not verified: whether text inside the specs also falls under other terms (for example Stripe's website terms linked in
  `termsOfService`). The MIT licence in the repository is the only grant I found.
* Rejected: the APIs.guru directory. Its repo is CC0 for contributed definitions, but it states other definitions are
  "acquired from public sources under the Fair use principle", so per-spec licences would have to be checked one by one.

## Not yet done

* Running the full pipeline on these specs (M1/M2 on real data), and checking POS quality on a review sample.
