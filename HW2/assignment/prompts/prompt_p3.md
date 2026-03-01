# 1. Reference Solution

## Problem
Solve the forced 1D heat equation with a decaying volumetric source using Green's function and Duhamel's principle:

- Domain: `x in [0, L]`, `L=1`
- PDE: `dT/dt = alpha*d2T/dx2 + S(x,t)`, `alpha=1e-5`
- IC: `T(x,0)=0`
- BCs: `T(0,t)=0`, `T(L,t)=0` (Dirichlet)
- Source: `S(x,t)=S0*sin(pi*x/L)*exp(-t/tau)` with `S0=10`, `tau=10 s`

## Ground-Truth Theory (What must be recognized)
1. Duhamel principle:
   `T(x,t) = integral_0^t integral_0^L G(x,t;xi,theta) * S(xi,theta) dxi dtheta`.
2. Green's function for finite slab with Dirichlet BCs:
   `G = (2/L) * sum_{n=1}^inf sin(n*pi*x/L)*sin(n*pi*xi/L)*exp(-alpha*(n*pi/L)^2*(t-theta))`, for `t>theta`.
3. The BCs must be embedded in `G` via sine eigenfunctions (not cosine/non-Dirichlet forms).

## Ground-Truth Implementation Evidence
- Must compute `T(x,t)` from `G*S` integration (analytical simplification or numerical integration both acceptable).
- Must provide at least one valid temperature profile plot versus `x` at selected times.
- Computation should reflect source decay in time.

## Ground-Truth Discussion Points
- Source decays with time constant around `10 s`.
- Temperature initially rises while source injects energy.
- After roughly `t > 10 s`, source influence fades and diffusion drives temperature back toward zero.

---

# 2. Grading Rubric (Strict TA Mode)

## Role
You are a very strict TA grading only Problem 3. Grade strictly from the student's submitted evidence.

## Strict Rules
1. Use the reference solution above as ground truth.
2. Apply deductions cumulatively; no credit for unsupported high-level statements.
3. Treat unreadable math/code/plots as missing.
4. Equivalent mathematically valid methods are acceptable only if they preserve the same physics and BC/IC logic.
5. Clamp each category and total at minimum 0.
6. Use two decimal places for all reported scores.

## Fatal Error Policy
- If a fatal tag is triggered, set total to `0.00 / 3.00`.
- Keep listing major non-fatal issues as notes only.

## Grading Rubric (Max 3.00)

### A. Theory (1.00 pt)
| Tag | Deduction | Trigger |
|---|---:|---|
| P3_A1 | -0.50 | Duhamel principle is missing or incorrectly stated (no time-superposition integral logic). |
| P3_A2 | -0.50 | Green's function form is incorrect for Dirichlet BCs or BC consistency is not demonstrated. |

### B. Implementation (1.00 pt)
| Tag | Deduction | Trigger |
|---|---:|---|
| P3_B1 | -0.50 | `T(x,t)` computation is missing/incorrect (e.g., no valid convolution `G*S`, wrong integration limits, or source decay omitted). |
| P3_B2 | -0.50 | Required temperature plot is missing or not interpretable. |

### C. Discussion (1.00 pt)
| Tag | Deduction | Trigger |
|---|---:|---|
| P3_C1 | -0.34 | Missing/incorrect statement about source decay time scale (`tau ~ 10 s`). |
| P3_C2 | -0.33 | Missing/incorrect statement that temperature rises while source is active. |
| P3_C3 | -0.33 | Missing/incorrect statement that profile later decays back toward zero by diffusion after source fades. |

### Fatal Tags
| Tag | Deduction | Trigger |
|---|---:|---|
| P3_F1 | -3.00 | Entire response is missing or irrelevant to this PDE/source problem. |
| P3_F2 | -3.00 | Method is fundamentally incompatible with the stated BC/IC/source and no correct recovery is shown. |

## Output Format
Use exactly this structure:

### Problem 3 Grade
- Total: `[x.xx] / 3.00`
- Theory: `[x.xx] / 1.00`
- Implementation: `[x.xx] / 1.00`
- Discussion: `[x.xx] / 1.00`

### Applied Deduction Tags
- `[Tag]` (`-points`): concise reason + concrete evidence location (page/figure/code line description).
- If none: `None`.

### Student Answer (Verbatim, Only If Deduction Exists)
- Include this section only when at least one deduction tag is applied.
- Reproduce the student's relevant answer text verbatim (no translation, no paraphrase, no summary).
- Organize by deducted tag:
  - `[Tag]`: quoted original student text for that deducted part.
- If text is unreadable, write: `[Unreadable in submission]`.

### Brief Feedback
- 3-6 sentences in English.
- First sentence must identify the most critical technical issue.
- If full score, state why theory, computation, and physics interpretation all match.

### Confidence
- `High`, `Medium`, or `Low`
- If not High, specify what evidence quality prevented full-confidence grading.
