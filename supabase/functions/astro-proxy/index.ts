import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

type JsonRecord = Record<string, unknown>;

type RenderDataNormalizationConfig = {
  natalPrefix?: string;
};

type SynastryPersonPayload = {
  birth_date?: string;
  birth_time?: string | null;
  natal_year?: number;
  natal_month?: number;
  natal_day?: number;
  natal_hour?: number;
  natal_minute?: number;
  natal_second?: number;
  timezone?: string | null;
  tz_offset_minutes?: number | null;
  lat?: number;
  lng?: number;
  name?: string | null;
  [key: string]: unknown;
};

const RENDER_DATA_DATE_FIELDS = [
  "year",
  "month",
  "day",
  "hour",
  "minute",
  "second",
] as const;

const DEFAULT_CONFIG: RenderDataNormalizationConfig = {
  natalPrefix: "natal_",
};

export const normalizeRenderDataPayload = (
  payload: JsonRecord,
  config: RenderDataNormalizationConfig = DEFAULT_CONFIG,
): JsonRecord => {
  const normalized: JsonRecord = { ...payload };
  const prefix = config.natalPrefix ?? "natal_";

  for (const field of RENDER_DATA_DATE_FIELDS) {
    const natalField = `${prefix}${field}`;
    const hasRenderField = normalized[field] !== undefined;
    const natalValue = payload[natalField];

    if (!hasRenderField && natalValue !== undefined) {
      normalized[field] = natalValue;
    }
  }

  return normalized;
};

const pad2 = (value: number) => String(value).padStart(2, "0");

const normalizeSynastryPerson = (
  person: SynastryPersonPayload,
): SynastryPersonPayload => {
  const normalized: SynastryPersonPayload = { ...person };

  if (!normalized.birth_date && normalized.natal_year !== undefined) {
    const year = normalized.natal_year;
    const month = normalized.natal_month;
    const day = normalized.natal_day;
    if (
      typeof year === "number" &&
      typeof month === "number" &&
      typeof day === "number"
    ) {
      normalized.birth_date = `${year}-${pad2(month)}-${pad2(day)}`;
    }
  }

  if (!normalized.birth_time && normalized.natal_hour !== undefined) {
    const hour = normalized.natal_hour;
    const minute = normalized.natal_minute ?? 0;
    const second = normalized.natal_second ?? 0;
    if (
      typeof hour === "number" &&
      typeof minute === "number" &&
      typeof second === "number"
    ) {
      normalized.birth_time = `${pad2(hour)}:${pad2(minute)}:${pad2(second)}`;
    }
  }

  return normalized;
};

const normalizeSynastryPayload = (payload: JsonRecord): JsonRecord => {
  const normalized: JsonRecord = { ...payload };
  const personA = (payload.person_a ?? payload.person1) as
    | SynastryPersonPayload
    | undefined;
  const personB = (payload.person_b ?? payload.person2) as
    | SynastryPersonPayload
    | undefined;

  if (personA && normalized.person_a === undefined) {
    normalized.person_a = normalizeSynastryPerson(personA);
  }

  if (personB && normalized.person_b === undefined) {
    normalized.person_b = normalizeSynastryPerson(personB);
  }

  return normalized;
};

const upstreamUrl = Deno.env.get("ASTRO_API_URL") ?? "http://localhost:8000";

serve(async (req) => {
  const url = new URL(req.url);
  const upstreamPath = url.pathname;
  const targetPath = upstreamPath;
  const upstreamUrlObject = new URL(upstreamUrl);
  const queryParams = new URLSearchParams(url.search);

  const requestHeaders = new Headers(req.headers);
  requestHeaders.set("host", upstreamUrlObject.host);

  let body: string | undefined;

  if (req.method !== "GET" && req.method !== "HEAD") {
    const payload = (await req.json()) as JsonRecord;
    let normalizedPayload = payload;
    if (upstreamPath === "/v1/chart/render-data") {
      normalizedPayload = normalizeRenderDataPayload(payload);
    } else if (upstreamPath === "/v1/synastry/compare") {
      normalizedPayload = normalizeSynastryPayload(payload);
    }
    body = JSON.stringify(normalizedPayload);
    requestHeaders.set("content-type", "application/json");
  } else {
    const contentType = req.headers.get("content-type") ?? "";
    const contentLength = req.headers.get("content-length");
    const hasBody =
      contentType.includes("application/json") ||
      (contentLength !== null && contentLength !== "0");

    if (hasBody) {
      const rawBody = await req.text();
      if (rawBody) {
        try {
          const payload = JSON.parse(rawBody) as JsonRecord;
          for (const [key, value] of Object.entries(payload)) {
            if (value === null || value === undefined) {
              continue;
            }
            if (!queryParams.has(key)) {
              queryParams.set(key, String(value));
            }
          }
        } catch {
          // Ignore invalid JSON body on GET requests.
        }
      }
    }
  }

  const upstreamResponse = await fetch(
    `${upstreamUrlObject.origin}${targetPath}${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`,
    {
      method: req.method,
      headers: requestHeaders,
      body,
    },
  );

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: upstreamResponse.headers,
  });
});
