# Public release and discovery handover

## Release contract

The private working repository is the source of truth. A public repository is
a reviewed projection, not a second place to edit history independently.

Release completion means all of these are true:

1. `warrior-scan --fsck` records no unclassified work-loss blocker.
2. `warrior-history public-plan` pins one source branch and a public noreply
   identity.
3. `build-public-candidate` exports only that branch and passes `fsck` plus its
   value-withholding public audit.
4. The candidate's current tree passes the deterministic test suite.
5. A normal, non-force push updates only the explicitly approved destination;
   its branch object is verified from the server afterwards.

The source repository, private refs, backup branches, unreachable commits, and
private replacement rules remain local and preserved.

## Discovery goals

### 1. Complete history-doctor coverage

Add candidate-only commit selection/squash operations one vertical slice at a
time. Every operation must pin source state, preserve the failed candidate,
verify source immutability, and prove the requested semantic outcome—not merely
accept a successful exit code.

### 2. Make secret policy configurable

Add a versioned public policy format for allowed placeholder identities,
private-host patterns, binary scanning bounds, and optional locally installed
scanners. Policy files must contain classifications, never secret values.

### 3. Close the project-import journey

Turn a `warrior-project` dossier and checkpoint closure plan into explicit,
reviewable candidate operations for repositories and package registries.
Keep discovery, preservation, forge creation, and package publication as
separate authority steps.

### 4. Prove every agent adapter

Run the same fixture journey through each supported harness: scan, explain a
finding, build a candidate plan, stop at its authority boundary, and report
verification evidence. Agent tests are manual harness acceptance checks;
Warrior's automated suite remains deterministic and model-free.

### 5. Finish macOS-native discovery

Audit the remaining macOS state stores that can hold work outside Git and add
bounded readers only where a reproducible fixture proves the finding. Record
unsupported stores as explicit gaps instead of guessing.
