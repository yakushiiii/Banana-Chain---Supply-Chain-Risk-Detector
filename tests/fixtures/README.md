# Test Fixtures

Small, committed test inputs for the Banana Chain backend. They give the Syft integration, the SBOM validator and (in Sprint 2) vulnerability matching known inputs with known expected results.

**Syft version used for every file here: 1.55.0** (`syft version`). Another Syft version may report different components, so if you upgrade, regenerate everything and update the counts below.

## Layout

```
fixtures/
├── README.md
├── sample-syft-cyclonedx-js-app.json      ← Syft output for repos/js-app
├── sample-syft-cyclonedx-py-app.json      ← Syft output for repos/py-app
├── sample-syft-cyclonedx-go-app.json      ← Syft output for repos/go-app
├── sample-syft-cyclonedx-empty-repo.json  ← Syft output for repos/empty-repo
├── malformed-sbom.json                    ← deliberately invalid SBOM
└── repos/                                 ← tiny projects for Syft to scan
    ├── js-app/      package.json, package-lock.json
    ├── py-app/      requirements.txt
    ├── go-app/      go.mod, go.sum, main.go
    └── empty-repo/  .gitkeep only
```

Everything in `repos/` is **input**: each folder stands in for a repo a user would give Banana Chain, so it contains only what a real project would. Generated SBOMs live one level up, outside `repos/`, so they never get scanned as part of a fixture.

## Fixture repos and expected Syft results

| Fixture | Direct dependencies | Known-vulnerable dependency (for Sprint 2) | Expected components |
|---|---|---|---|
| `js-app` | `axios@1.21.1`, `react@19.3.1`, `vue@3.5.45`, `lodash@4.17.20` | `lodash@4.17.20` (CVE-2021-23337, command injection in `_.template`, fixed in 4.17.21) | **54** (53 `library` + 1 `file`) |
| `py-app` | `requests==2.32.5`, `urllib3==2.6.3`, `PyYAML==5.3.1`, `six==1.17.0`, `idna==3.20` | `requests` (CVE-2026-25645, fixed in 2.33.0), `urllib3` (CVE-2026-44431 and 4 more, fixed in 2.7.0+), `PyYAML` (CVE-2020-14343, fixed in 5.4). `six` and `idna` are clean. | **6** (5 `library` + 1 `file`) |
| `go-app` | `github.com/google/uuid v1.6.0`, `github.com/pkg/errors v0.9.1`, `golang.org/x/text v0.3.7` | `golang.org/x/text v0.3.7` (CVE-2022-32149, fixed in 0.3.8) | **5** (4 `library` + 1 `file`) |
| `empty-repo` | none | none | **0** |

**What the counts include.** "Expected components" is the length of the `components` array in Syft's CycloneDX output:

- **`library`** entries are packages. For `js-app` this includes every transitive dependency in `package-lock.json` plus the root package `json-test-app` itself. For `go-app` it includes the main module `go-app` (version `UNKNOWN`) alongside its 3 dependencies. `py-app` has no lockfile, so Syft only reports the 5 listed packages.
- **`file`** entries are the manifest Syft read (`package-lock.json`, `requirements.txt`, `go.mod`). There is one per fixture.

**Empty scans omit `components`.** For `empty-repo`, Syft leaves the `components` key out entirely instead of writing `"components": []`. Code that reads SBOMs must treat a missing `components` key as zero components.

### How each repo was made

**js-app.** `package.json` was written by hand (`lodash` is pinned to an old version on purpose), and `package-lock.json` was generated with npm. Use `npm install --package-lock-only` to regenerate it, which writes the lockfile without creating `node_modules/` or running install scripts. **Never commit `node_modules/`**: Syft scans it and adds dozens of extra components, such as GitHub Actions from the packages' own CI workflows.

**py-app.** `requirements.txt` was written by hand with pinned versions. The comments in it note which packages are vulnerable.

**go-app.** `go.mod` and `go.sum` were generated with the Go toolchain. `main.go` imports all three dependencies so `go mod tidy` keeps them.

**empty-repo.** It's an empty folder with a `.gitkeep` so git tracks it. Syft ignores `.gitkeep`.

## Generated SBOM files

### `sample-syft-cyclonedx-<fixture>.json`

Real Syft output for each fixture, pretty-printed with `jq` (Syft writes compact single-line JSON; `jq .` only changes whitespace). From this folder:

```
for d in js-app py-app go-app empty-repo; do
  syft dir:repos/$d -o cyclonedx-json | jq . > sample-syft-cyclonedx-$d.json
done
```

Fields under `properties` like `syft:package:foundBy` and `syft:location:0:path` are Syft-specific extras, not required CycloneDX fields.

### `malformed-sbom.json`

A copy of `sample-syft-cyclonedx-py-app.json` with the required top-level fields **`bomFormat` and `specVersion` removed**:

```
jq 'del(.bomFormat, .specVersion)' sample-syft-cyclonedx-py-app.json > malformed-sbom.json
```

It should **fail** CycloneDX validation.

## Checking counts

```
for d in js-app py-app go-app empty-repo; do
  echo -n "$d: "; syft dir:repos/$d -o cyclonedx-json 2>/dev/null | jq '.components // [] | length'
done
```

`// []` handles the empty case. If any number changes, update the table above.