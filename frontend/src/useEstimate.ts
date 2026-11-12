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

export function useEstimate(schema: Schema | null) {
  const [draft, setDraft] = useState<Draft>({
    category: "can_ho_chung_cu",
    district: "",
    area: "50",
    bedrooms: "",
    furnishing: "Unknown",
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

  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({
      ...current,
      [key === "area" ? "area_m2" : key]: "",
    }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (!draft.district) next.district = "Chọn quận/huyện tại Hà Nội.";
    if (
      !draft.area ||
      !Number.isFinite(Number(draft.area)) ||
      Number(draft.area) <= 5 ||
      Number(draft.area) > 500
    )
      next.area_m2 = "Diện tích phải lớn hơn 5 và tối đa 500 m².";
    if (
      draft.bedrooms !== "" &&
      (!Number.isInteger(Number(draft.bedrooms)) ||
        Number(draft.bedrooms) < 0 ||
        invalidLayout)
    )
      next.bedrooms = `Diện tích này hỗ trợ tối đa ${maximum} phòng ngủ riêng. Chọn 0 nếu là studio.`;
    setErrors(next);
    if (Object.keys(next).length) {
      const key = Object.keys(next)[0];
      requestAnimationFrame(() =>
        document.getElementById(key === "area_m2" ? "area" : key)?.focus(),
      );
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
            body.detail || "Không thể ước tính lúc này. Vui lòng thử lại.";
        setErrors(fields);
        return;
      }
      setEstimate(body);
      setSubmitted(sent);
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return;
      if (id === request.current)
        setErrors({ form: "Mất kết nối với dịch vụ. Vui lòng thử lại." });
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
  };
}
