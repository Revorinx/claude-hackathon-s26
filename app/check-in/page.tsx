"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CarePlan, CheckInResponse, Symptoms } from "@/lib/types/care-plan";
import { loadCarePlan } from "@/lib/care-plan-storage";
import { demoCheckIn } from "@/lib/demo-checkin";
import { Disclaimer } from "@/components/Disclaimer";

const defaultSymptoms: Symptoms = {
  pain: 2,
  fever: "none",
  swelling: "none",
  shortness_of_breath: "none",
  nausea: "none",
  worse_overall: false,
};

export default function CheckInPage() {
  const [plan, setPlan] = useState<CarePlan | null>(null);
  const [symptoms, setSymptoms] = useState<Symptoms>(defaultSymptoms);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckInResponse | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    setPlan(loadCarePlan());
  }, []);

  async function submit() {
    if (!plan) return;
    setLoading(true);
    setNote(null);
    setResult(null);
    try {
      const res = await fetch("/api/check-in", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symptoms,
          red_flags: plan.red_flags,
          care_plan_summary: plan.plain_language_summary,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult(data as CheckInResponse);
        return;
      }
      if (res.status === 503) {
        setNote("API unavailable — showing demo triage logic.");
        setResult(demoCheckIn(symptoms, plan));
        return;
      }
      throw new Error(data.error ?? "Check-in failed");
    } catch (e) {
      setNote(
        e instanceof Error
          ? `${e.message} — showing demo triage.`
          : "Error — showing demo triage."
      );
      setResult(demoCheckIn(symptoms, plan));
    } finally {
      setLoading(false);
    }
  }

  if (!plan) {
    return (
      <main className="flex flex-1 flex-col justify-center px-5 pb-8 pt-8">
        <h1 className="text-2xl font-semibold text-stone-900">Check-in</h1>
        <p className="mt-3 text-stone-600">
          Load a care plan first so we can compare your symptoms to your
          discharge warning signs.
        </p>
        <Link
          href="/upload"
          className="mt-8 inline-flex min-h-12 items-center justify-center rounded-2xl bg-teal-700 px-5 font-medium text-white"
        >
          Add discharge instructions
        </Link>
        <Disclaimer />
      </main>
    );
  }

  return (
    <main className="flex flex-1 flex-col px-5 pb-8 pt-8">
      <h1 className="text-2xl font-semibold text-stone-900">How are you feeling?</h1>
      <p className="mt-2 text-sm text-stone-600">
        Quick check-in. We&apos;ll compare this to the warning signs from your
        paperwork.
      </p>

      <div className="mt-8 space-y-6">
        <div>
          <label className="text-sm font-medium text-stone-800" htmlFor="pain">
            Pain (0–10)
          </label>
          <div className="mt-2 flex items-center gap-4">
            <input
              id="pain"
              type="range"
              min={0}
              max={10}
              value={symptoms.pain}
              onChange={(e) =>
                setSymptoms((s) => ({ ...s, pain: Number(e.target.value) }))
              }
              className="w-full accent-teal-700"
            />
            <span className="w-8 text-right text-sm font-medium text-stone-800">
              {symptoms.pain}
            </span>
          </div>
        </div>

        <SelectField
          label="Fever"
          value={symptoms.fever}
          onChange={(fever) => setSymptoms((s) => ({ ...s, fever }))}
          options={[
            { value: "none", label: "None / not measured" },
            { value: "low", label: "Low-grade" },
            { value: "high", label: "High / shaking chills" },
            { value: "unknown", label: "Not sure" },
          ]}
        />

        <SelectField
          label="Swelling"
          value={symptoms.swelling}
          onChange={(swelling) => setSymptoms((s) => ({ ...s, swelling }))}
          options={[
            { value: "none", label: "None" },
            { value: "mild", label: "Mild" },
            { value: "moderate", label: "Moderate" },
            { value: "severe", label: "Severe" },
          ]}
        />

        <SelectField
          label="Shortness of breath"
          value={symptoms.shortness_of_breath}
          onChange={(shortness_of_breath) =>
            setSymptoms((s) => ({ ...s, shortness_of_breath }))
          }
          options={[
            { value: "none", label: "None" },
            { value: "mild", label: "Mild" },
            { value: "moderate", label: "Moderate" },
            { value: "severe", label: "Severe" },
          ]}
        />

        <SelectField
          label="Nausea"
          value={symptoms.nausea}
          onChange={(nausea) => setSymptoms((s) => ({ ...s, nausea }))}
          options={[
            { value: "none", label: "None" },
            { value: "mild", label: "Mild" },
            { value: "moderate", label: "Moderate" },
            { value: "severe", label: "Severe" },
          ]}
        />

        <label className="flex cursor-pointer items-center gap-3 rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <input
            type="checkbox"
            className="size-5 rounded border-stone-300 text-teal-700"
            checked={symptoms.worse_overall}
            onChange={(e) =>
              setSymptoms((s) => ({ ...s, worse_overall: e.target.checked }))
            }
          />
          <span className="text-sm text-stone-800">
            Overall, I feel worse than yesterday
          </span>
        </label>
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={loading}
        className="mt-8 min-h-12 rounded-2xl bg-teal-700 px-5 font-medium text-white shadow-sm hover:bg-teal-800 disabled:opacity-60"
      >
        {loading ? "Getting guidance…" : "Get guidance"}
      </button>

      {note ? (
        <p className="mt-4 text-sm text-stone-600" role="status">
          {note}
        </p>
      ) : null}

      {result ? (
        <section
          className={`mt-8 rounded-2xl border p-4 shadow-sm ${
            result.tier === "urgent"
              ? "border-red-200 bg-red-50"
              : result.tier === "provider"
                ? "border-amber-200 bg-amber-50"
                : "border-teal-200 bg-teal-50"
          }`}
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-600">
            Suggested next step
          </p>
          <h2 className="mt-1 text-lg font-semibold text-stone-900">
            {result.warning}
          </h2>
          <p className="mt-2 text-sm font-medium capitalize text-stone-800">
            Level: {result.tier === "home"
              ? "Continue home care"
              : result.tier === "provider"
                ? "Contact your provider"
                : "Seek urgent care / emergency if severe"}
          </p>
          <p className="mt-3 text-sm leading-relaxed text-stone-800">
            {result.rationale}
          </p>
          <div className="mt-4 rounded-xl bg-white/70 p-3 text-sm text-stone-800">
            <p className="font-medium text-stone-900">Why we&apos;re flagging this</p>
            <p className="mt-1">{result.reason_for_concern}</p>
            <p className="mt-3 text-xs text-stone-600">
              From your instructions: &quot;{result.triggering_excerpt}&quot;
            </p>
          </div>
          <div className="mt-4 rounded-xl border border-stone-200 bg-white p-3">
            <p className="text-xs font-semibold uppercase text-stone-500">
              Share with caregiver / clinic
            </p>
            <p className="mt-2 whitespace-pre-wrap text-sm text-stone-800">
              {result.shareable_text}
            </p>
          </div>
        </section>
      ) : null}

      <Disclaimer />
    </main>
  );
}

function SelectField<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  const id = label.replace(/\s+/g, "-").toLowerCase();
  return (
    <div>
      <label className="text-sm font-medium text-stone-800" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="mt-2 w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-900 shadow-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-600/20"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
