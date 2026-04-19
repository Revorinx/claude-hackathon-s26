# claude-hackathon-s26


#building a healthcare app that uses uploaded after-visit summary PDFs you get from appointments
Clinical follow-up
Return precautions (“red flags”): Clear, plain-language symptoms that mean “call 911 / go back to ER / call your doctor” — often the highest-impact content after discharge instructions. Include a translation feature tailored to anyone language they primarily speak (using Google translate)
Follow-up appointments: Primary care, specialist, imaging, labs — with dates, locations, and “what to bring” (fasting labs, prior records).
Wound / device care: Dressing changes, drain care, ostomy, splints — step-by-step and photo-friendly checklists where appropriate.
Referrals: Which specialist, why, urgency, and whether the patient still needs to schedule.
Symptom & recovery tracking: Simple daily sliders or checklists (pain, breathing, swelling) to spot trends; optional sharing with the care team in a pilot.
Medication-adjacent
Pharmacy & pickup: Which pharmacy, ready-by expectations, copay reminders, medication reconciliation (“these are the meds you should have now — flag anything different”).
OTC / supplements: What’s allowed or discouraged if the discharge summary mentions it.
Lifestyle & education
Fluids / sodium / renal-cardiac diets when relevant (stricter than generic “healthy eating”).
Activity progression: Not just “exercise” but walking limits, lifting restrictions, driving restrictions, return-to-work/school.
Substance use: Alcohol/smoking guidance if in the care plan.
Education snippets: Short articles or videos tied to the diagnosis (e.g., asthma action plan).
Logistics & social context
Transportation / parking for follow-up visits (especially for mobility-limited patients).
Caregiver mode: Read-only or delegated tasks for a family member with consent.
Language & accessibility: Multi-language content, large text, screen reader support.
Engagement & safety
Notification preferences: Quiet hours, channel choice (push vs SMS vs email), frequency caps.
Check-in nudges: “Did you take your morning meds?” with low-friction taps, not guilt-heavy UX.
#avoid hospital API - use python  