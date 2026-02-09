# ElectiveRules Verification Checklist

Use this after generating `out/ElectiveRules.prefill.csv` to make sure cap logic is correct before broad rollout.

## 1) Load suggested rules
1. In Google Sheets, open/create tab `ElectiveRules`.
2. Import `out/ElectiveRules.priority.csv` first (or `out/ElectiveRules.prefill.csv` for full set).
3. Confirm headers are exactly: `Institution`, `Program`, `Rule_Text`.

## 2) Validate known bug fix
1. Program: `MacEwan` + `Bachelor of Arts Undeclared`.
2. Student setup: provide 3 strong Group B electives and enough other required marks.
3. Run **Admissions Checker -> Check Eligibility**.
4. Confirm `Avg Used` includes at most 2 Group B electives.

## 3) Spot-check random sampled programs
1. Take at least 10 rows from `out/ElectiveRules.priority.csv`.
2. For each row, confirm the rule text against source admissions wording.
3. Keep rows only when wording clearly matches.

## 4) Resolve unresolved rows
1. Open `out/ElectiveRules.prefill.audit.csv`.
2. Filter `Rule_Text` blank or `Parse_Status` not `rule_detected`.
3. Manually review and add rule text where needed.

## 5) Regression sanity pass
1. Run `runElectiveRuleSelfTest_()` in Apps Script editor.
2. Re-run checker on a few known student profiles.
3. Confirm no obvious average regressions in `Eligible`/`Ineligible`.
