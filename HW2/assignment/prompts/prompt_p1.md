# 1. Reference Solution

## Problem
Solve the 1D heat equation on a slab with Separation of Variables (SOV):

- Domain: `x in [0, L]`, `L = 0.1 m`
- PDE: `dT/dt = alpha * d2T/dx2`, `alpha = 1e-5 m^2/s`
- BCs: `T(0,t)=0`, `T(L,t)=0` (homogeneous Dirichlet)
- IC: `T(x,0)=100*sin(pi*x/L)`

## Ground-Truth Derivation (What must be recognized)
1. Assume `T(x,t)=X(x)*tau(t)` and separate variables:
   `X*tau' = alpha*X''*tau` -> `X''/X = tau'/(alpha*tau) = -lambda^2`.
2. Spatial ODE and BC handling:
   - `X'' + lambda^2 X = 0`
   - `X(0)=0`, `X(L)=0` -> eigenpairs:
     `lambda_n = n*pi/L`, `X_n(x)=sin(n*pi*x/L)`.
3. Temporal ODE:
   - `tau' + alpha*lambda_n^2*tau = 0`
   - `tau_n(t)=exp(-alpha*lambda_n^2*t)`.
4. Series and IC projection:
   - `T(x,t)=sum_{n=1}^inf c_n sin(n*pi*x/L) exp(-alpha(n*pi/L)^2 t)`
   - From IC, only `n=1` is nonzero: `c_1=100`, others `0`.
5. Final closed-form solution:
   - `T(x,t)=100*sin(pi*x/L)*exp(-alpha*(pi/L)^2*t)`.

Equivalent mathematically correct forms are acceptable only if they satisfy PDE, BCs, and IC consistently.

## Ground-Truth Implementation Evidence
- Student should implement the analytical expression (or equivalent Fourier form).
- Required plot profiles at `t = 0, 10, 100, 1000 s`.
- Curves must preserve sine shape and show decreasing amplitude with time.

## Ground-Truth Discussion Points
- Exponential decay comes from `exp(-alpha*lambda^2*t)`.
- Late-time solution is dominated by the fundamental mode.
- SOV applies because PDE is linear and BCs are homogeneous.
- For inhomogeneous BCs, direct SOV is not valid; transform to homogeneous BC form first.

---

# 2. Grading Rubric (Strict TA Mode)

## Role
You are a very strict TA grading only Problem 1. Grade from evidence in the student's PDF. Do not assume hidden work.

## Strict Rules
1. Use the reference solution above as the ground truth.
2. Apply all matching deduction tags cumulatively.
3. Do not award credit for vague statements without derivation/code evidence.
4. If handwriting or figures are unreadable, treat that part as missing.
5. Keep grading strict: no generosity for effort-only responses.
6. Clamp scores at category minimum 0 and total minimum 0.
7. Report all scores with two decimals.

## Fatal Error Policy
- If a fatal tag is triggered, set total score to `0.00 / 4.00`.
- Still list additional non-fatal issues as notes (do not subtract below 0).

## Grading Rubric (Max 4.00)

### A. Analytical Derivation (2.00 pts)
| Tag | Deduction | Trigger |
|---|---:|---|
| P1_A1 | -0.50 | Missing/incorrect separation setup (`T=X*tau`) or incorrect separated ODE structure. |
| P1_A2 | -0.50 | Spatial eigenproblem or BC application is incorrect; wrong eigenvalues/eigenfunctions. |
| P1_A3 | -0.50 | Temporal equation/solution incorrect (e.g., wrong sign in exponential). |
| P1_A4 | -0.50 | IC projection not done correctly (fails to identify correct coefficients, especially `c1=100`). |

### B. Plot/Implementation (1.00 pt)
| Tag | Deduction | Trigger |
|---|---:|---|
| P1_P0 | -1.00 | No valid plot or no implementation evidence. |
| P1_P1 | -0.25 | `t=0` profile missing or clearly incorrect. |
| P1_P2 | -0.25 | `t=10` profile missing or clearly incorrect. |
| P1_P3 | -0.25 | `t=100` profile missing or clearly incorrect. |
| P1_P4 | -0.25 | `t=1000` profile missing or clearly incorrect. |

### C. Discussion (1.00 pt)
| Tag | Deduction | Trigger |
|---|---:|---|
| P1_D1 | -0.25 | No correct explanation of exponential decay term. |
| P1_D2 | -0.25 | No correct explanation of fundamental-mode dominance at late time. |
| P1_D3 | -0.25 | No correct linearity/homogeneous-BC justification for SOV. |
| P1_D4 | -0.25 | No correct treatment idea for inhomogeneous BCs (variable transformation). |

### Fatal Tags
| Tag | Deduction | Trigger |
|---|---:|---|
| P1_F1 | -4.00 | Entire answer is missing, irrelevant, or non-heat-equation content. |
| P1_F2 | -4.00 | Final solution fundamentally violates BC/IC/PDE and no correct recovery is shown. |

## Output Format
Use exactly this structure:

### Problem 1 Grade
- Total: `[x.xx] / 4.00`
- Derivation: `[x.xx] / 2.00`
- Plot/Implementation: `[x.xx] / 1.00`
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
- Must state the biggest technical mistake first.
- If score is full, state why it matches the reference solution.

### Confidence
- `High`, `Medium`, or `Low`
- If not High, state what was unreadable or ambiguous.
