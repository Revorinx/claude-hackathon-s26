# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A healthcare follow-up app that parses after-visit summary PDFs from medical appointments and surfaces structured, actionable information to patients. **No hospital API integrations** — backend is Python, PDF data is the sole source of truth.

## Tech Stack Decisions

- **Backend**: Python (PDF parsing, Claude API, business logic)
- **Frontend**: TBD (likely React or Next.js)
- **Translation**: Google Translate API (for multi-language support)
- **No hospital/EHR API integration** — all data comes from uploaded PDFs

---

## Feature Architecture (Frontend / Backend split)

### 1. PDF Upload & Parsing
- **Backend**: Accept PDF upload, extract structured data (return precautions, appointments, medications, wound care, referrals, lifestyle instructions) using a PDF parsing library + Claude API for semantic extraction. Output a normalized JSON schema shared across all features.
- **Frontend**: File upload UI, loading/processing state, error states for unreadable PDFs.

### 2. Return Precautions ("Red Flags")
- **Backend**: Extract red-flag symptoms from parsed PDF. Run through Google Translate API when a non-English language is selected.
- **Frontend**: High-visibility card (prominent placement, bold/red styling). Language selector that triggers re-translation. "Call 911 / Go to ER / Call doctor" action buttons per symptom.

### 3. Follow-Up Appointments
- **Backend**: Parse appointment dates, locations, providers, and "what to bring" instructions from PDF. Expose as structured list.
- **Frontend**: Appointment cards with date, provider, location, and checklist of what to bring (fasting requirements, prior records). Calendar export option.

### 4. Wound / Device Care
- **Backend**: Extract step-by-step wound/device care instructions (dressing changes, drains, ostomy, splints).
- **Frontend**: Step-by-step checklist UI, photo-friendly layout. Checkboxes persist locally per session.

### 5. Referrals
- **Backend**: Extract specialist referrals with urgency, reason, and scheduling status.
- **Frontend**: Referral cards showing specialist type, reason, urgency level, and whether patient still needs to schedule.

### 6. Symptom & Recovery Tracking
- **Backend**: Define trackable symptom dimensions from the PDF (pain, breathing, swelling, etc.). Store daily check-in data. Detect trends.
- **Frontend**: Daily slider/checkbox check-in UI. Trend visualization (simple chart). Optional share-with-care-team export.

### 7. Medications & Pharmacy
- **Backend**: Extract current medication list from PDF, reconcile against discharge instructions. Extract pharmacy info, copay notes, OTC/supplement guidance.
- **Frontend**: Medication reconciliation list ("these are the meds you should have now — flag anything different"). Pharmacy card with pickup expectations and copay info. OTC/supplement allowed/discouraged flags.

### 8. Lifestyle & Education
- **Backend**: Extract diet restrictions (fluid/sodium/renal-cardiac), activity limits (walking, lifting, driving, return-to-work), substance use guidance. Surface relevant education content tied to diagnosis.
- **Frontend**: Structured sections per category. Activity restriction cards with specific limits (not generic). Linked education snippets (articles/videos) by diagnosis keyword.

### 9. Logistics & Accessibility
- **Backend**: Extract transportation/parking notes for follow-up visits. Support caregiver delegation (read-only mode with consent flag).
- **Frontend**: Large text / screen reader support. Multi-language content (Google Translate). Caregiver mode toggle (read-only delegated view).

### 10. Notifications & Engagement
- **Backend**: Schedule medication reminders and appointment nudges. Respect quiet hours and frequency caps. Support push / SMS / email channels.
- **Frontend**: Notification preferences UI (channel choice, quiet hours). Low-friction check-in prompts ("Did you take your morning meds?" — one-tap). Avoid guilt-heavy copy.

---

## Key Architectural Constraints

- All patient data originates from the uploaded PDF — no external health record lookups.
- The normalized JSON from PDF parsing is the shared contract between backend features and frontend components.
- Translation applies to red flags first (highest priority), then other content.
- Caregiver mode is read-only — no write permissions without explicit patient consent.
