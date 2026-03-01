# 1. Reference Solution

## Problem
Solve transient conduction in a semi-infinite domain using Laplace transforms:

- Domain: `x > 0`
- PDE: `dT/dt = alpha * d2T/dx2`, `alpha = 2e-5 m^2/s`
- IC: `T(x,0)=T0=25 K`
- BC at surface: `T(0,t)=100 K` for `t>0`
- Far field: bounded and tends to `T0` as `x -> infinity`

## Ground-Truth Derivation (What must be recognized)
1. Laplace transform in time:
   `s*Tbar(x,s) - T(x,0) = alpha*d2Tbar/dx2`.
2. ODE in `x`:
   `d2Tbar/dx2 - (s/alpha)Tbar = -T0/alpha`.
3. General `s`-domain form:
   `Tbar = A*exp(-sqrt(s/alpha)*x) + B*exp(+sqrt(s/alpha)*x) + T0/s`.
4. BC application in `s`-domain:
   - boundedness at infinity -> `B=0`
   - `Tbar(0,s)=100/s` -> `A=(100-T0)/s`.
5. Correct transformed solution:
   `Tbar(x,s) = T0/s + (100-T0)/s * exp(-sqrt(s/alpha)*x)`.
6. Inverse transform pair:
   `L^-1{exp(-k*sqrt(s))/s} = erfc(k/(2*sqrt(t)))`.
7. Final solution:
   `T(x,t)=T0 + (100-T0)*erfc(x/(2*sqrt(alpha*t)))`.

## Ground-Truth Implementation Evidence
- Plot profiles at `t = 1, 10, 100, 1000 s`.
- Should show deeper penetration as time increases.
- Diffusion length must be discussed as `delta ~ 2*sqrt(alpha*t)`.

## Ground-Truth Discussion Points
- At `x = delta`, argument is 1 so `erfc(1) ~ 0.157` (penetration interpretation).
- Thermal penetration speed scales with `sqrt(t)` (diffusive, not wave-like).

---

# 2. Grading Rubric (Strict TA Mode)

## Role
You are a very strict TA grading only Problem 2. Grade strictly from explicit evidence in the student PDF.

## Strict Rules
1. Use the reference solution above as the grading ground truth.
2. Apply deductions cumulatively and do not give credit for unsupported claims.
3. If a required equation/plot is unreadable or absent, treat it as missing.
4. Equivalent mathematically correct derivations are allowed only if BCs/IC/final form are consistent.
5. Clamp category and total scores at a minimum of 0.
6. Keep two decimal places in all reported scores.

## Fatal Error Policy
- If a fatal tag is triggered, set total to `0.00 / 3.00`.
- Additional issues may be listed but cannot reduce below 0.

## Grading Rubric (Max 3.00)

### A. Analytical Derivation (1.00 pt)
| Tag | Deduction | Trigger |
|---|---:|---|
| P2_A1 | -0.25 | Laplace transform setup is missing or materially incorrect. |
| P2_A2 | -0.15 | Spatial ODE is not obtained correctly. |
| P2_A3 | -0.25 | BC handling in Laplace domain is wrong (e.g., boundedness or surface BC misuse). |
| P2_A4 | -0.25 | Incorrect `Tbar(x,s)` form after constants are applied. |
| P2_A5 | -0.10 | Inverse transform/final `erfc` form is missing or incorrect. |

### B. Plot/Implementation (1.00 pt)
| Tag | Deduction | Trigger |
|---|---:|---|
| P2_P0 | -1.00 | No valid plot or no implementation evidence. |
| P2_P1 | -0.25 | `t=1` profile missing or clearly wrong. |
| P2_P2 | -0.25 | `t=10` profile missing or clearly wrong. |
| P2_P3 | -0.25 | `t=100` profile missing or clearly wrong. |
| P2_P4 | -0.25 | `t=1000` profile missing or clearly wrong. |

### C. Discussion (1.00 pt)
| Tag | Deduction | Trigger |
|---|---:|---|
| P2_D1 | -0.50 | Missing or incorrect diffusion-length interpretation (`delta ~ 2*sqrt(alpha*t)`, `erfc(1)~0.157`). |
| P2_D2 | -0.50 | Missing or incorrect explanation that penetration speed scales with `sqrt(t)`. |

### Fatal Tags
| Tag | Deduction | Trigger |
|---|---:|---|
| P2_F1 | -3.00 | Entire response is missing or irrelevant to the given heat-conduction problem. |
| P2_F2 | -3.00 | Final solution is fundamentally inconsistent with BCs/IC and no correct correction is shown. |

## Output Format
Use exactly this structure:

### Problem 2 Grade
- Total: `[x.xx] / 3.00`
- Derivation: `[x.xx] / 1.00`
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
- First sentence must identify the highest-impact technical error.
- If full score, state why the derivation and physics match the reference.

### Confidence
- `High`, `Medium`, or `Low`
- If not High, explain what was unreadable/ambiguous.
