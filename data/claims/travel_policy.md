# Falcon Bay Services LLC (fictional): domestic travel-expense policy (extract)

*Synthetic policy written for this portfolio project. Falcon Bay Services LLC is a fictional company.*

Applies to business trips inside the UAE. All amounts are in UAE dirhams (AED) and include VAT.

1. **Receipts.** Every expense line above AED 50 needs an itemised receipt or tax invoice. A booking
   confirmation, quote or card slip without items is not a receipt. Lines of AED 50 or less may be claimed
   without a receipt.
2. **Hotels.** Up to AED 600 per night.
3. **Meals.** Up to AED 150 per day in total, for all meal lines dated the same day.
4. **Deadline.** Submit the claim within 30 days after the last day of the trip.
5. **Dates.** Every expense must be dated between the first and the last day of the trip (both included),
   as shown on the receipt.
6. **Not reimbursable.** Alcohol, hotel minibar, spa or leisure services, personal shopping and souvenirs,
   traffic fines, and costs of family members or guests who are not on business.
7. **Amounts.** The amount claimed must equal the total on the receipt.
8. **One claim per receipt.** A receipt may be claimed only once. Earlier claims by the same employee are
   listed with each claim.
9. **Pre-approval.** Any single expense above AED 2,000 needs a pre-approval reference (PA-…).

## Problem codes used by the pre-check

| Code | Rule |
|---|---|
| `missing_receipt` | 1 |
| `over_limit` | 2, 3 |
| `late_submission` | 4 |
| `outside_trip_dates` | 5 |
| `non_reimbursable` | 6 |
| `amount_mismatch` | 7 |
| `duplicate` | 8 |
| `missing_preapproval` | 9 |
