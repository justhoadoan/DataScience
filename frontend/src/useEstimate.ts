import { useRef, useState, type FormEvent } from "react";
import type { Draft, Estimate, Schema } from "./types";

export function maxBedrooms(draft: Draft, schema: Schema | null) {
  if (!schema) return 0;
  const policy = schema.layout_policy;
  return Math.max(
    0,
    Math.min(
      policy.category_max_bedrooms[draft.category],
      Math.floor(
        (Number(draft.area) - policy.shared_area_m2) /
          policy.area_per_separate_bedroom_m2,
      ),
    ),
  );
}

function focusError(fields: Record<string, string>) {
  const key = Object.keys(fields)[0];
  requestAnimationFrame(() => {
    const field = document.getElementById(key === "area_m2" ? "area" : key);
    const details = field?.closest("details");
    if (details) details.open = true;
    field?.focus();
  });
}

export function useEstimate(schema: Schema | null) {
  const [draft, setDraft] = useState<Draft>({
    category: "can_ho_chung_cu",
    district: "",
    area: "50",
    bedrooms: "",
    furnishing: "Unknown",
    valuation_date: "",
    ward_key: "Unknown",
    project_id: "Unknown",
    bathrooms: "",
  });
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [submitted, setSubmitted] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const request = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const stale =
    !!submitted && JSON.stringify(draft) !== JSON.stringify(submitted);
  const maximum = maxBedrooms(draft, schema);
  const invalidLayout =
    draft.bedrooms !== "" && Number(draft.bedrooms) > maximum;
  const valuationDates = schema?.valuation_date?.supported_categories?.includes(
    draft.category,
  )
    ? schema.valuation_date
    : undefined;

  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({
      ...current,
      [key]: value,
      ...(key === "district"
        ? { ward_key: "Unknown", project_id: "Unknown" }
        : {}),
      ...(key === "category" ? { bathrooms: "" } : {}),
    }));
    setErrors((current) => ({
      ...current,
      [key === "area" ? "area_m2" : key]: "",
      ...(key === "district" ? { ward_key: "", project_id: "" } : {}),
    }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (!draft.district) next.district = "Choose a district in Hanoi.";
    if (
      !draft.area ||
      !Number.isFinite(Number(draft.area)) ||
      Number(draft.area) <= 5 ||
      Number(draft.area) > 500
    )
      next.area_m2 = "Enter an area greater than 5 and no more than 500 m².";
    if (
      draft.bedrooms !== "" &&
      (!Number.isInteger(Number(draft.bedrooms)) ||
        Number(draft.bedrooms) < 0 ||
        invalidLayout)
    )
      next.bedrooms = `This area allows up to ${maximum} separate bedrooms. Choose 0 for a studio.`;
    if (
      valuationDates &&
      draft.valuation_date &&
      (draft.valuation_date < valuationDates.min ||
        draft.valuation_date > valuationDates.max)
    )
      next.valuation_date = "Choose a valuation date within the allowed range.";
    setErrors(next);
    if (Object.keys(next).length) {
      focusError(next);
      return;
    }
    controller.current?.abort();
    const active = new AbortController();
    controller.current = active;
    const id = ++request.current;
    const sent = { ...draft };
    setBusy(true);
    try {
      const response = await fetch("/api/predict", {
        method: "POST",
        signal: active.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: sent.category,
          district: sent.district,
          area_m2: Number(sent.area),
          bedrooms: sent.bedrooms === "" ? null : Number(sent.bedrooms),
          furnishing: sent.furnishing,
          valuation_date: valuationDates
            ? sent.valuation_date || undefined
            : undefined,
          ward_key: schema?.optional.includes("ward_key")
            ? sent.ward_key
            : undefined,
          project_id: schema?.optional.includes("project_id")
            ? sent.project_id
            : undefined,
          bathrooms:
            schema?.optional.includes("bathrooms") && sent.bathrooms !== ""
              ? Number(sent.bathrooms)
              : undefined,
        }),
      });
      const body = await response.json();
      if (id !== request.current) return;
      if (!response.ok) {
        const fields: Record<string, string> = {};
        if (Array.isArray(body.detail))
          body.detail.forEach((error: { loc?: string[]; msg: string }) => {
            const name = error.loc?.at(-1) || "form";
            fields[name === "body" ? "form" : name] = error.msg.replace(
              /^Value error, /,
              "",
            );
          });
        else
          fields.form =
            body.detail ||
            "An estimate is unavailable right now. Please try again.";
        setErrors(fields);
        focusError(fields);
        return;
      }
      setEstimate(body);
      setSubmitted(sent);
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return;
      if (id === request.current)
        setErrors({
          form: "Connection lost. Check your connection and try again.",
        });
    } finally {
      if (id === request.current) setBusy(false);
    }
  }
  return {
    draft,
    update,
    estimate,
    submitted,
    busy,
    errors,
    submit,
    stale,
    maximum,
    invalidLayout,
    valuationDates,
  };
}
