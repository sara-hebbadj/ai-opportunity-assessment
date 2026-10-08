# The 20-case hand-computed fixture (`mini_log.csv`)

A tiny event log in the same format as the real one, designed so every number can be worked out on paper.
`tests/test_diagnostic.py` checks the code's numbers against the hand calculations below.

Every step happens at 09:00 UTC, so every wait is a whole number of days. Case `cNN` starts on
1 January 2018 + 2 × (NN − 1) days. Short names: S = submitted by employee, A = approved by administration,
B = approved by budget owner, F = final approval by supervisor, R = request payment, P = payment handled,
XA / XS / XE = rejected by administration / supervisor / employee.

| Cases | Variant | Waits before each step (days) | Throughput (days) |
|---|---|---|---|
| c01–c08 | S A F R P | A 1, F *k*, R 1, P 3 with *k* = 1, 1, 2, 2, 2, 3, 3, 4 | 6, 6, 7, 7, 7, 8, 8, 9 |
| c09–c12 | S A B F R P | A 1, B 2, F *b*, R 1, P 3 with *b* = 1, 1, 2, 3 | 8, 8, 9, 10 |
| c13–c15 | S F R P | F 1, R 1, P 3 | 5, 5, 5 |
| c16–c18 | S XA XE S A F R P | XA 1, XE *e*, S 1, A 1, F 2, R 1, P 3 with *e* = 2, 4, 9 | 11, 13, 18 |
| c19 | S A XS XE S A F R P | A 1, XS 2, XE 1, S 2, A 1, F 2, R 1, P 3 | 13 |
| c20 | S XA XE (abandoned) | XA 1, XE 3 | 4 |

## Hand calculations

- **Throughput, sorted (20 values):** 4, 5, 5, 5, 6, 6, 7, 7, 7, 8, 8, 8, 8, 9, 9, 10, 11, 13, 13, 18. Sum 167.
  - p50 = position 0.5 × 19 = 9.5 → (8 + 8) / 2 = **8.0**
  - p90 = position 0.9 × 19 = 17.1 → 13 + 0.1 × (13 − 13) = **13.0**
  - mean = 167 / 20 = **8.35**
- **Rejected cases:** c16–c20 = 5 / 20 = **25%**. Their throughput median (4, 11, 13, 13, 18) = **13**;
  the other 15 cases' median = **7**.
- **Resubmitted cases** (more than one S): c16–c19 = 4 / 20 = **20%**.
- **First rejecter:** administration in c16, c17, c18, c20 (**4**), supervisor in c19 (**1**).
- **Variants:** 6. The top one (S A F R P) has 8 / 20 = **40%** of cases.
- **Waiting by step (sum of days):** A 17, B 8, F 36, R 19, P 57, XA 4, XS 2, XE 19, S 5 → total **167**
  (the same as the throughput sum, as it must be). F's 19 waits have median **2**. P's share = 57 / 167 = **34.1%**.
- **Waiting by role:** payment stage (role UNDEFINED: R + P) 76 / 167 = **45.5%**; supervisor (F + XS) 38;
  employee (XE + S) 24; administration (A + XA) 21; budget owner 8.
- **Share of cases that wait for each role** (first event skipped): supervisor 19 / 20 = **95%**,
  administration 17 / 20 = **85%**, employee 5 / 20 = **25%**, budget owner 4 / 20 = **20%**.
