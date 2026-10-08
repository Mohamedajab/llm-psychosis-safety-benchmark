# Independent review portal

The reviewer website is a separate project, not the local collection-control dashboard.
Its first stage covers synthetic scenarios and the draft annotation rubric only.
Model-reply annotation remains unavailable until the relevant review and calibration gates pass.

## Materials and blinding

The pack contains 30 twelve-turn scripts and six twenty-four-turn scripts used in the
closed sized exploration, plus the current draft rubric. Each script has a randomly
assigned blind ID, a version and a material hash. The export contains no intended
condition, scenario-family identifier, model response, provider, price or repetition.
The private label map remains in ignored local storage. Do not regenerate IDs once
review begins; material revisions require new versions and re-review.

The scripts come from the verified frozen inputs. The rubric is the author draft
available when the pack was created; this does not make it clinically validated.

## Workflow

The website starts owner-private and review-closed. Authentication uses ChatGPT;
app approval and platform sharing are separate checks. The researcher can preview
but cannot contribute independent reviews. No invitation is sent automatically.

The owner records the actual institutional determination, study contact, retention
period and withdrawal handling before opening participation. These are administrative
records, not approvals issued by the website. Assigned reviewers must read the
participant information, consent and attest to independent review. If those terms
change, consent must be recorded again before continuing.

Scenario feedback covers relevance, clarity, plausibility, a blinded interpretation
classification, urgency, emotional intensity, stigma, leading wording, unnecessary
actionable detail and suggested revisions. These are draft questions, not validated
scales. Rubric feedback addresses P1–P5, P2/P3 applicability, secondary dimensions and
boundary cases. Submissions do not automatically approve constructs or the study.

Reviewers can save drafts or skip without giving a personal reason. Server checks
enforce assignment, approval, current consent and independent-review status. Reviewers
cannot see another reviewer's feedback. Earlier submitted revisions are retained.
Owner exports use pseudonymous IDs and omit sign-in emails; free-text feedback must
still be checked for identifying information before use or release.

## Verification and remaining work

Thirty-three local synthetic checks passed, including unauthorized access, owner
authorization, consent gates, material hashes, stale drafts, duplicate submissions,
reviewer isolation, access revocation and changed participant terms. Test fixtures
were removed locally and are not shipped to the hosted database. Type checking and
the production build passed. Browser visual QA and WebMCP runtime validation were
unavailable; browser tools only read status or navigate, never supply review judgments.

Coverage of two reviewers per item is a tracking rule, not a validity criterion.
Reviewer qualifications and independence still need verification. Paired-condition
equivalence, history-context review and calibration are separate steps. This review
can motivate future revisions; it cannot retroactively validate exploratory collection
or turn it into a preregistered confirmatory study.
